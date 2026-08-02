"""Calcul des lots (parts arabes/hermétiques) à partir des formules de lots.json.

Chaque formule (ex. "ASC + Moon - Sun") est évaluée à partir d'un dictionnaire de
points déjà calculés (angles, planètes, cuspides de maisons). Les lots fondamentaux
(Fortune, Esprit) sont calculés en premier car d'autres lots en dépendent.
"""

from __future__ import annotations

import re

from app.core.aspects import BodyForAspect, compute_cross_aspects
from app.core.reference_data import lots_library
from app.core.zodiac import SIGNS_FR, sign_and_degree

_TOKEN_RE = re.compile(r"([+-]?)\s*([A-Za-z0-9_]+)")
_HOUSE_CUSP_TOKEN_RE = re.compile(r"^(\d+)(?:st|nd|rd|th)_house_cusp$")

_FUNDAMENTAL_LOT_TOKENS = {
    "Lot de Fortune": "Lot_Fortune",
    "Lot d'Esprit": "Lot_Esprit",
}


class UnknownLotPointError(KeyError):
    pass


def _resolve_token(token: str, points: dict[str, float]) -> float:
    if token in points:
        return points[token]
    match = _HOUSE_CUSP_TOKEN_RE.match(token)
    if match:
        key = f"house_cusp_{match.group(1)}"
        if key in points:
            return points[key]
    raise UnknownLotPointError(f"Point inconnu dans une formule de lot : '{token}'")


def _evaluate_formula(formula: str, points: dict[str, float]) -> float:
    total = 0.0
    for sign, token in _TOKEN_RE.findall(formula):
        value = _resolve_token(token, points)
        total += value if sign != "-" else -value
    return total % 360


def compute_lots(
    points: dict[str, float],
    is_day_chart: bool,
    find_house_fn,
    natal_bodies: list[BodyForAspect] | None = None,
    aspect_orbs: dict[str, float] | None = None,
) -> list[dict]:
    """points : dictionnaire de longitudes déjà calculées (ASC, MC, Descendant, planètes,
    house_cusp_1..12). find_house_fn : fonction(longitude) -> numéro de maison natale.
    natal_bodies : planètes natales pour calculer les aspects de chaque lot vers le thème.
    """
    library = lots_library()["lots"]
    ordered = [lot for lot in library if lot["name"] in _FUNDAMENTAL_LOT_TOKENS] + [
        lot for lot in library if lot["name"] not in _FUNDAMENTAL_LOT_TOKENS
    ]

    working_points = dict(points)
    natal_bodies = natal_bodies or []
    orbs = aspect_orbs or {}

    results = []
    for lot in ordered:
        formula = lot["day_formula"] if is_day_chart else lot["night_formula"]
        longitude = _evaluate_formula(formula, working_points)
        sign, degree = sign_and_degree(longitude)

        token = _FUNDAMENTAL_LOT_TOKENS.get(lot["name"])
        if token:
            working_points[token] = longitude

        lot_body = BodyForAspect(name=lot["name"], longitude=longitude)
        aspects_to_natal = compute_cross_aspects(
            [lot_body], natal_bodies, orbs, include_minor=False, include_applying=False
        )

        results.append(
            {
                "name": lot["name"],
                "name_en": lot["name_en"],
                "category": lot["category"],
                "signification": lot["signification"],
                "formula_used": formula,
                "sign": sign,
                "sign_fr": SIGNS_FR[sign],
                "degree": round(degree, 2),
                "absolute_longitude": round(longitude, 4),
                "house": find_house_fn(longitude),
                "aspects_to_natal": [
                    {"planet": a["body_b"], "type": a["type"], "type_fr": a["type_fr"], "orb": a["orb"]}
                    for a in aspects_to_natal
                ],
            }
        )

    return results
