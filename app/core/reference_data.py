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


@lru_cache
def ruler_map(system: str) -> dict[str, str]:
    """sign -> planet name, pour system in {'traditional', 'modern'}."""
    key = f"{system}_ruler"
    return {entry["sign"]: entry[key] for entry in rulerships()["rulerships"]}
