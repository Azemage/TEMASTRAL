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


def line_longitude_at_latitude(
    equatorial: EquatorialPosition, gst_degrees: float, line_type: str, latitude: float
) -> float | None:
    """Longitude de la ligne demandée à UNE latitude précise, sans balayer toutes les
    latitudes — utilisé pour évaluer rapidement, à un instant donné, si une ligne passe près
    d'un lieu fixe (prévision multi-années). Renvoie None pour ASC/DC si la planète ne se
    lève/couche jamais à cette latitude ce jour-là (barrière circumpolaire)."""
    if line_type in ("MC", "IC"):
        return compute_meridian_lines(equatorial, gst_degrees)[line_type]
    if line_type not in ("ASC", "DC"):
        raise ValueError(f"Type de ligne inconnu : {line_type}")

    dec_rad = math.radians(equatorial.declination)
    lat_rad = math.radians(latitude)
    cos_h0 = -math.tan(lat_rad) * math.tan(dec_rad)
    if not (-1 <= cos_h0 <= 1):
        return None
    h0 = math.degrees(math.acos(cos_h0))
    lst = equatorial.right_ascension + (-h0 if line_type == "ASC" else h0)
    return _normalize_longitude(lst - gst_degrees)


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


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
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
    distance = haversine_km(latitude, longitude, target["lat"], target["lon"])
    return distance, target


def _constant_longitude(line_points: list[dict]) -> float | None:
    """Renvoie la longitude constante d'une ligne de MC/IC (segment vertical à 2 points),
    ou None si `line_points` est une courbe (ASC/DC)."""
    if len(line_points) == 2 and line_points[0]["lon"] == line_points[1]["lon"]:
        return line_points[0]["lon"]
    return None


def _crossings_curve_vs_constant(curve: list[dict], const_lon: float) -> list[dict]:
    points = sorted(curve, key=lambda p: p["lat"])
    crossings: list[dict] = []
    for p1, p2 in zip(points, points[1:]):
        d1 = _normalize_longitude(p1["lon"] - const_lon)
        d2 = _normalize_longitude(p2["lon"] - const_lon)
        if d1 == 0:
            crossings.append({"lat": p1["lat"], "lon": const_lon})
        elif d1 * d2 < 0 and abs(d1 - d2) < 180:
            ratio = abs(d1) / (abs(d1) + abs(d2))
            lat = p1["lat"] + ratio * (p2["lat"] - p1["lat"])
            crossings.append({"lat": round(lat, 3), "lon": round(const_lon, 3)})
    return crossings


def _crossings_curve_vs_curve(curve_a: list[dict], curve_b: list[dict]) -> list[dict]:
    lons_a = {p["lat"]: p["lon"] for p in curve_a}
    lons_b = {p["lat"]: p["lon"] for p in curve_b}
    common_lats = sorted(set(lons_a) & set(lons_b))
    crossings: list[dict] = []
    for lat1, lat2 in zip(common_lats, common_lats[1:]):
        if lat2 - lat1 > 1.5:
            # Écart de latitude anormal (barrière circumpolaire d'une des deux courbes) :
            # pas de continuité fiable entre les deux échantillons, on ignore ce segment.
            continue
        d1 = _normalize_longitude(lons_a[lat1] - lons_b[lat1])
        d2 = _normalize_longitude(lons_a[lat2] - lons_b[lat2])
        if d1 == 0:
            crossings.append({"lat": lat1, "lon": round(lons_a[lat1], 3)})
        elif d1 * d2 < 0 and abs(d1 - d2) < 180:
            ratio = abs(d1) / (abs(d1) + abs(d2))
            lat = lat1 + ratio * (lat2 - lat1)
            lon = lons_a[lat1] + ratio * (lons_a[lat2] - lons_a[lat1])
            crossings.append({"lat": round(lat, 3), "lon": round(_normalize_longitude(lon), 3)})
    return crossings


def find_line_crossings(line_a_points: list[dict], line_b_points: list[dict]) -> list[dict]:
    """Points où deux lignes (chacune une liste de points {"lat","lon"}) se croisent sur la
    carte, par interpolation linéaire entre échantillons consécutifs. Les lignes de MC/IC sont
    des segments verticaux (longitude constante) ; deux méridiennes distinctes ne se croisent
    donc jamais à une longitude finie (cas ignoré)."""
    const_a = _constant_longitude(line_a_points)
    const_b = _constant_longitude(line_b_points)
    if const_a is not None and const_b is not None:
        return []
    if const_a is not None:
        return _crossings_curve_vs_constant(line_b_points, const_a)
    if const_b is not None:
        return _crossings_curve_vs_constant(line_a_points, const_b)
    return _crossings_curve_vs_curve(line_a_points, line_b_points)


def compute_all_crossings(lines: list[dict]) -> list[dict]:
    """Croisements entre lignes de planètes DIFFÉRENTES (approximation cartographique des
    parans — voir `advanced_technique_parans` dans les significations : un croisement entre
    les lignes de deux planètes distinctes marque un lieu où leurs deux thèmes symboliques se
    combinent). Les croisements entre lignes d'une même planète (ex. son ASC et son DC) ne sont
    pas des parans et sont exclus. `lines` : liste de {"planet", "line_type", "line_points"}."""
    crossings: list[dict] = []
    for i in range(len(lines)):
        for j in range(i + 1, len(lines)):
            line_a, line_b = lines[i], lines[j]
            if line_a["planet"] == line_b["planet"]:
                continue
            for point in find_line_crossings(line_a["line_points"], line_b["line_points"]):
                crossings.append(
                    {
                        "lat": point["lat"],
                        "lon": point["lon"],
                        "planet_a": line_a["planet"],
                        "line_type_a": line_a["line_type"],
                        "planet_b": line_b["planet"],
                        "line_type_b": line_b["line_type"],
                    }
                )
    return crossings


def find_interesting_cities(
    lines: list[dict],
    crossings: list[dict],
    cities: list[dict],
    threshold_km: float = 300.0,
    top_n: int = 12,
) -> list[dict]:
    """Classe un ensemble de villes candidates par intérêt astrocartographique : une ville est
    d'autant plus intéressante qu'elle est proche de plusieurs lignes planétaires et, surtout,
    proche d'un croisement de lignes (paran approximatif — combinaison de deux thèmes
    planétaires). Score déterministe et relatif (sert au tri, pas à une lecture absolue) :
    chaque ligne/croisement à proximité contribue selon sa distance (plus proche = plus de
    poids), les croisements comptant double par rapport à une simple ligne."""
    scored: list[dict] = []
    for city in cities:
        nearby_lines = analyze_nearby_lines(lines, city["lat"], city["lon"], threshold_km)
        nearby_crossings = []
        for crossing in crossings:
            distance_km = haversine_km(city["lat"], city["lon"], crossing["lat"], crossing["lon"])
            if distance_km <= threshold_km:
                nearby_crossings.append({**crossing, "distance_km": round(distance_km, 1)})
        nearby_crossings.sort(key=lambda c: c["distance_km"])

        if not nearby_lines and not nearby_crossings:
            continue

        line_score = sum(1 - match["distance_km"] / threshold_km for match in nearby_lines)
        crossing_score = sum(2 * (1 - c["distance_km"] / threshold_km) for c in nearby_crossings)
        scored.append(
            {
                "name": city["name"],
                "country": city["country"],
                "latitude": city["lat"],
                "longitude": city["lon"],
                "score": round(line_score + crossing_score, 2),
                "nearby_lines": nearby_lines,
                "nearby_crossings": nearby_crossings,
            }
        )

    scored.sort(key=lambda c: c["score"], reverse=True)
    return scored[:top_n]


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
