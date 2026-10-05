"""Décans : chaque signe (30°) divisé en trois tranches de 10°, chacune régie par une planète
classique selon le système chaldéen — voir app/reference_data/decans.json pour la table complète
et son statut épistémique. Indépendant du système de maisons : un décan qualifie la position
d'un point dans SON SIGNE, jamais une maison en particulier."""

from __future__ import annotations

from app.core.reference_data import decans as decans_reference


def decan_number(degree_in_sign: float) -> int:
    """Numéro du décan (1, 2 ou 3) pour un degré dans le signe (0 <= x < 30)."""
    return min(int(degree_in_sign // 10), 2) + 1


def decan_ruler(sign: str, degree_in_sign: float) -> str:
    return decans_reference()["decan_rulers_by_sign"][sign][decan_number(degree_in_sign) - 1]


def analyze_decan(sign: str, degree_in_sign: float) -> dict:
    number = decan_number(degree_in_sign)
    return {"decan_number": number, "decan_ruler": decans_reference()["decan_rulers_by_sign"][sign][number - 1]}


def decan_breakdown_for_sign(sign: str) -> list[dict]:
    """Les trois décans d'UN signe entier (indépendant de toute position réelle) — utile pour
    afficher la structure complète d'un signe, par exemple pour une maison de signe intégral
    (whole sign) qui couvre exactement les 30° du signe."""
    rulers = decans_reference()["decan_rulers_by_sign"][sign]
    return [
        {"decan_number": i + 1, "ruler": ruler, "start_degree": i * 10, "end_degree": (i + 1) * 10}
        for i, ruler in enumerate(rulers)
    ]
