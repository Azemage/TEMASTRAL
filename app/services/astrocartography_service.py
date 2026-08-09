"""Calcul et mise en cache des lignes d'astrocartographie natales et de transit
(cyclocartographie). Les lignes natales dépendent uniquement de l'instant de naissance (pas du
lieu : ce sont les positions planétaires globales à cet instant qui définissent les lignes,
projetées ensuite sur toute la carte du monde) ; elles sont calculées une seule fois par thème
et mises en cache. Les lignes de transit dépendent de l'instant présent et sont partagées par
tous les utilisateurs : un seul calcul par jour, mis en cache pour tous.
"""

from __future__ import annotations

from datetime import date as date_type
from datetime import datetime, timedelta, timezone

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import models
from app.core import ephemeris, reference_data
from app.core.astrocartography import (
    ASTROCARTOGRAPHY_PLANETS,
    LINE_TYPES,
    analyze_nearby_lines,
    compute_all_crossings,
    compute_astrocartography_lines,
    find_interesting_cities,
    haversine_km,
    line_longitude_at_latitude,
)
from app.core.ephemeris import PLANET_IDS

DEFAULT_TIME_WHEN_UNKNOWN = "12:00:00"


def jd_ut_for_chart(chart: models.NatalChart) -> float:
    effective_time = (
        chart.birth_time.isoformat() if (chart.birth_time_known and chart.birth_time) else DEFAULT_TIME_WHEN_UNKNOWN
    )
    return ephemeris.local_datetime_to_jd_ut(chart.birth_date.isoformat(), effective_time, chart.birth_timezone)


def compute_lines_for_jd(jd_ut: float) -> list[dict]:
    equatorial_positions = {
        name: ephemeris.calc_planet_equatorial(jd_ut, PLANET_IDS[name]) for name in ASTROCARTOGRAPHY_PLANETS
    }
    gst_degrees = ephemeris.greenwich_sidereal_time_degrees(jd_ut)
    lines = compute_astrocartography_lines(equatorial_positions, gst_degrees)
    return [{"planet": line.planet, "line_type": line.line_type, "line_points": line.line_points} for line in lines]


def get_or_compute_natal_lines(db: Session, chart: models.NatalChart) -> list[models.NatalAstrocartographyLine]:
    existing = (
        db.query(models.NatalAstrocartographyLine)
        .filter(models.NatalAstrocartographyLine.natal_chart_id == chart.id)
        .order_by(models.NatalAstrocartographyLine.planet, models.NatalAstrocartographyLine.line_type)
        .all()
    )
    if existing:
        return existing

    jd_ut = jd_ut_for_chart(chart)
    rows = [
        models.NatalAstrocartographyLine(
            natal_chart_id=chart.id, planet=line["planet"], line_type=line["line_type"], line_points=line["line_points"]
        )
        for line in compute_lines_for_jd(jd_ut)
    ]
    db.add_all(rows)
    try:
        db.commit()
    except IntegrityError:
        # Une requête concurrente pour ce même thème a gagné la course et inséré les lignes en
        # premier (contrainte UNIQUE natal_chart_id+planet+line_type) : on abandonne notre
        # insertion et on relit le cache qu'elle vient de remplir.
        db.rollback()
        return (
            db.query(models.NatalAstrocartographyLine)
            .filter(models.NatalAstrocartographyLine.natal_chart_id == chart.id)
            .order_by(models.NatalAstrocartographyLine.planet, models.NatalAstrocartographyLine.line_type)
            .all()
        )
    for row in rows:
        db.refresh(row)
    # Même ordre que la branche de lecture en cache ci-dessus (order_by planet, line_type),
    # pour que la réponse ne dépende pas de si c'est le premier ou un appel ultérieur.
    rows.sort(key=lambda r: (r.planet, r.line_type))
    return rows


def compute_interesting_cities_for_chart(
    db: Session, chart: models.NatalChart, threshold_km: float = 300.0, top_n: int = 12
) -> list[dict]:
    """Suggère automatiquement, parmi les grandes villes mondiales, celles au profil
    astrocartographique le plus marqué pour ce thème natal : proches de plusieurs lignes
    planétaires et/ou d'un croisement de lignes (voir find_interesting_cities)."""
    natal_lines = get_or_compute_natal_lines(db, chart)
    lines_as_dicts = [
        {"planet": line.planet, "line_type": line.line_type, "line_points": line.line_points} for line in natal_lines
    ]
    crossings = compute_all_crossings(lines_as_dicts)
    cities = reference_data.world_cities()
    return find_interesting_cities(lines_as_dicts, crossings, cities, threshold_km=threshold_km, top_n=top_n)


def get_or_compute_transit_lines(db: Session, as_of_date: date_type | None = None) -> list[models.GlobalTransitLinesCache]:
    calc_date = as_of_date or datetime.now(timezone.utc).date()
    existing = (
        db.query(models.GlobalTransitLinesCache)
        .filter(models.GlobalTransitLinesCache.calculation_date == calc_date)
        .order_by(models.GlobalTransitLinesCache.planet, models.GlobalTransitLinesCache.line_type)
        .all()
    )
    if existing:
        return existing

    jd_ut = ephemeris.jd_ut_for_date_utc_noon(calc_date.isoformat())
    rows = [
        models.GlobalTransitLinesCache(
            calculation_date=calc_date, planet=line["planet"], line_type=line["line_type"], line_points=line["line_points"]
        )
        for line in compute_lines_for_jd(jd_ut)
    ]
    db.add_all(rows)
    try:
        db.commit()
    except IntegrityError:
        # Cache partagé par tous les utilisateurs : une autre requête concurrente pour la même
        # date a déjà inséré les lignes en premier. On relit son résultat plutôt que d'échouer.
        db.rollback()
        return (
            db.query(models.GlobalTransitLinesCache)
            .filter(models.GlobalTransitLinesCache.calculation_date == calc_date)
            .order_by(models.GlobalTransitLinesCache.planet, models.GlobalTransitLinesCache.line_type)
            .all()
        )
    for row in rows:
        db.refresh(row)
    rows.sort(key=lambda r: (r.planet, r.line_type))
    return rows


def compute_interesting_cities_for_transit(
    db: Session, as_of_date: date_type | None = None, threshold_km: float = 300.0, top_n: int = 5
) -> list[dict]:
    """Équivalent de compute_interesting_cities_for_chart mais pour la cyclocartographie
    (transit) : classe les grandes villes mondiales selon leur proximité aux lignes de transit
    et aux croisements de lignes DU JOUR (ou de la date demandée) — recalculé à chaque date
    différente puisque les lignes de transit bougent avec le temps."""
    transit_lines = get_or_compute_transit_lines(db, as_of_date)
    lines_as_dicts = [
        {"planet": line.planet, "line_type": line.line_type, "line_points": line.line_points} for line in transit_lines
    ]
    crossings = compute_all_crossings(lines_as_dicts)
    cities = reference_data.world_cities()
    return find_interesting_cities(lines_as_dicts, crossings, cities, threshold_km=threshold_km, top_n=top_n)


def create_saved_location(
    db: Session,
    session: models.AnonymousSession,
    chart: models.NatalChart,
    label: str | None,
    city: str | None,
    country: str | None,
    latitude: float,
    longitude: float,
) -> models.SavedLocation:
    natal_lines = get_or_compute_natal_lines(db, chart)
    lines_as_dicts = [{"planet": line.planet, "line_type": line.line_type, "line_points": line.line_points} for line in natal_lines]
    nearby = analyze_nearby_lines(lines_as_dicts, latitude, longitude)

    location = models.SavedLocation(
        anonymous_session_id=session.id,
        natal_chart_id=chart.id,
        label=label,
        city=city,
        country=country,
        latitude=latitude,
        longitude=longitude,
        nearby_lines_analysis=nearby,
    )
    db.add(location)
    db.commit()
    db.refresh(location)
    return location


def list_saved_locations(db: Session, chart: models.NatalChart) -> list[models.SavedLocation]:
    return (
        db.query(models.SavedLocation)
        .filter(models.SavedLocation.natal_chart_id == chart.id)
        .order_by(models.SavedLocation.created_at.desc())
        .all()
    )


class SavedLocationAccessError(Exception):
    """Levée quand un lieu sauvegardé est demandé par une session qui n'en est pas propriétaire."""


def delete_saved_location(db: Session, session: models.AnonymousSession, location_id: str) -> bool:
    location = db.query(models.SavedLocation).filter(models.SavedLocation.id == location_id).first()
    if location is None:
        return False
    if location.anonymous_session_id != session.id:
        raise SavedLocationAccessError("Ce lieu sauvegardé n'appartient pas à cette session.")
    db.delete(location)
    db.commit()
    return True


def compute_location_forecast(
    latitude: float,
    longitude: float,
    start_date: date_type,
    years: int,
    planets: list[str] | None = None,
    line_types: list[str] | None = None,
    threshold_km: float = 300.0,
    step_days: int = 7,
) -> list[dict]:
    """Prévision inverse de la carte du jour : le lieu est fixe, on balaie le temps pour
    détecter les fenêtres où une ligne planétaire (de transit) passe à proximité. Pour chaque
    date échantillonnée, la longitude de la ligne est évaluée directement à `latitude` (voir
    line_longitude_at_latitude) plutôt que sur les 170 latitudes du tracé complet — inutile ici
    puisqu'on ne s'intéresse qu'à un seul point, et bien plus rapide sur un horizon de
    plusieurs années. Les échantillons consécutifs sous le seuil sont regroupés en fenêtres
    avec une date de plus grande proximité (`peak_date`)."""
    selected_planets = planets or ASTROCARTOGRAPHY_PLANETS
    selected_line_types = line_types or list(LINE_TYPES)
    end_date = start_date + timedelta(days=round(years * 365.25))

    samples: list[tuple[date_type, dict[tuple[str, str], float | None]]] = []
    current = start_date
    while current <= end_date:
        jd_ut = ephemeris.jd_ut_for_date_utc_noon(current.isoformat())
        equatorial_positions = {planet: ephemeris.calc_planet_equatorial(jd_ut, PLANET_IDS[planet]) for planet in selected_planets}
        gst_degrees = ephemeris.greenwich_sidereal_time_degrees(jd_ut)

        distances: dict[tuple[str, str], float | None] = {}
        for planet in selected_planets:
            for line_type in selected_line_types:
                line_lon = line_longitude_at_latitude(equatorial_positions[planet], gst_degrees, line_type, latitude)
                distances[(planet, line_type)] = (
                    None if line_lon is None else haversine_km(latitude, longitude, latitude, line_lon)
                )
        samples.append((current, distances))
        current += timedelta(days=step_days)

    windows: list[dict] = []
    for planet in selected_planets:
        for line_type in selected_line_types:
            key = (planet, line_type)
            open_window: dict | None = None
            for sample_date, distances in samples:
                distance = distances[key]
                active = distance is not None and distance <= threshold_km
                if active:
                    if open_window is None:
                        open_window = {
                            "planet": planet,
                            "line_type": line_type,
                            "start_date": sample_date,
                            "end_date": sample_date,
                            "peak_date": sample_date,
                            "peak_distance_km": distance,
                        }
                    else:
                        open_window["end_date"] = sample_date
                        if distance < open_window["peak_distance_km"]:
                            open_window["peak_distance_km"] = distance
                            open_window["peak_date"] = sample_date
                elif open_window is not None:
                    windows.append(open_window)
                    open_window = None
            if open_window is not None:
                windows.append(open_window)

    windows.sort(key=lambda w: w["start_date"])
    return windows
