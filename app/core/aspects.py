"""Calcul des aspects entre corps célestes (thème natal)."""

from __future__ import annotations

from dataclasses import dataclass

from app.core.reference_data import aspects_reference

# nom technique -> (nom_fr, angle)
_ORB_FIELD_BY_ASPECT = {
    "conjunction": "conjunction",
    "opposition": "opposition",
    "square": "square",
    "trine": "trine",
    "sextile": "sextile",
    "semi_sextile": "semi_sextile",
    "semi_square": "semi_square",
    "sesquiquadrate": "sesquiquadrate",
    "quincunx": "quincunx",
    "quintile": "quintile",
}


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


def compute_aspects(
    bodies: list[BodyForAspect],
    orbs: dict[str, float],
    include_minor: bool = True,
) -> list[dict]:
    """Calcule tous les aspects entre chaque paire de corps de la liste."""
    results: list[dict] = []
    definitions = _aspect_definitions(include_minor)

    for i in range(len(bodies)):
        for j in range(i + 1, len(bodies)):
            b1, b2 = bodies[i], bodies[j]
            sep = angular_separation(b1.longitude, b2.longitude)

            best_match = None
            for aspect_def in definitions:
                orb_limit = orbs.get(aspect_def["name"], aspect_def["default_orb"])
                orb_value = abs(sep - aspect_def["angle"])
                if orb_value <= orb_limit:
                    if best_match is None or orb_value < best_match[1]:
                        best_match = (aspect_def, orb_value)

            if best_match is None:
                continue

            aspect_def, orb_value = best_match
            dt = 0.01  # jour, pas de temps pour estimer la direction du mouvement
            future_sep = angular_separation(
                b1.longitude + b1.speed_longitude * dt,
                b2.longitude + b2.speed_longitude * dt,
            )
            applying = abs(future_sep - aspect_def["angle"]) < orb_value

            results.append(
                {
                    "planet1": b1.name,
                    "planet2": b2.name,
                    "type": aspect_def["name"],
                    "type_fr": aspect_def["name_fr"],
                    "angle": aspect_def["angle"],
                    "orb": round(orb_value, 2),
                    "applying": applying,
                }
            )

    return results
