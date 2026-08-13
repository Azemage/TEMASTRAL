"""Chargement en mémoire des tables de référence JSON (app/reference_data/)."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

REFERENCE_DIR = Path(__file__).resolve().parent.parent / "reference_data"


@lru_cache
def _load(filename: str) -> dict:
    with open(REFERENCE_DIR / filename, encoding="utf-8") as f:
        return json.load(f)


def rulerships() -> dict:
    return _load("rulerships.json")


def dignities() -> dict:
    return _load("dignities.json")


def aspects_reference() -> dict:
    return _load("aspects.json")


def houses_meanings() -> dict:
    return _load("houses_meanings.json")


def lots_library() -> dict:
    return _load("lots.json")


def config_reference() -> dict:
    return _load("config_reference.json")


def character_traits() -> dict:
    return _load("character_traits.json")


def lot_timing_rules() -> dict:
    return _load("lot_timing_rules.json")


def zodiacal_releasing_algorithm() -> dict:
    return _load("zodiacal_releasing_algorithm.json")


def identity_trait_tags() -> dict:
    return _load("identity_trait_tags.json")


def identity_traits() -> dict:
    return _load("identity_traits.json")


def planets_in_signs_full() -> dict:
    return _load("planets_in_signs_full.json")


def planets_in_houses_full() -> dict:
    return _load("planets_in_houses_full.json")


def synastry_compatibility() -> dict:
    return _load("synastry_compatibility.json")


def derived_house_relations() -> dict:
    return _load("derived_house_relations.json")


def axes_thematiques_lots() -> dict:
    return _load("axes_thematiques_lots.json")


def astrocartography_significations() -> dict:
    return _load("astrocartography_significations.json")


def witchy_calendar_events() -> dict:
    """Catalogue d'événements du calendrier ésotérique annuel (poids, gabarits de sens,
    formule de score) — voir app/core/witchy_calendar.py pour le calcul déterministe des
    dates et app/services/interpretation_service.py pour la mise en mots par le LLM."""
    return _load("witchy_calendar_events.json")


def world_cities() -> list[dict]:
    """Grandes villes mondiales (Natural Earth 110m populated places, domaine public) —
    capitales et métropoles majeures, utilisées comme bassin de candidats pour la suggestion
    de villes intéressantes en astrocartographie."""
    return _load("world_cities.json")


@lru_cache
def ruler_map(system: str) -> dict[str, str]:
    """sign -> planet name, pour system in {'traditional', 'modern'}."""
    key = f"{system}_ruler"
    return {entry["sign"]: entry[key] for entry in rulerships()["rulerships"]}
