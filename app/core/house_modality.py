"""Classification angulaire/succédente/cadente des maisons (kentra/epanaphora/apoklima,
tradition hellénistique systématisée par William Lilly), points de dignité accidentelle de
Lilly par maison, et modalité dominante d'une carte (synthèse raisonnée : Lilly utilisait ces
points planète par planète pour une question horaire ponctuelle, pas pour une tendance générale
de toute la carte — voir app/reference_data/house_modality.json pour le statut épistémique
détaillé de chaque couche, à toujours répercuter dans toute lecture).

Ne couvre PAS les modificateurs additionnels documentés par Lilly (mouvement direct/rétrograde,
vitesse, phase lunaire, combustion/cazimi — section 3.2 de la source) : volontairement hors
scope initial, chaque planète n'étant notée ici que par sa maison."""

from __future__ import annotations

from app.core.dispositors import CLASSIC_PLANETS
from app.core.reference_data import house_modality as house_modality_reference

MODALITIES = ["angular", "succedent", "cadent"]


def classify_house(house_number: int) -> str:
    return house_modality_reference()["modality_by_house"][str(house_number)]


def lilly_points_for_house(house_number: int) -> int:
    return house_modality_reference()["lilly_dignity_points_by_house"][str(house_number)]


def compute_house_modality_analysis(planets: list[dict], planet_names: list[str] | None = None) -> dict:
    """`planets` : la liste `chart_data["planets"]` (chaque élément a au moins `name`/`house`).
    `planet_names` : sous-ensemble à inclure (par défaut les 10 planètes classiques Soleil-
    Pluton, cohérent avec elements_balance/modality_balance ailleurs dans l'app — la source
    parle des '7 planètes classiques ou celles que gère votre app')."""
    include = set(planet_names or CLASSIC_PLANETS)
    ref = house_modality_reference()

    per_planet = []
    counts = {m: 0 for m in MODALITIES}
    weighted = {m: 0 for m in MODALITIES}

    for planet in planets:
        if planet["name"] not in include:
            continue
        house = planet["house"]
        modality = classify_house(house)
        points = lilly_points_for_house(house)
        counts[modality] += 1
        weighted[modality] += points
        per_planet.append({"planet": planet["name"], "house": house, "modality": modality, "lilly_points": points})

    dominant_simple = max(MODALITIES, key=lambda m: counts[m])
    dominant_weighted = max(MODALITIES, key=lambda m: weighted[m])

    return {
        "per_planet": per_planet,
        "counts_by_modality": counts,
        "weighted_score_by_modality": weighted,
        "dominant_modality_simple": dominant_simple,
        "dominant_modality_weighted": dominant_weighted,
        "reading": ref["dominant_modality_reading"][dominant_weighted],
        "methodological_note": ref["dominant_modality_methodological_note"],
    }


def _group_by_quadrants(groups_ref: dict) -> list[dict]:
    return [{"key": key, "theme": group["theme"], "houses": group["houses"]} for key, group in groups_ref.items()]


def group_houses_by_standard_quadrant() -> list[dict]:
    """Découpage documenté, commence à chaque angle (1-2-3, 4-5-6, 7-8-9, 10-11-12)."""
    return _group_by_quadrants(house_modality_reference()["quadrant_groupings"]["standard"]["groups"])


def group_houses_by_angle_centered_quadrant() -> list[dict]:
    """Découpage alternatif, chaque angle au centre de son bloc (12-1-2, 3-4-5, 6-7-8, 9-10-11)
    — non vérifié dans une source classique, voir le statut épistémique dans la donnée de
    référence, toujours à présenter comme variante non confirmée."""
    return _group_by_quadrants(house_modality_reference()["quadrant_groupings"]["angle_centered"]["groups"])
