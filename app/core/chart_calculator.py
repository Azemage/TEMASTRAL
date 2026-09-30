"""Assemble le thème natal complet : planètes, angles, maisons, aspects, balances, dispositeurs."""

from __future__ import annotations

from app.core import ephemeris
from app.core.aspects import BodyForAspect, compute_aspects
from app.core.derived_houses import compute_derived_houses
from app.core.degrees import analyze_degree
from app.core.dispositors import CLASSIC_PLANETS, compute_dispositors
from app.core.draconic import compute_draconic_chart
from app.core.house_modality import (
    compute_house_modality_analysis,
    group_houses_by_angle_centered_quadrant,
    group_houses_by_standard_quadrant,
)
from app.core.lots import compute_lots
from app.core.traits import compute_character_traits
from app.core.zodiac import ELEMENTS, MODALITIES, sign_and_degree

DEFAULT_TIME_WHEN_UNKNOWN = "12:00:00"


def _position_dict(name: str, longitude: float, house: int | None, retrograde: bool) -> dict:
    sign, degree = sign_and_degree(longitude)
    from app.core.zodiac import SIGNS_FR

    return {
        "name": name,
        "sign": sign,
        "sign_fr": SIGNS_FR[sign],
        "degree": round(degree, 2),
        "absolute_longitude": round(longitude, 4),
        "house": house,
        "retrograde": retrograde,
    }


def _angle_dict(longitude: float) -> dict:
    sign, degree = sign_and_degree(longitude)
    from app.core.zodiac import SIGNS_FR

    return {
        "sign": sign,
        "sign_fr": SIGNS_FR[sign],
        "degree": round(degree, 2),
        "absolute_longitude": round(longitude, 4),
    }


def find_house(longitude: float, cusps: list[float]) -> int:
    longitude = longitude % 360
    for i in range(12):
        start = cusps[i]
        end = cusps[(i + 1) % 12]
        if start < end:
            if start <= longitude < end:
                return i + 1
        else:  # la maison traverse 0°
            if longitude >= start or longitude < end:
                return i + 1
    return 12


def calculate_natal_chart(
    birth_date: str,
    birth_time: str | None,
    time_known: bool,
    timezone: str,
    latitude: float,
    longitude: float,
    house_system: str = "placidus",
    aspect_orbs: dict[str, float] | None = None,
    include_minor_aspects: bool = True,
    optional_points: list[str] | None = None,
    ascendant_override_longitude: float | None = None,
) -> dict:
    optional_points = optional_points or []
    aspect_orbs = aspect_orbs or {}
    effective_time = birth_time if (time_known and birth_time) else DEFAULT_TIME_WHEN_UNKNOWN

    jd_ut = ephemeris.local_datetime_to_jd_ut(birth_date, effective_time, timezone)

    bodies_result = ephemeris.calc_all_bodies(jd_ut, optional_points)

    if ascendant_override_longitude is not None:
        # Ascendant fixé manuellement (ex. rectification par questionnaire) : la ville/heure
        # de naissance exactes ne sont alors ni connues ni utilisées pour les maisons, donc
        # seule une convention indépendante de l'heure a du sens ici — maisons de signes
        # intégraux (whole sign) à partir du signe ascendant donné. Le Milieu du Ciel n'est
        # dans ce cas qu'un repère de maison 10 (0° du 10e signe), pas l'angle astronomique
        # réel, faute d'heure/lieu exacts pour le calculer.
        house1_start = (ascendant_override_longitude % 360 // 30) * 30
        cusps = [(house1_start + i * 30) % 360 for i in range(12)]
    else:
        houses_result = ephemeris.calc_houses(jd_ut, latitude, longitude, house_system)
        cusps = houses_result.cusps

    planets = []
    planet_signs: dict[str, str] = {}
    degree_analysis = []
    aspect_bodies: list[BodyForAspect] = []
    for name, raw in bodies_result.bodies.items():
        house = find_house(raw.longitude, cusps)
        planets.append(_position_dict(name, raw.longitude, house, raw.retrograde))
        aspect_bodies.append(BodyForAspect(name=name, longitude=raw.longitude, speed_longitude=raw.speed_longitude))
        sign, degree = sign_and_degree(raw.longitude)
        degree_analysis.append({**analyze_degree(name, sign, degree), "house": house})
        if name in CLASSIC_PLANETS:
            planet_signs[name] = sign

    if ascendant_override_longitude is not None:
        ascendant = ascendant_override_longitude % 360
        midheaven = cusps[9]  # repère de maison 10 (voir remarque ci-dessus), pas l'angle réel
    else:
        ascendant = houses_result.ascendant
        midheaven = houses_result.midheaven
    descendant = (ascendant + 180) % 360
    imum_coeli = (midheaven + 180) % 360

    angles = {
        "ascendant": _angle_dict(ascendant),
        "midheaven": _angle_dict(midheaven),
        "descendant": _angle_dict(descendant),
        "imum_coeli": _angle_dict(imum_coeli),
    }

    houses = []
    for i, cusp_longitude in enumerate(cusps):
        sign, degree = sign_and_degree(cusp_longitude)
        from app.core.zodiac import SIGNS_FR

        houses.append(
            {
                "number": i + 1,
                "sign": sign,
                "sign_fr": SIGNS_FR[sign],
                "degree": round(degree, 2),
                "absolute_longitude": round(cusp_longitude, 4),
            }
        )

    aspects = compute_aspects(aspect_bodies, aspect_orbs, include_minor=include_minor_aspects)

    elements_balance = {"fire": 0, "earth": 0, "air": 0, "water": 0}
    modality_balance = {"cardinal": 0, "fixed": 0, "mutable": 0}
    for planet in planets:
        if planet["name"] not in CLASSIC_PLANETS:
            continue
        elements_balance[ELEMENTS[planet["sign"]]] += 1
        modality_balance[MODALITIES[planet["sign"]]] += 1

    sun_house = next((p["house"] for p in planets if p["name"] == "Sun"), None)
    is_day_chart = sun_house is not None and 7 <= sun_house <= 12

    dispositors_traditional = compute_dispositors(planet_signs, "traditional")
    dispositors_modern = compute_dispositors(planet_signs, "modern")

    character_traits = compute_character_traits(
        planets=planets,
        ascendant_sign=angles["ascendant"]["sign"],
        elements_balance=elements_balance,
        modality_balance=modality_balance,
    )

    lot_points = {"ASC": ascendant, "MC": midheaven, "Descendant": descendant, "IC": imum_coeli}
    lot_points.update({name: raw.longitude for name, raw in bodies_result.bodies.items()})
    lot_points.update({f"house_cusp_{i + 1}": cusp for i, cusp in enumerate(cusps)})
    lots = compute_lots(
        points=lot_points,
        is_day_chart=is_day_chart,
        find_house_fn=lambda lon: find_house(lon, cusps),
        natal_bodies=aspect_bodies,
        aspect_orbs=aspect_orbs,
    )

    derived_houses = compute_derived_houses(planets)

    house_modality_analysis = compute_house_modality_analysis(planets)
    house_quadrants_standard = group_houses_by_standard_quadrant()
    house_quadrants_angle_centered = group_houses_by_angle_centered_quadrant()

    north_node_raw = bodies_result.bodies.get("north_node")
    draconic = compute_draconic_chart(
        planets,
        angles,
        houses,
        aspects,
        jd_ut,
        north_node_raw.longitude if north_node_raw else None,
    )

    return {
        "schema_version": 1,
        "time_known": time_known,
        "ascendant_manually_set": ascendant_override_longitude is not None,
        "is_day_chart": is_day_chart,
        "planets": planets,
        "angles": angles,
        "houses": houses,
        "aspects": aspects,
        "elements_balance": elements_balance,
        "modality_balance": modality_balance,
        "dispositors_traditional": dispositors_traditional,
        "dispositors_modern": dispositors_modern,
        "character_traits": character_traits,
        "lots": lots,
        "derived_houses": derived_houses,
        "draconic": draconic,
        "degree_analysis": degree_analysis,
        "house_modality_analysis": house_modality_analysis,
        "house_quadrants_standard": house_quadrants_standard,
        "house_quadrants_angle_centered": house_quadrants_angle_centered,
        "unavailable_points": bodies_result.unavailable_points,
    }
