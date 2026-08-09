"""Calcul des lignes d'astrocartographie (MC/IC/ASC/DC) pour un ensemble de planètes.

Principe (technique classique d'astro*carto*graphie) : pour chaque planète, on trace sur une
carte du monde les lieux où cette planète est angulaire (sur l'un des 4 angles du thème local
à cet endroit) au moment de référence (naissance pour l'astrocartographie natale, instant
présent pour la cyclocartographie/transit — seule la source du jour julien change, le calcul
géométrique est identique).

Formules (astronomie sphérique standard, indépendantes de tout logiciel commercial) :
- Ligne de MC (culmination supérieure) : longitude = ascension_droite - temps_sidéral_Greenwich
- Ligne de IC (culmination inférieure) : longitude_MC + 180°
- Lignes d'ASC/DC (lever/coucher) : pour chaque latitude φ, l'angle horaire du lever/coucher
  H0 = arccos(-tan(φ) · tan(δ)) (δ = déclinaison de la planète). Angle horaire local à
  l'ASC (lever, à l'est du méridien) : H = -H0 ; au DC (coucher) : H = +H0. Temps sidéral
  local correspondant : LST = ascension_droite + H. Longitude géographique : LST - temps
  sidéral de Greenwich. Aux latitudes où |tan(φ)·tan(δ)| > 1, la planète ne se lève/couche
  jamais (circumpolaire ou toujours sous l'horizon à cette latitude) : ce point est omis.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from app.core.ephemeris import EquatorialPosition

# Planètes couvertes par la technique (voir astrocartography_significations.json,
# planet_line_meanings) — pas les nœuds/Chiron/Lilith, non documentés pour cette technique.
ASTROCARTOGRAPHY_PLANETS = [
    "Sun", "Moon", "Mercury", "Venus", "Mars",
    "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto",
]

LINE_TYPES = ("ASC", "DC", "MC", "IC")

# Un point tous les 1° de latitude est largement suffisant pour un rendu fluide (voir note
# d'implémentation du schéma SQL fourni) sans alourdir le JSON stocké.
_LATITUDE_STEP = 1.0
_LATITUDE_MAX = 85.0  # au-delà, trop proche des pôles pour un rendu cartographique utile


def _normalize_longitude(lon: float) -> float:
    """Ramène une longitude dans l'intervalle [-180, 180)."""
    return ((lon + 180) % 360) - 180


def compute_meridian_lines(equatorial: EquatorialPosition, gst_degrees: float) -> dict[str, float]:
    """Lignes de MC et IC : verticales (longitude constante), valables à toutes les latitudes."""
    mc_longitude = _normalize_longitude(equatorial.right_ascension - gst_degrees)
    ic_longitude = _normalize_longitude(mc_longitude + 180)
    return {"MC": mc_longitude, "IC": ic_longitude}


def compute_horizon_line_points(equatorial: EquatorialPosition, gst_degrees: float) -> dict[str, list[dict]]:
    """Lignes d'ASC (lever) et de DC (coucher) : courbes dépendant de la latitude."""
    asc_points: list[dict] = []
    dc_points: list[dict] = []
    dec_rad = math.radians(equatorial.declination)

    latitude = -_LATITUDE_MAX
    while latitude <= _LATITUDE_MAX + 1e-9:
        lat_rad = math.radians(latitude)
        cos_h0 = -math.tan(lat_rad) * math.tan(dec_rad)
        if -1 <= cos_h0 <= 1:
            h0 = math.degrees(math.acos(cos_h0))
            lst_asc = equatorial.right_ascension - h0
            lst_dc = equatorial.right_ascension + h0
            asc_points.append({"lat": round(latitude, 1), "lon": round(_normalize_longitude(lst_asc - gst_degrees), 3)})
            dc_points.append({"lat": round(latitude, 1), "lon": round(_normalize_longitude(lst_dc - gst_degrees), 3)})
        # latitudes circumpolaires pour cette déclinaison : pas de lever/coucher, point omis.
        latitude += _LATITUDE_STEP

    return {"ASC": asc_points, "DC": dc_points}


@dataclass
class AstrocartographyLine:
    planet: str
    line_type: str
    line_points: list[dict]


def compute_astrocartography_lines(
    equatorial_positions: dict[str, EquatorialPosition], gst_degrees: float
) -> list[AstrocartographyLine]:
    """Calcule les 4 lignes (ASC/DC/MC/IC) pour chaque planète fournie."""
    lines: list[AstrocartographyLine] = []
    for planet, equatorial in equatorial_positions.items():
        meridians = compute_meridian_lines(equatorial, gst_degrees)
        horizons = compute_horizon_line_points(equatorial, gst_degrees)

        # Lignes MC/IC stockées comme un simple segment vertical (2 points suffisent : la
        # longitude est constante quelle que soit la latitude), format cohérent avec les
        # lignes ASC/DC (liste de points lat/lon) pour un rendu carte unifié côté frontend.
        mc_lon = round(meridians["MC"], 3)
        ic_lon = round(meridians["IC"], 3)
        lines.append(
            AstrocartographyLine(
                planet=planet,
                line_type="MC",
                line_points=[{"lat": -_LATITUDE_MAX, "lon": mc_lon}, {"lat": _LATITUDE_MAX, "lon": mc_lon}],
            )
        )
        lines.append(
            AstrocartographyLine(
                planet=planet,
                line_type="IC",
                line_points=[{"lat": -_LATITUDE_MAX, "lon": ic_lon}, {"lat": _LATITUDE_MAX, "lon": ic_lon}],
            )
        )
        lines.append(AstrocartographyLine(planet=planet, line_type="ASC", line_points=horizons["ASC"]))
        lines.append(AstrocartographyLine(planet=planet, line_type="DC", line_points=horizons["DC"]))

    return lines


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r_earth_km = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return 2 * r_earth_km * math.asin(min(1.0, math.sqrt(a)))


def _closest_point_on_line(line_points: list[dict], latitude: float, longitude: float) -> tuple[float, dict] | None:
    """Point de la ligne le plus proche (distance orthodromique) du lieu donné. Les lignes
    étant échantillonnées tous les 1° de latitude, interpoler entre les deux points encadrant
    la latitude cible donne une bien meilleure précision qu'un simple point le plus proche."""
    if not line_points:
        return None
    sorted_points = sorted(line_points, key=lambda p: p["lat"])
    if latitude <= sorted_points[0]["lat"]:
        target = sorted_points[0]
    elif latitude >= sorted_points[-1]["lat"]:
        target = sorted_points[-1]
    else:
        lower = max((p for p in sorted_points if p["lat"] <= latitude), key=lambda p: p["lat"])
        upper = min((p for p in sorted_points if p["lat"] >= latitude), key=lambda p: p["lat"])
        if upper["lat"] == lower["lat"]:
            target = lower
        else:
            ratio = (latitude - lower["lat"]) / (upper["lat"] - lower["lat"])
            interpolated_lon = lower["lon"] + ratio * (upper["lon"] - lower["lon"])
            target = {"lat": latitude, "lon": interpolated_lon}
    distance = _haversine_km(latitude, longitude, target["lat"], target["lon"])
    return distance, target


def analyze_nearby_lines(
    lines: list[dict], latitude: float, longitude: float, threshold_km: float = 250.0
) -> list[dict]:
    """Pour un lieu donné, renvoie les lignes qui en passent à moins de `threshold_km`, triées
    de la plus proche à la plus éloignée. `lines` : liste de {"planet", "line_type",
    "line_points"} (calcul déterministe, aucune interprétation ici)."""
    results = []
    for line in lines:
        closest = _closest_point_on_line(line["line_points"], latitude, longitude)
        if closest is None:
            continue
        distance_km, _point = closest
        if distance_km <= threshold_km:
            results.append(
                {
                    "planet": line["planet"],
                    "line_type": line["line_type"],
                    "distance_km": round(distance_km, 1),
                }
            )
    return sorted(results, key=lambda r: r["distance_km"])
