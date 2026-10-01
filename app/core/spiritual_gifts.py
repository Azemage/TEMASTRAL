"""Signaux déterministes de sensibilité psychique/spirituelle et de dons potentiels — voir
app/reference_data/spiritual_gifts.json pour le système à quatre dictionnaires (nature du
don, mode d'activation de l'aspect, canal d'expression par signe, aire de vie par maison) sur
lequel s'appuie l'interprétation.

Ce module se contente de repérer les signaux DOCUMENTÉS réellement présents dans un thème
donné (occupants des maisons IV/VIII/XII, aspects documentés, concentration en eau,
astéroïdes disponibles) — composer une interprétation cohérente à partir de ces signaux et
des quatre dictionnaires reste le rôle du modèle de lecture (voir interpretation_service.py),
jamais de ce module. Aucun texte interprétatif n'est généré ici, uniquement des faits
calculés."""

from __future__ import annotations

from itertools import combinations

from app.core.dispositors import CLASSIC_PLANETS
from app.core.reference_data import spiritual_gifts

KEY_HOUSES = (4, 8, 12)
NOTABLE_ASTEROIDS = ("lilith_mean", "vesta", "ceres")


def _find_water_grand_trine(aspects: list[dict], planets_by_name: dict, water_signs: set[str]) -> list[str] | None:
    """Cherche trois planètes classiques mutuellement en trigone, toutes en signe d'eau — le
    'grand trigone d'eau' cité par la source comme amplificateur marqué de n'importe quel type
    de don. Retourne la première combinaison trouvée (il est rare qu'il y en ait plusieurs),
    ou None."""
    trine_pairs = {frozenset((a["planet1"], a["planet2"])) for a in aspects if a["type"] == "trine"}
    water_classic = [
        name for name, p in planets_by_name.items() if name in CLASSIC_PLANETS and p["sign"] in water_signs
    ]
    for trio in combinations(water_classic, 3):
        if all(frozenset(pair) in trine_pairs for pair in combinations(trio, 2)):
            return list(trio)
    return None


def compute_spiritual_gifts_signals(chart_data: dict) -> dict:
    planets = chart_data["planets"]
    planets_by_name = {p["name"]: p for p in planets}
    ref = spiritual_gifts()
    water_signs = set(ref["water_signs"])
    relevant_aspect_types = set(ref["relevant_aspect_types"])
    documented_pairs = {frozenset((e["planet1"], e["planet2"])): e["gift_type"] for e in ref["documented_aspect_pairs"]}

    key_house_occupants = {house: [p["name"] for p in planets if p["house"] == house] for house in KEY_HOUSES}

    documented_aspects_present = []
    for aspect in chart_data["aspects"]:
        if aspect["type"] not in relevant_aspect_types:
            continue
        gift_type = documented_pairs.get(frozenset((aspect["planet1"], aspect["planet2"])))
        if gift_type:
            documented_aspects_present.append({**aspect, "gift_type": gift_type})

    water_sign_classic_planets = [
        p["name"] for p in planets if p["name"] in CLASSIC_PLANETS and p["sign"] in water_signs
    ]

    notable_asteroids = {
        name: {"sign": planets_by_name[name]["sign"], "house": planets_by_name[name]["house"]}
        for name in NOTABLE_ASTEROIDS
        if name in planets_by_name
    }

    south_node = planets_by_name.get("south_node")

    return {
        "key_house_occupants": key_house_occupants,
        "documented_aspects_present": documented_aspects_present,
        "water_sign_classic_planets": water_sign_classic_planets,
        "has_water_stellium": len(water_sign_classic_planets) >= 3,
        "water_grand_trine": _find_water_grand_trine(chart_data["aspects"], planets_by_name, water_signs),
        "notable_asteroids": notable_asteroids,
        "south_node_sign_house": (
            {"sign": south_node["sign"], "house": south_node["house"]} if south_node else None
        ),
    }
