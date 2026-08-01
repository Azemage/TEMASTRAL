"""Recherche de ville -> latitude/longitude/fuseau horaire.

Utilise Nominatim (OpenStreetMap) pour le géocodage et timezonefinder pour déduire le
fuseau IANA à partir des coordonnées. Nécessite un accès réseau sortant ; en cas
d'indisponibilité, le frontend permet toujours la saisie manuelle des coordonnées.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from geopy.geocoders import Nominatim
from timezonefinder import TimezoneFinder

router = APIRouter(prefix="/api/geocode", tags=["geocode"])

_geolocator = Nominatim(user_agent="temastral-natal-chart-app")
_tz_finder = TimezoneFinder()


@router.get("")
def geocode(query: str = Query(..., min_length=2)):
    try:
        locations = _geolocator.geocode(query, exactly_one=False, limit=5, language="fr")
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail="Service de géocodage indisponible. Vous pouvez saisir les coordonnées manuellement.",
        ) from exc

    if not locations:
        return []

    results = []
    for loc in locations:
        tz_name = _tz_finder.timezone_at(lat=loc.latitude, lng=loc.longitude)
        results.append(
            {
                "display_name": loc.address,
                "latitude": loc.latitude,
                "longitude": loc.longitude,
                "timezone": tz_name,
            }
        )
    return results
