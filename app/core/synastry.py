"""Compatibilité entre deux thèmes natals (synastrie) : trois techniques complémentaires.

1. Inter-aspects : aspects entre les planètes du thème A et celles du thème B (jamais entre
   planètes d'un même thème), annotés du poids ('très fort'/'fort'/'moyen'/'faible') des
   couples de significateurs pertinents pour le mode de relation choisi.
2. Chevauchement de maisons : dans quelle maison de A tombe chaque planète de B (et
   réciproquement) — montre DANS QUELLE SPHÈRE DE VIE l'autre s'insère structurellement.
3. Thème composite : un thème unique représentant la relation elle-même, calculé par point
   médian de chaque paire de planètes homologues.

Voir app/reference_data/synastry_compatibility.json pour la table de référence (couples de
significateurs et maisons clés par mode de relation) et son document source.

Comme le reste du calcul astrologique de l'app, cette pondération est déterministe et ne
constitue jamais un score de compatibilité en pourcentage — elle sert uniquement à prioriser
ce que la lecture LLM développera en premier.
"""

from __future__ import annotations

from functools import lru_cache

from app.core.aspects import BodyForAspect, compute_cross_aspects
from app.core.chart_calculator import find_house
from app.core.reference_data import synastry_compatibility
from app.core.zodiac import SIGNS_FR, sign_and_degree

SUPPORTED_RELATIONSHIP_MODES = {"romantic", "friendship", "professional"}

PERSONAL_PLANETS = {"Sun", "Moon", "Mercury", "Venus", "Mars"}
NODE_POINTS = {"north_node", "south_node"}

DEFAULT_SYNASTRY_MAJOR_ORB = 4.0
_MAJOR_ASPECT_NAMES = ["conjunction", "opposition", "square", "trine", "sextile"]

COMPOSITE_PLANETS = ["Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto"]

_WEIGHT_ORDER = ["très fort", "fort", "moyen", "faible"]


def _weight_rank(label: str) -> int:
    """Classe un libellé de poids ('très fort', 'fort (symbolique)', ...) du plus prioritaire
    (0) au moins prioritaire, en cherchant la sous-chaîne la plus spécifique d'abord."""
    for rank, level in enumerate(_WEIGHT_ORDER):
        if level in label:
            return rank
    return len(_WEIGHT_ORDER)


def _expand_pair_token(token: str) -> set[str]:
    if token == "personal_planets":
        return set(PERSONAL_PLANETS)
    if token == "Nodes":
        return set(NODE_POINTS)
    return {token}


@lru_cache
def _pair_weight_lookup(mode: str) -> dict[frozenset, list[dict]]:
    """{frozenset des deux planètes} -> liste des règles de significateurs qui s'y appliquent
    pour ce mode (peut en contenir plusieurs : une règle générique type 'Saturn-personal_planets'
    et une règle plus spécifique type 'Mars-Saturn' peuvent toutes deux couvrir le même couple,
    avec des poids et significations différents — on les garde toutes)."""
    rules = synastry_compatibility()["technique_1_inter_aspects"]["significator_pairs_by_mode"].get(mode, [])
    lookup: dict[frozenset, list[dict]] = {}
    for rule in rules:
        left, right = rule["pair"].split("-", 1)
        for planet_l in _expand_pair_token(left):
            for planet_r in _expand_pair_token(right):
                key = frozenset({planet_l, planet_r})
                lookup.setdefault(key, []).append(rule)
    return lookup


def compute_inter_aspects(
    chart_a_data: dict,
    chart_b_data: dict,
    mode: str,
    orb: float = DEFAULT_SYNASTRY_MAJOR_ORB,
) -> list[dict]:
    bodies_a = [BodyForAspect(name=p["name"], longitude=p["absolute_longitude"]) for p in chart_a_data["planets"]]
    bodies_b = [BodyForAspect(name=p["name"], longitude=p["absolute_longitude"]) for p in chart_b_data["planets"]]

    orbs = dict.fromkeys(_MAJOR_ASPECT_NAMES, orb)
    # include_applying=False : les deux thèmes sont figés chacun à leur propre instant de
    # naissance, il n'y a pas de 'maintenant' commun par rapport auquel juger applicatif/séparatif.
    raw_aspects = compute_cross_aspects(bodies_a, bodies_b, orbs, include_minor=True, include_applying=False)

    weight_lookup = _pair_weight_lookup(mode)
    results = []
    for a in raw_aspects:
        matches = weight_lookup.get(frozenset({a["body_a"], a["body_b"]}), [])
        results.append(
            {
                "planet_a": a["body_a"],
                "planet_b": a["body_b"],
                "type": a["type"],
                "type_fr": a["type_fr"],
                "orb": a["orb"],
                "significator_matches": [{"weight": m["weight"], "meaning": m["meaning"]} for m in matches],
            }
        )

    def _sort_key(entry: dict) -> tuple[int, float]:
        best = min((_weight_rank(m["weight"]) for m in entry["significator_matches"]), default=len(_WEIGHT_ORDER))
        return (best, entry["orb"])

    results.sort(key=_sort_key)
    return results


def compute_house_overlay(chart_a_data: dict, chart_b_data: dict, mode: str) -> dict:
    cusps_a = [h["absolute_longitude"] for h in sorted(chart_a_data["houses"], key=lambda h: h["number"])]
    cusps_b = [h["absolute_longitude"] for h in sorted(chart_b_data["houses"], key=lambda h: h["number"])]

    key_placements = synastry_compatibility()["technique_2_house_overlay"]["key_placements_by_mode"].get(mode, {})
    meaning_by_house = {int(key.split("_")[1]): meaning for key, meaning in key_placements.items()}

    def _overlay(source_planets: list[dict], target_cusps: list[float]) -> list[dict]:
        entries = []
        for p in source_planets:
            house = find_house(p["absolute_longitude"], target_cusps)
            entries.append({"planet": p["name"], "house": house, "key_meaning": meaning_by_house.get(house)})
        return entries

    return {
        "a_planets_in_b_houses": _overlay(chart_a_data["planets"], cusps_b),
        "b_planets_in_a_houses": _overlay(chart_b_data["planets"], cusps_a),
    }


def _midpoint_longitude(lon1: float, lon2: float) -> float:
    """Point médian du plus petit arc entre deux longitudes écliptiques (méthode standard du
    thème composite). En cas d'opposition exacte (180°), les deux arcs sont équivalents ; on
    retient conventionnellement celui qui avance dans le sens direct du zodiaque depuis lon1."""
    diff = (lon2 - lon1) % 360
    if diff > 180:
        diff -= 360
    return (lon1 + diff / 2) % 360


def _composite_point(longitude: float) -> dict:
    sign, degree = sign_and_degree(longitude)
    return {
        "sign": sign,
        "sign_fr": SIGNS_FR[sign],
        "degree": round(degree, 2),
        "absolute_longitude": round(longitude, 4),
    }


def compute_composite_chart(chart_a_data: dict, chart_b_data: dict) -> dict:
    planets_a = {p["name"]: p["absolute_longitude"] for p in chart_a_data["planets"]}
    planets_b = {p["name"]: p["absolute_longitude"] for p in chart_b_data["planets"]}

    points = {
        name: _composite_point(_midpoint_longitude(planets_a[name], planets_b[name]))
        for name in COMPOSITE_PLANETS
        if name in planets_a and name in planets_b
    }

    ascendant_longitude = _midpoint_longitude(
        chart_a_data["angles"]["ascendant"]["absolute_longitude"],
        chart_b_data["angles"]["ascendant"]["absolute_longitude"],
    )

    return {
        "points": points,
        "ascendant": _composite_point(ascendant_longitude),
        "method": "midpoint_composite_ascendant",
    }


def compute_synastry(chart_a_data: dict, chart_b_data: dict, mode: str) -> dict:
    if mode not in SUPPORTED_RELATIONSHIP_MODES:
        raise ValueError(
            f"Mode de relation non pris en charge : {mode!r}. Modes disponibles : {sorted(SUPPORTED_RELATIONSHIP_MODES)}."
        )

    return {
        "relationship_mode": mode,
        "inter_aspects": compute_inter_aspects(chart_a_data, chart_b_data, mode),
        "house_overlay": compute_house_overlay(chart_a_data, chart_b_data, mode),
        "composite_chart": compute_composite_chart(chart_a_data, chart_b_data),
        "charts_time_known": {
            "chart_a": chart_a_data.get("time_known", True),
            "chart_b": chart_b_data.get("time_known", True),
        },
    }
