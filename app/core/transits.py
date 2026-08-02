"""Transits sur les douze prochains mois : positions planétaires à une date donnée et
transits à venir, comparés au thème natal.

Toutes les planètes classiques sont incluses (Soleil à Pluton) : l'horizon est borné à un an,
donc même les planètes rapides (Lune, Mercure, Vénus, Mars) restent pertinentes sans faire
exploser la portée du calcul. Leur vitesse angulaire impose en revanche un échantillonnage
plus fin que pour les planètes lentes (voir `SAMPLE_STEP_DAYS`), sans quoi un passage exact
pourrait être 'sauté' entre deux échantillons trop espacés.
"""

from __future__ import annotations

from datetime import date as date_type
from datetime import timedelta
from functools import lru_cache

from app.core import ephemeris
from app.core.aspects import BodyForAspect, angular_separation, compute_cross_aspects
from app.core.reference_data import aspects_reference, lot_timing_rules
from app.core.zodiac import SIGNS_FR, sign_and_degree

TRANSIT_PLANETS = ["Moon", "Mercury", "Venus", "Sun", "Mars", "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto"]
DEFAULT_TRANSIT_ORB = 3.0
_MAJOR_ASPECT_NAMES = ["conjunction", "opposition", "square", "trine", "sextile"]

# Pas d'échantillonnage (en jours) par planète pour le balayage de l'année, calé sur sa
# vitesse angulaire maximale de sorte qu'un passage exact ne puisse jamais être manqué entre
# deux échantillons consécutifs.
SAMPLE_STEP_DAYS: dict[str, float] = {
    "Moon": 1 / 24,  # jusqu'à ~13°/j
    "Mercury": 0.25,
    "Venus": 0.25,
    "Sun": 0.25,
    "Mars": 0.25,
    "Jupiter": 1.0,
    "Saturn": 1.0,
    "Uranus": 1.0,
    "Neptune": 1.0,
    "Pluto": 1.0,
}

# Poids utilisés pour la note d'intensité (1 à 4 flammes) : une planète lente/lourde ou un
# aspect dur pèsent plus qu'un passage rapide ou une harmonie douce. Reflète la différence
# entre un transit de fond (Saturne, Pluton...) et un frôlement quotidien (Lune notamment).
PLANET_INTENSITY_WEIGHT: dict[str, float] = {
    "Moon": 1.0,
    "Mercury": 1.5,
    "Venus": 1.5,
    "Sun": 2.0,
    "Mars": 2.5,
    "Jupiter": 3.0,
    "Neptune": 3.5,
    "Uranus": 3.5,
    "Saturn": 4.0,
    "Pluto": 4.0,
}

ASPECT_INTENSITY_WEIGHT: dict[str, float] = {
    "conjunction": 4.0,
    "opposition": 4.0,
    "square": 3.0,
    "trine": 2.0,
    "sextile": 1.0,
}


def _intensity_flames(planet_name: str, aspect_name: str, orb: float, orb_reference: float) -> int:
    """Note d'intensité de 1 à 4 flammes, combinant poids de la planète, poids de l'aspect et
    précision de l'orbe (plus l'aspect est exact par rapport à `orb_reference`, l'orbe maximal
    considéré dans ce contexte, plus il pèse)."""
    planet_weight = PLANET_INTENSITY_WEIGHT.get(planet_name, 2.0)
    aspect_weight = ASPECT_INTENSITY_WEIGHT.get(aspect_name, 1.0)
    orb_factor = max(0.0, 1 - orb / orb_reference) if orb_reference > 0 else 1.0
    score = planet_weight * aspect_weight * (0.6 + 0.4 * orb_factor)
    if score >= 10:
        return 4
    if score >= 6:
        return 3
    if score >= 3:
        return 2
    return 1


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
    # Midi UTC pour la date choisie : suffisant pour situer les planètes lentes, et pour les
    # rapides (Lune incluse) l'écart avec l'heure exacte de naissance/consultation reste
    # inférieur à l'orbe utilisée ici.
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
                "intensity": _intensity_flames(a["body_a"], a["type"], a["orb"], orb),
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
    """Balaie la période pour détecter les moments où un transit est au plus près de
    l'exactitude (minimum local de l'orbe) avec un point natal, planète par planète, chacune
    à son propre pas d'échantillonnage (`SAMPLE_STEP_DAYS`).

    Le passage par un minimum local (plutôt qu'un simple seuil d'orbe) gère naturellement
    les boucles rétrogrades : une même planète peut ainsi 'toucher' le même aspect à plusieurs
    reprises dans l'année (direct, rétrograde, direct), et chaque passage est détecté
    séparément. Une 'fenêtre active' (orbe <= window_orb_threshold) encadre chaque pic pour
    donner une période plutôt qu'une seule date.
    """
    definitions = _major_aspect_definitions()
    total_days = (end_date - start_date).days
    start_jd = ephemeris.local_datetime_to_jd_ut(start_date.isoformat(), "12:00:00", "UTC")

    favorability = _favorability_lookup()
    events = []

    for planet_name in TRANSIT_PLANETS:
        step = SAMPLE_STEP_DAYS.get(planet_name, 1.0)
        n_samples = int(total_days / step) + 1
        offsets = [i * step for i in range(n_samples)]
        longitudes = [ephemeris.calc_planet(start_jd + offset, ephemeris.PLANET_IDS[planet_name]).longitude for offset in offsets]
        sample_dates = [start_date + timedelta(days=offset) for offset in offsets]

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
                            "intensity": _intensity_flames(
                                planet_name, aspect_def["name"], orb_series[i], peak_orb_threshold
                            ),
                        }
                    )

    events.sort(key=lambda e: e["peak_date"])
    return events
