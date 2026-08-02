"""Calcul des aspects entre corps célestes (thème natal, transits, lots)."""

from __future__ import annotations

from dataclasses import dataclass

from app.core.reference_data import aspects_reference


def _aspect_definitions(include_minor: bool) -> list[dict]:
    ref = aspects_reference()
    defs = list(ref["major_aspects"])
    if include_minor:
        defs += list(ref["minor_aspects"])
    return defs


def angular_separation(lon1: float, lon2: float) -> float:
    """Écart angulaire circulaire entre deux longitudes, dans [0, 180]."""
    diff = abs(lon1 - lon2) % 360
    return 360 - diff if diff > 180 else diff


@dataclass
class BodyForAspect:
    name: str
    longitude: float
    speed_longitude: float = 0.0


def _match_aspect(sep: float, orbs: dict[str, float], definitions: list[dict]) -> tuple[dict, float] | None:
    """Meilleure correspondance (orbe la plus fine) parmi les définitions d'aspects, ou None."""
    best: tuple[dict, float] | None = None
    for aspect_def in definitions:
        orb_limit = orbs.get(aspect_def["name"], aspect_def["default_orb"])
        orb_value = abs(sep - aspect_def["angle"])
        if orb_value <= orb_limit and (best is None or orb_value < best[1]):
            best = (aspect_def, orb_value)
    return best


def _is_applying(b1: BodyForAspect, b2: BodyForAspect, aspect_angle: float, current_orb: float) -> bool:
    dt = 0.01  # jour, pas de temps pour estimer la direction du mouvement
    future_sep = angular_separation(
        b1.longitude + b1.speed_longitude * dt,
        b2.longitude + b2.speed_longitude * dt,
    )
    return abs(future_sep - aspect_angle) < current_orb


def compute_aspects(
    bodies: list[BodyForAspect],
    orbs: dict[str, float],
    include_minor: bool = True,
) -> list[dict]:
    """Calcule tous les aspects entre chaque paire de corps d'une même liste (thème natal)."""
    results: list[dict] = []
    definitions = _aspect_definitions(include_minor)

    for i in range(len(bodies)):
        for j in range(i + 1, len(bodies)):
            b1, b2 = bodies[i], bodies[j]
            sep = angular_separation(b1.longitude, b2.longitude)
            match = _match_aspect(sep, orbs, definitions)
            if match is None:
                continue
            aspect_def, orb_value = match
            results.append(
                {
                    "planet1": b1.name,
                    "planet2": b2.name,
                    "type": aspect_def["name"],
                    "type_fr": aspect_def["name_fr"],
                    "angle": aspect_def["angle"],
                    "orb": round(orb_value, 2),
                    "applying": _is_applying(b1, b2, aspect_def["angle"], orb_value),
                }
            )
    return results


def compute_cross_aspects(
    bodies_a: list[BodyForAspect],
    bodies_b: list[BodyForAspect],
    orbs: dict[str, float],
    include_minor: bool = True,
    include_applying: bool = True,
) -> list[dict]:
    """Aspects entre deux ensembles distincts de corps (ex. transits vs natal, lot vs natal).

    `include_applying=False` pour des comparaisons entre points fixes au même instant
    (ex. lot natal vs planète natale), où 'applicatif/séparatif' n'a pas de sens.
    """
    results: list[dict] = []
    definitions = _aspect_definitions(include_minor)

    for a in bodies_a:
        for b in bodies_b:
            sep = angular_separation(a.longitude, b.longitude)
            match = _match_aspect(sep, orbs, definitions)
            if match is None:
                continue
            aspect_def, orb_value = match
            entry = {
                "body_a": a.name,
                "body_b": b.name,
                "type": aspect_def["name"],
                "type_fr": aspect_def["name_fr"],
                "angle": aspect_def["angle"],
                "orb": round(orb_value, 2),
            }
            if include_applying:
                entry["applying"] = _is_applying(a, b, aspect_def["angle"], orb_value)
            results.append(entry)
    return results
