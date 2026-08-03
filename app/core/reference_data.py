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


@lru_cache
def ruler_map(system: str) -> dict[str, str]:
    """sign -> planet name, pour system in {'traditional', 'modern'}."""
    key = f"{system}_ruler"
    return {entry["sign"]: entry[key] for entry in rulerships()["rulerships"]}
