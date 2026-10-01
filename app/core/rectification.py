"""Rectification de l'heure de naissance par recoupement d'événements de vie déjà survenus
contre les angles (Ascendant/Milieu du Ciel/Descendant/Fond du Ciel) obtenus pour chaque heure
candidate d'un intervalle donné — deuxième étape du questionnaire de rectification (la première
étant le questionnaire de traits physiques/tempérament, purement déclaratif, voir
app/reference_data/ascendant_rectification_traits.json).

[Interprétatif / traditionnel] Combine trois signaux classiques de rectification, chacun
approximatif pris isolément :
- transits réels (positions planétaires à la date de l'événement) en aspect majeur avec les
  angles de chaque heure candidate ;
- directions par arc solaire (toutes les planètes natales avancées du même nombre de degrés
  que d'années écoulées), en conjonction avec les angles ;
- Lune progressée (progression secondaire, un jour d'éphéméride pour une année de vie), en
  conjonction avec les angles — le signal le plus discriminant du fait de sa vitesse.

N'utilise QUE des événements déjà survenus pour resserrer une heure de naissance inconnue ou
approximative : l'inverse d'une prédiction. Voir ASCENDANT_RECTIFICATION_WARNING, à toujours
afficher avec le résultat — un score élevé ne prouve rien à lui seul, plusieurs heures peuvent
produire des scores proches.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date as date_type

from app.core import ephemeris
from app.core.aspects import BodyForAspect, angular_separation, compute_cross_aspects
from app.core.transits import TRANSIT_PLANETS
from app.core.zodiac import sign_and_degree

ASCENDANT_RECTIFICATION_WARNING = (
    "Technique de recoupement indicative (transits et directions vers les angles à la date "
    "d'événements de vie déjà survenus), pas une méthode garantie : plusieurs heures peuvent "
    "produire des scores proches, et un score élevé ne prouve rien à lui seul. À croiser avec "
    "le questionnaire de traits physiques/tempérament et, si possible, avec un acte de "
    "naissance ou un souvenir familial de l'heure."
)

_NATAL_PLANETS_FOR_DIRECTIONS = [
    "Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto",
]
_SOLAR_ARC_ORB = 1.0
_PROGRESSED_MOON_ORB = 2.0
_TRANSIT_ORBS = {"conjunction": 2.0, "opposition": 2.0, "square": 2.0, "trine": 1.5, "sextile": 1.5}
_SIGNIFICANCE_WEIGHT = {"major": 1.5, "moderate": 1.0}

# Poids par planète transitante : les signaux lents (Saturne, Uranus, Pluton...) sont
# traditionnellement les plus décisifs pour la rectification (un aspect exact et rare compte
# plus qu'un passage lunaire quotidien, beaucoup trop fréquent pour discriminer une heure).
_RECTIFICATION_PLANET_WEIGHT = {
    "Sun": 0.5, "Moon": 0.3, "Mercury": 0.3, "Venus": 0.3, "Mars": 0.7,
    "Jupiter": 1.0, "Saturn": 1.5, "Uranus": 1.5, "Neptune": 1.3, "Pluto": 1.5, "chiron": 1.0,
}
_ASPECT_WEIGHT = {"conjunction": 1.0, "opposition": 1.0, "square": 0.8, "trine": 0.5, "sextile": 0.4}


@dataclass
class LifeEvent:
    label: str
    event_date: date_type
    significance: str = "major"  # "major" ou "moderate"


@dataclass
class _PrecomputedEvent:
    event: LifeEvent
    transiting_bodies: list[BodyForAspect]
    arc_years: float  # (event_date - birth_date).days / 365.25
    weight: float


def _angle_bodies(ascendant: float, midheaven: float) -> list[BodyForAspect]:
    descendant = (ascendant + 180) % 360
    imum_coeli = (midheaven + 180) % 360
    return [
        BodyForAspect(name="ascendant", longitude=ascendant),
        BodyForAspect(name="midheaven", longitude=midheaven),
        BodyForAspect(name="descendant", longitude=descendant),
        BodyForAspect(name="imum_coeli", longitude=imum_coeli),
    ]


def _precompute_events(life_events: list[LifeEvent], birth_date: date_type) -> list[_PrecomputedEvent]:
    precomputed = []
    for event in life_events:
        jd_event = ephemeris.local_datetime_to_jd_ut(event.event_date.isoformat(), "12:00:00", "UTC")
        transiting_bodies = []
        for name in TRANSIT_PLANETS:
            raw = ephemeris.calc_planet(jd_event, ephemeris.PLANET_IDS[name])
            transiting_bodies.append(BodyForAspect(name=name, longitude=raw.longitude, speed_longitude=raw.speed_longitude))
        arc_years = (event.event_date - birth_date).days / 365.25
        weight = _SIGNIFICANCE_WEIGHT.get(event.significance, 1.0)
        precomputed.append(_PrecomputedEvent(event=event, transiting_bodies=transiting_bodies, arc_years=arc_years, weight=weight))
    return precomputed


def _score_candidate(
    jd_ut: float, angle_bodies: list[BodyForAspect], precomputed_events: list[_PrecomputedEvent]
) -> tuple[float, list[dict]]:
    natal_planet_longitudes = {
        name: ephemeris.calc_planet(jd_ut, ephemeris.PLANET_IDS[name]).longitude
        for name in _NATAL_PLANETS_FOR_DIRECTIONS
    }
    moon_id = ephemeris.PLANET_IDS["Moon"]

    total_score = 0.0
    matches: list[dict] = []

    for pre in precomputed_events:
        # 1) Transits réels (à la date de l'événement) en aspect avec les angles de cette heure.
        aspects = compute_cross_aspects(
            pre.transiting_bodies, angle_bodies, _TRANSIT_ORBS, include_minor=False, include_applying=False
        )
        for a in aspects:
            planet_weight = _RECTIFICATION_PLANET_WEIGHT.get(a["body_a"], 0.5)
            aspect_weight = _ASPECT_WEIGHT.get(a["type"], 0.5)
            orb_limit = _TRANSIT_ORBS[a["type"]]
            exactness = max(0.0, 1 - a["orb"] / orb_limit)
            contribution = planet_weight * aspect_weight * exactness * pre.weight
            if contribution <= 0:
                continue
            total_score += contribution
            matches.append(
                {
                    "event_label": pre.event.label,
                    "event_date": pre.event.event_date.isoformat(),
                    "method": "transit",
                    "body": a["body_a"],
                    "angle": a["body_b"],
                    "aspect_type": a["type"],
                    "orb": a["orb"],
                    "score": round(contribution, 3),
                }
            )

        # 2) Directions par arc solaire (conjonction uniquement, orbe serré) vers les angles.
        for planet_name, natal_lon in natal_planet_longitudes.items():
            directed_lon = (natal_lon + pre.arc_years) % 360
            for angle_body in angle_bodies:
                sep = angular_separation(directed_lon, angle_body.longitude)
                if sep > _SOLAR_ARC_ORB:
                    continue
                exactness = 1 - sep / _SOLAR_ARC_ORB
                contribution = exactness * pre.weight
                total_score += contribution
                matches.append(
                    {
                        "event_label": pre.event.label,
                        "event_date": pre.event.event_date.isoformat(),
                        "method": "solar_arc",
                        "body": planet_name,
                        "angle": angle_body.name,
                        "aspect_type": "conjunction",
                        "orb": round(sep, 3),
                        "score": round(contribution, 3),
                    }
                )

        # 3) Lune progressée (progression secondaire, jour pour an) en conjonction avec un
        # angle — signal traditionnellement le plus discriminant (mouvement rapide).
        progressed_jd = jd_ut + pre.arc_years
        progressed_moon_lon = ephemeris.calc_planet(progressed_jd, moon_id).longitude
        for angle_body in angle_bodies:
            sep = angular_separation(progressed_moon_lon, angle_body.longitude)
            if sep > _PROGRESSED_MOON_ORB:
                continue
            exactness = 1 - sep / _PROGRESSED_MOON_ORB
            contribution = exactness * pre.weight * 1.2
            total_score += contribution
            matches.append(
                {
                    "event_label": pre.event.label,
                    "event_date": pre.event.event_date.isoformat(),
                    "method": "progressed_moon",
                    "body": "Moon",
                    "angle": angle_body.name,
                    "aspect_type": "conjunction",
                    "orb": round(sep, 3),
                    "score": round(contribution, 3),
                }
            )

    matches.sort(key=lambda m: -m["score"])
    return total_score, matches[:12]


def _parse_hhmmss_to_minutes(value: str) -> int:
    hh, mm, *_rest = value.split(":")
    return int(hh) * 60 + int(mm)


def scan_candidate_times(
    birth_date: date_type,
    timezone: str,
    latitude: float,
    longitude: float,
    life_events: list[LifeEvent],
    window_start: str = "00:00:00",
    window_end: str = "23:59:00",
    step_minutes: int = 4,
    house_system: str = "placidus",
    candidate_signs: list[str] | None = None,
    top_n: int = 15,
) -> dict:
    """Balaie [window_start, window_end] par pas de `step_minutes`, calcule les angles de
    chaque heure candidate et les score contre `life_events` (voir _score_candidate). Retourne
    les `top_n` meilleures heures ainsi qu'un résumé par signe ascendant sur tout le balayage
    (utile même sans filtrage `candidate_signs`)."""
    precomputed_events = _precompute_events(life_events, birth_date)

    start_minutes = _parse_hhmmss_to_minutes(window_start)
    end_minutes = _parse_hhmmss_to_minutes(window_end)
    step_minutes = max(1, step_minutes)

    candidates = []
    for minute in range(start_minutes, end_minutes + 1, step_minutes):
        hh, mm = divmod(minute, 60)
        time_str = f"{hh:02d}:{mm:02d}:00"
        jd_ut = ephemeris.local_datetime_to_jd_ut(birth_date.isoformat(), time_str, timezone)
        houses_result = ephemeris.calc_houses(jd_ut, latitude, longitude, house_system)
        ascendant = houses_result.ascendant
        midheaven = houses_result.midheaven
        asc_sign, asc_degree = sign_and_degree(ascendant)

        if candidate_signs and asc_sign not in candidate_signs:
            continue

        mc_sign, mc_degree = sign_and_degree(midheaven)
        angle_bodies = _angle_bodies(ascendant, midheaven)
        total_score, matches = _score_candidate(jd_ut, angle_bodies, precomputed_events)

        candidates.append(
            {
                "time": time_str,
                "ascendant_sign": asc_sign,
                "ascendant_degree": round(asc_degree, 2),
                "midheaven_sign": mc_sign,
                "midheaven_degree": round(mc_degree, 2),
                "total_score": round(total_score, 3),
                "matches": matches,
            }
        )

    candidates.sort(key=lambda c: -c["total_score"])
    top_candidates = candidates[:top_n]

    by_sign: dict[str, dict] = {}
    for c in candidates:
        entry = by_sign.setdefault(c["ascendant_sign"], {"sign": c["ascendant_sign"], "best_score": 0.0, "candidate_count": 0})
        entry["candidate_count"] += 1
        entry["best_score"] = max(entry["best_score"], c["total_score"])
    by_sign_summary = sorted(by_sign.values(), key=lambda e: -e["best_score"])

    return {
        "candidates": top_candidates,
        "by_sign_summary": by_sign_summary,
        "warning": ASCENDANT_RECTIFICATION_WARNING,
    }
