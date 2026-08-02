"""Transits actuels : positions des planètes lentes à une date donnée, comparées au thème natal.

Seules les planètes lentes (Jupiter à Pluton) sont considérées : leurs transits durent
plusieurs jours à plusieurs mois, contrairement aux luminaires/planètes rapides dont la
position change en quelques heures et qui n'apportent pas de lecture 'de fond' utile ici.
"""

from __future__ import annotations

from datetime import date as date_type
from functools import lru_cache

from app.core import ephemeris
from app.core.aspects import BodyForAspect, compute_cross_aspects
from app.core.reference_data import lot_timing_rules
from app.core.zodiac import SIGNS_FR, sign_and_degree

TRANSIT_PLANETS = ["Jupiter", "Saturn", "Uranus", "Neptune", "Pluto"]
DEFAULT_TRANSIT_ORB = 3.0
_MAJOR_ASPECT_NAMES = ["conjunction", "opposition", "square", "trine", "sextile"]


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
