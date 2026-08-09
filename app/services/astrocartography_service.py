"""Calcul et mise en cache des lignes d'astrocartographie natales et de transit
(cyclocartographie). Les lignes natales dépendent uniquement de l'instant de naissance (pas du
lieu : ce sont les positions planétaires globales à cet instant qui définissent les lignes,
projetées ensuite sur toute la carte du monde) ; elles sont calculées une seule fois par thème
et mises en cache. Les lignes de transit dépendent de l'instant présent et sont partagées par
tous les utilisateurs : un seul calcul par jour, mis en cache pour tous.
"""

from __future__ import annotations

from datetime import date as date_type
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app import models
from app.core import ephemeris
from app.core.astrocartography import ASTROCARTOGRAPHY_PLANETS, analyze_nearby_lines, compute_astrocartography_lines
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
    db.commit()
    for row in rows:
        db.refresh(row)
    # Même ordre que la branche de lecture en cache ci-dessus (order_by planet, line_type),
    # pour que la réponse ne dépende pas de si c'est le premier ou un appel ultérieur.
    rows.sort(key=lambda r: (r.planet, r.line_type))
    return rows


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
    db.commit()
    for row in rows:
        db.refresh(row)
    rows.sort(key=lambda r: (r.planet, r.line_type))
    return rows


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
