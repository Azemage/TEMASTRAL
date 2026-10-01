"""Classification angulaire/succédente/cadente des maisons (kentra/epanaphora/apoklima,
tradition hellénistique systématisée par William Lilly), pondérée par un poids PAR PLANÈTE
(`planet_weight` — préférence personnelle de l'utilisateur de cette app, remplace le barème
historique de dignité accidentelle de Lilly par maison, conservé dans la donnée de référence à
titre documentaire uniquement) pour déterminer la modalité dominante d'une carte — voir
app/reference_data/house_modality.json pour le statut épistémique détaillé de chaque couche, à
toujours répercuter dans toute lecture. `compute_quadrant_loads` regroupe en plus les maisons en
quatre blocs centrés sur chaque angle et identifie le(s) bloc(s) le(s) plus chargé(s) en
planètes, pour enrichir la lecture interprétée.

Ne couvre PAS les modificateurs additionnels documentés par Lilly (mouvement direct/rétrograde,
vitesse, phase lunaire, combustion/cazimi — section 3.2 de la source) : volontairement hors
scope initial, chaque planète n'étant notée ici que par sa maison."""

from __future__ import annotations

from app.core.dispositors import CLASSIC_PLANETS
from app.core.reference_data import house_modality as house_modality_reference

MODALITIES = ["angular", "succedent", "cadent"]


def classify_house(house_number: int) -> str:
    return house_modality_reference()["modality_by_house"][str(house_number)]


def planet_weight_for(planet_name: str) -> int:
    """Poids d'une planète (Soleil/Lune=4, Mercure/Vénus/Mars=3, Jupiter/Saturne=2,
    Uranus/Neptune/Pluton=1) — voir `planet_weight_note` dans la donnée de référence. 0 pour
    une planète absente de la table (ex. un astéroïde)."""
    return house_modality_reference()["planet_weight"].get(planet_name, 0)


def compute_house_modality_analysis(planets: list[dict], planet_names: list[str] | None = None) -> dict:
    """`planets` : la liste `chart_data["planets"]` (chaque élément a au moins `name`/`house`).
    `planet_names` : sous-ensemble à inclure (par défaut les 10 planètes classiques Soleil-
    Pluton, cohérent avec elements_balance/modality_balance ailleurs dans l'app)."""
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
        points = planet_weight_for(planet["name"])
        counts[modality] += 1
        weighted[modality] += points
        per_planet.append({"planet": planet["name"], "house": house, "modality": modality, "points": points})

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


def compute_quadrant_loads(planets: list[dict], planet_names: list[str] | None = None) -> list[dict]:
    """Regroupe les maisons en quatre blocs de trois maisons centrés sur chaque angle
    (Identité 12-1-2, Racines 3-4-5, Relations 6-7-8, Vie publique 9-10-11 — non vérifié dans
    une source classique, voir le statut épistémique dans la donnée de référence), puis charge
    chaque bloc des planètes classiques qui l'occupent pour repérer les zones de concentration
    de la carte. `is_most_loaded` marque le ou les blocs à `planet_count` maximal (égalité
    possible, jamais forcée sur un seul bloc)."""
    include = set(planet_names or CLASSIC_PLANETS)
    groups_ref = house_modality_reference()["quadrant_groups"]["groups"]

    planets_by_house: dict[int, list[str]] = {}
    for planet in planets:
        if planet["name"] not in include:
            continue
        planets_by_house.setdefault(planet["house"], []).append(planet["name"])

    groups = []
    for key, group in groups_ref.items():
        planets_in_group = [name for house in group["houses"] for name in planets_by_house.get(house, [])]
        groups.append(
            {
                "key": key,
                "theme": group["theme"],
                "houses": group["houses"],
                "planets": planets_in_group,
                "planet_count": len(planets_in_group),
            }
        )

    max_count = max((g["planet_count"] for g in groups), default=0)
    for g in groups:
        g["is_most_loaded"] = max_count > 0 and g["planet_count"] == max_count

    return sorted(groups, key=lambda g: -g["planet_count"])
