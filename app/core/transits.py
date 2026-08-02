"""Transits actuels : positions des planètes lentes à une date donnée, comparées au thème natal.

Seules les planètes lentes (Jupiter à Pluton) sont considérées : leurs transits durent
plusieurs jours à plusieurs mois, contrairement aux luminaires/planètes rapides dont la
position change en quelques heures et qui n'apportent pas de lecture 'de fond' utile ici.
"""

from __future__ import annotations

from datetime import date as date_type
from datetime import timedelta
from functools import lru_cache

from app.core import ephemeris
from app.core.aspects import BodyForAspect, angular_separation, compute_cross_aspects
from app.core.reference_data import aspects_reference, lot_timing_rules
from app.core.zodiac import SIGNS_FR, sign_and_degree

TRANSIT_PLANETS = ["Jupiter", "Saturn", "Uranus", "Neptune", "Pluto"]
DEFAULT_TRANSIT_ORB = 3.0
_MAJOR_ASPECT_NAMES = ["conjunction", "opposition", "square", "trine", "sextile"]


@lru_cache
def _major_aspect_definitions() -> list[dict]:
    return [a for a in aspects_reference()["major_aspects"] if a["name"] in _MAJOR_ASPECT_NAMES]


@lru_cache
def _favorability_lookup() -> dict[tuple[str, str], dict]:
    rules = lot_timing_rules()["transit_to_natal_favorability"]["rules"]
    lookup = {}
    for rule in rules:
        for aspect in rule["aspects"]:
            lookup[(rule["transiting_planet"], aspect)] = {"label": rule["label"], "description": rule["description"]}
    return lookup


def compute_current_transits(
    natal_bodies: list[BodyForAspect],
    as_of_date: date_type,
    orb: float = DEFAULT_TRANSIT_ORB,
) -> dict:
    # Midi UTC pour la date choisie : l'orbite de ces planètes est trop lente pour que
    # l'heure exacte du jour ait un impact significatif sur le résultat.
    jd_ut = ephemeris.local_datetime_to_jd_ut(as_of_date.isoformat(), "12:00:00", "UTC")

    transiting_bodies: list[BodyForAspect] = []
    positions = []
    for name in TRANSIT_PLANETS:
        raw = ephemeris.calc_planet(jd_ut, ephemeris.PLANET_IDS[name])
        transiting_bodies.append(BodyForAspect(name=name, longitude=raw.longitude, speed_longitude=raw.speed_longitude))
        sign, degree = sign_and_degree(raw.longitude)
        positions.append(
            {
                "name": name,
                "sign": sign,
                "sign_fr": SIGNS_FR[sign],
                "degree": round(degree, 2),
                "absolute_longitude": round(raw.longitude, 4),
                "retrograde": raw.speed_longitude < 0,
            }
        )

    orbs = dict.fromkeys(_MAJOR_ASPECT_NAMES, orb)
    raw_aspects = compute_cross_aspects(
        transiting_bodies, natal_bodies, orbs, include_minor=False, include_applying=True
    )

    favorability = _favorability_lookup()
    aspects = []
    for a in raw_aspects:
        info = favorability.get((a["body_a"], a["type"]), {"label": "neutre", "description": ""})
        aspects.append(
            {
                "transiting_planet": a["body_a"],
                "natal_point": a["body_b"],
                "type": a["type"],
                "type_fr": a["type_fr"],
                "orb": a["orb"],
                "applying": a["applying"],
                "favorability": info["label"],
                "favorability_description": info["description"],
            }
        )

    return {"date": as_of_date.isoformat(), "transiting_planets": positions, "aspects": aspects}


def compute_upcoming_transits(
    natal_bodies: list[BodyForAspect],
    start_date: date_type,
    end_date: date_type,
    peak_orb_threshold: float = 1.0,
    window_orb_threshold: float = 2.0,
) -> list[dict]:
    """Balaie la période jour par jour pour détecter les moments où un transit de planète
    lente est au plus près de l'exactitude (minimum local de l'orbe) avec un point natal.

    Le passage par un minimum local (plutôt qu'un simple seuil d'orbe) gère naturellement
    les boucles rétrogrades : une même planète peut ainsi 'toucher' le même aspect à trois
    reprises dans l'année (direct, rétrograde, direct), et chaque passage est détecté
    séparément. Une 'fenêtre active' (orbe <= window_orb_threshold) encadre chaque pic pour
    donner une période plutôt qu'une seule date.
    """
    definitions = _major_aspect_definitions()
    total_days = (end_date - start_date).days
    sample_dates = [start_date + timedelta(days=i) for i in range(total_days + 1)]

    positions_by_planet: dict[str, list[float]] = {name: [] for name in TRANSIT_PLANETS}
    for d in sample_dates:
        jd_ut = ephemeris.local_datetime_to_jd_ut(d.isoformat(), "12:00:00", "UTC")
        for name in TRANSIT_PLANETS:
            raw = ephemeris.calc_planet(jd_ut, ephemeris.PLANET_IDS[name])
            positions_by_planet[name].append(raw.longitude)

    favorability = _favorability_lookup()
    events = []

    for planet_name, longitudes in positions_by_planet.items():
        for natal_body in natal_bodies:
            for aspect_def in definitions:
                orb_series = [
                    abs(angular_separation(lon, natal_body.longitude) - aspect_def["angle"]) for lon in longitudes
                ]
                for i in range(1, len(orb_series) - 1):
                    is_local_min = orb_series[i] < orb_series[i - 1] and orb_series[i] < orb_series[i + 1]
                    if not (is_local_min and orb_series[i] <= peak_orb_threshold):
                        continue

                    window_start = sample_dates[i]
                    j = i
                    while j > 0 and orb_series[j - 1] <= window_orb_threshold:
                        j -= 1
                        window_start = sample_dates[j]
                    window_end = sample_dates[i]
                    j = i
                    while j < len(orb_series) - 1 and orb_series[j + 1] <= window_orb_threshold:
                        j += 1
                        window_end = sample_dates[j]

                    info = favorability.get((planet_name, aspect_def["name"]), {"label": "neutre", "description": ""})
                    events.append(
                        {
                            "transiting_planet": planet_name,
                            "natal_point": natal_body.name,
                            "type": aspect_def["name"],
                            "type_fr": aspect_def["name_fr"],
                            "peak_date": sample_dates[i].isoformat(),
                            "peak_orb": round(orb_series[i], 3),
                            "window_start": window_start.isoformat(),
                            "window_end": window_end.isoformat(),
                            "favorability": info["label"],
                            "favorability_description": info["description"],
                        }
                    )

    events.sort(key=lambda e: e["peak_date"])
    return events
