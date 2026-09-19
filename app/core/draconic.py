"""Thème draconique : dérivé du thème natal par une rotation de tous les points de sorte que
le Nœud Nord tombe à 0° Bélier — lu traditionnellement comme la carte de l'âme avant
l'incarnation, la nature profonde qui précède la personnalité exprimée par le thème natal.

Point clé : comme TOUS les points (planètes, angles, cuspides) subissent exactement la même
rotation, deux choses restent rigoureusement IDENTIQUES au thème natal — la distance angulaire
entre deux points ne change jamais sous une rotation globale :
- la maison occupée par chaque planète (distance planète <-> cuspide inchangée)
- les aspects entre planètes (distance planète <-> planète inchangée)

`houses` (numéro de maison par planète) et `aspects` sont donc repris tels quels du thème
natal, JAMAIS recalculés. Seul le SIGNE de chaque point change (et donc les balances élément/
modalité, qui en dépendent) : c'est la seule chose que ce module calcule réellement. Appelé
directement depuis chart_calculator.calculate_natal_chart, sur le même principe que
compute_derived_houses — stocké dans computed_chart_data, pas d'endpoint séparé.
"""

from __future__ import annotations

from app.core import ephemeris
from app.core.dispositors import CLASSIC_PLANETS
from app.core.zodiac import ELEMENTS, MODALITIES, SIGNS_FR, sign_and_degree

SCHEMA_VERSION = 1


def _shifted_point(longitude: float, node_longitude: float) -> dict:
    draconic_longitude = (longitude - node_longitude) % 360
    sign, degree = sign_and_degree(draconic_longitude)
    return {
        "sign": sign,
        "sign_fr": SIGNS_FR[sign],
        "degree": round(degree, 2),
        "absolute_longitude": round(draconic_longitude, 4),
    }


def compute_draconic_chart(
    planets: list[dict],
    angles: dict,
    houses: list[dict],
    aspects: list[dict],
    jd_ut: float,
    north_node_longitude: float | None,
) -> dict:
    """`north_node_longitude` vient de `bodies_result.bodies["north_node"]` quand ce point a été
    sélectionné (cas par défaut désormais) ; sinon recalculé ici directement (calcul orbital
    pur, sans fichier d'éphémérides externe) pour que la rotation fonctionne même sur un thème
    plus ancien où les Nœuds n'auraient pas été choisis."""
    if north_node_longitude is None:
        north_node_longitude = ephemeris.calc_planet(jd_ut, ephemeris.NORTH_NODE_ID).longitude

    draconic_planets = []
    for p in planets:
        shifted = _shifted_point(p["absolute_longitude"], north_node_longitude)
        draconic_planets.append({**shifted, "name": p["name"], "house": p["house"], "retrograde": p["retrograde"]})

    draconic_angles = {
        name: _shifted_point(a["absolute_longitude"], north_node_longitude) for name, a in angles.items()
    }

    draconic_houses = [
        {**_shifted_point(h["absolute_longitude"], north_node_longitude), "number": h["number"]} for h in houses
    ]

    elements_balance = {"fire": 0, "earth": 0, "air": 0, "water": 0}
    modality_balance = {"cardinal": 0, "fixed": 0, "mutable": 0}
    for planet in draconic_planets:
        if planet["name"] not in CLASSIC_PLANETS:
            continue
        elements_balance[ELEMENTS[planet["sign"]]] += 1
        modality_balance[MODALITIES[planet["sign"]]] += 1

    return {
        "schema_version": SCHEMA_VERSION,
        "planets": draconic_planets,
        "angles": draconic_angles,
        "houses": draconic_houses,
        "aspects": aspects,
        "elements_balance": elements_balance,
        "modality_balance": modality_balance,
    }
