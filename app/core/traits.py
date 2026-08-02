"""Résumé rapide et déterministe des traits de caractère (Soleil, Lune, Ascendant,
élément et modalité dominants). Complémentaire à la lecture rédigée par le LLM : une
liste de mots-clés lisible en un coup d'œil, avant d'entrer dans le détail."""

from __future__ import annotations

from app.core.reference_data import character_traits

ELEMENT_PRIORITY = ["fire", "earth", "air", "water"]
MODALITY_PRIORITY = ["cardinal", "fixed", "mutable"]


def _dominant(balance: dict[str, int], priority: list[str]) -> str:
    """Élément/modalité au score le plus élevé. En cas d'égalité, l'ordre de `priority`
    départage de façon déterministe plutôt que selon l'ordre arbitraire du dict."""
    return max(priority, key=lambda key: balance[key])


def compute_character_traits(
    sun_sign: str,
    moon_sign: str,
    ascendant_sign: str,
    elements_balance: dict[str, int],
    modality_balance: dict[str, int],
) -> dict:
    data = character_traits()
    dominant_element = _dominant(elements_balance, ELEMENT_PRIORITY)
    dominant_modality = _dominant(modality_balance, MODALITY_PRIORITY)

    sources = [
        {"origin": "sun", "label": sun_sign, "traits": data["signs"][sun_sign][:2]},
        {"origin": "moon", "label": moon_sign, "traits": data["signs"][moon_sign][:2]},
        {"origin": "ascendant", "label": ascendant_sign, "traits": data["signs"][ascendant_sign][:2]},
        {"origin": "dominant_element", "label": dominant_element, "traits": data["elements"][dominant_element][:1]},
        {"origin": "dominant_modality", "label": dominant_modality, "traits": data["modalities"][dominant_modality][:1]},
    ]

    keywords: list[str] = []
    for source in sources:
        for trait in source["traits"]:
            if trait not in keywords:
                keywords.append(trait)

    return {"keywords": keywords, "sources": sources}
