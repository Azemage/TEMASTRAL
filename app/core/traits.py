"""Résumé rapide et déterministe des traits de caractère, en coup d'œil avant la lecture
rédigée par le LLM. Combine planète + signe + maison :
- planètes personnelles (Soleil, Lune, Ascendant, Mercure, Vénus, Mars) : tags de
  personnalité par signe (`identity_trait_tags.json`), contextualisés par la maison occupée
  (sphère de vie où le trait domine).
- planètes sociales (Jupiter, Saturne) : mêmes principe, à partir des mots-clés de
  `planets_in_signs_full.json` (pas de tags dédiés dans identity_trait_tags.json).
- planètes générationnelles (Uranus, Neptune, Pluton) : leur signe seul ne caractérise pas
  l'individu (partagé par toute une tranche d'âge) — on ne les mélange donc pas au nuage de
  tags. Seule leur maison individualise : elles apparaissent séparément dans
  `generational_placements`, avec la phrase de `planets_in_houses_full.json`.

Les tags qui reviennent depuis au moins deux sources différentes sont signalés comme traits
dominants (`dominant_traits`), à mettre en avant en priorité.
"""

from __future__ import annotations

from collections import Counter

from app.core.reference_data import character_traits, identity_trait_tags, planets_in_houses_full, planets_in_signs_full

ELEMENT_PRIORITY = ["fire", "earth", "air", "water"]
MODALITY_PRIORITY = ["cardinal", "fixed", "mutable"]

PERSONAL_TAGGED_PLANETS = ["Sun", "Moon", "Mercury", "Venus", "Mars"]
SOCIAL_PLANETS = ["Jupiter", "Saturn"]
GENERATIONAL_PLANETS = ["Uranus", "Neptune", "Pluto"]


def _dominant(balance: dict[str, int], priority: list[str]) -> str:
    """Élément/modalité au score le plus élevé. En cas d'égalité, l'ordre de `priority`
    départage de façon déterministe plutôt que selon l'ordre arbitraire du dict."""
    return max(priority, key=lambda key: balance[key])


def _source(origin: str, label: str, traits: list[str], house: int | None, house_context_tags: dict[str, str]) -> dict:
    return {
        "origin": origin,
        "label": label,
        "house": house,
        "house_context": house_context_tags.get(str(house)) if house else None,
        "traits": traits,
    }


def compute_character_traits(
    planets: list[dict],
    ascendant_sign: str,
    elements_balance: dict[str, int],
    modality_balance: dict[str, int],
) -> dict:
    planet_by_name = {p["name"]: p for p in planets}
    tag_data = identity_trait_tags()
    tags_by_planet_sign = tag_data["tags_by_planet_sign"]
    house_context_tags = tag_data["house_context_tags"]["tags"]
    signs_full = planets_in_signs_full()
    houses_full = planets_in_houses_full()
    base_traits = character_traits()

    sources = [_source("ascendant", ascendant_sign, tags_by_planet_sign["Ascendant"][ascendant_sign], None, house_context_tags)]

    for planet_name in PERSONAL_TAGGED_PLANETS:
        p = planet_by_name[planet_name]
        traits = tags_by_planet_sign[planet_name][p["sign"]]
        sources.append(_source(planet_name.lower(), p["sign"], traits, p["house"], house_context_tags))

    for planet_name in SOCIAL_PLANETS:
        p = planet_by_name[planet_name]
        traits = signs_full[planet_name][p["sign"]]["keywords"]
        sources.append(_source(planet_name.lower(), p["sign"], traits, p["house"], house_context_tags))

    dominant_element = _dominant(elements_balance, ELEMENT_PRIORITY)
    dominant_modality = _dominant(modality_balance, MODALITY_PRIORITY)
    sources.append(_source("dominant_element", dominant_element, base_traits["elements"][dominant_element][:1], None, house_context_tags))
    sources.append(_source("dominant_modality", dominant_modality, base_traits["modalities"][dominant_modality][:1], None, house_context_tags))

    tag_counts = Counter(trait for source in sources for trait in source["traits"])
    dominant_traits: list[str] = []
    for source in sources:
        for trait in source["traits"]:
            if tag_counts[trait] >= 2 and trait not in dominant_traits:
                dominant_traits.append(trait)

    keywords: list[str] = []
    for source in sources:
        for trait in source["traits"]:
            if trait not in keywords:
                keywords.append(trait)

    generational_placements = []
    for planet_name in GENERATIONAL_PLANETS:
        p = planet_by_name[planet_name]
        generational_placements.append(
            {
                "planet": planet_name,
                "sign": p["sign"],
                "sign_fr": p["sign_fr"],
                "house": p["house"],
                "note": houses_full[planet_name][str(p["house"])],
            }
        )

    return {
        "keywords": keywords,
        "dominant_traits": dominant_traits,
        "sources": sources,
        "generational_placements": generational_placements,
    }
