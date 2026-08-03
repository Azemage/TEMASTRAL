from functools import lru_cache
from zoneinfo import available_timezones

from fastapi import APIRouter

from app.core.reference_data import (
    axes_thematiques_lots,
    config_reference,
    derived_house_relations,
    houses_meanings,
    lots_library,
    rulerships,
)

router = APIRouter(prefix="/api/reference", tags=["reference"])

# Préfixes d'alias historiques/techniques (ex. 'US/Eastern', 'Etc/GMT+5', 'SystemV/...')
# à exclure : ils désignent les mêmes fuseaux que leurs équivalents canoniques
# 'Continent/Ville' mais doublonnent inutilement la liste proposée à l'utilisateur.
_EXCLUDED_PREFIXES = ("Etc/", "SystemV/", "US/", "Canada/", "Brazil/", "Mexico/", "Chile/")
_EXCLUDED_EXACT = {"UCT", "GMT", "GMT0", "GMT+0", "GMT-0", "Greenwich", "Universal", "Zulu", "WET", "CET", "EET", "MET"}


@lru_cache
def _canonical_timezones() -> list[str]:
    zones = {
        tz
        for tz in available_timezones()
        if "/" in tz and not tz.startswith(_EXCLUDED_PREFIXES) and tz not in _EXCLUDED_EXACT
    }
    zones.add("UTC")
    return sorted(zones)


@router.get("/config")
def get_config():
    return config_reference()


@router.get("/houses")
def get_houses_meanings():
    return houses_meanings()


@router.get("/rulerships")
def get_rulerships():
    return rulerships()


@router.get("/lots")
def get_lots():
    return lots_library()


@router.get("/derived-house-relations")
def get_derived_house_relations():
    return derived_house_relations()


@router.get("/axes-thematiques-lots")
def get_axes_thematiques_lots():
    return axes_thematiques_lots()


@router.get("/timezones")
def get_timezones():
    return _canonical_timezones()
