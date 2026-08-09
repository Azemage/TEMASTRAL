"""Wrapper autour de pyswisseph : conversion temporelle et positions astronomiques brutes.

Utilise l'algorithme Moshier (SEFLG_MOSEPH), intégré à pyswisseph, qui ne nécessite
aucun fichier d'éphémérides externe et reste précis à la seconde d'arc près sur la
période couverte par les naissances humaines. Si des fichiers Swiss Ephemeris (.se1)
sont installés (voir SE_EPHE_PATH), ils peuvent être activés en remplaçant
CALC_FLAGS par swe.FLG_SWIEPH | swe.FLG_SPEED pour une précision encore supérieure.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

import swisseph as swe

CALC_FLAGS = swe.FLG_MOSEPH | swe.FLG_SPEED

PLANET_IDS: dict[str, int] = {
    "Sun": swe.SUN,
    "Moon": swe.MOON,
    "Mercury": swe.MERCURY,
    "Venus": swe.VENUS,
    "Mars": swe.MARS,
    "Jupiter": swe.JUPITER,
    "Saturn": swe.SATURN,
    "Uranus": swe.URANUS,
    "Neptune": swe.NEPTUNE,
    "Pluto": swe.PLUTO,
    "chiron": swe.CHIRON,
    "lilith_mean": swe.MEAN_APOG,
}

# Le nœud sud n'a pas d'identifiant swisseph direct : il est l'opposé du nœud nord.
NORTH_NODE_ID = swe.MEAN_NODE

HOUSE_SYSTEM_CODES: dict[str, bytes] = {
    "placidus": b"P",
    "koch": b"K",
    "equal": b"E",
    "whole_sign": b"W",
    "regiomontanus": b"R",
}


class InvalidBirthDataError(ValueError):
    pass


def local_datetime_to_jd_ut(date_str: str, time_str: str, tz_name: str) -> float:
    """Convertit une date/heure locale de naissance (avec fuseau IANA) en jour julien UT."""
    try:
        dt_naive = datetime.fromisoformat(f"{date_str}T{time_str}")
    except ValueError as exc:
        raise InvalidBirthDataError(f"Date/heure invalide : {date_str} {time_str}") from exc

    try:
        tz = ZoneInfo(tz_name)
    except Exception as exc:
        raise InvalidBirthDataError(f"Fuseau horaire inconnu : {tz_name}") from exc

    dt_local = dt_naive.replace(tzinfo=tz)
    dt_utc = dt_local.astimezone(ZoneInfo("UTC"))
    hour_decimal = dt_utc.hour + dt_utc.minute / 60 + dt_utc.second / 3600
    return swe.julday(dt_utc.year, dt_utc.month, dt_utc.day, hour_decimal)


@dataclass
class RawPlanetPosition:
    longitude: float
    latitude: float
    distance: float
    speed_longitude: float

    @property
    def retrograde(self) -> bool:
        return self.speed_longitude < 0


def calc_planet(jd_ut: float, planet_id: int) -> RawPlanetPosition:
    (lon, lat, dist, speed_lon, _speed_lat, _speed_dist), _flag = swe.calc_ut(jd_ut, planet_id, CALC_FLAGS)
    return RawPlanetPosition(longitude=lon % 360, latitude=lat, distance=dist, speed_longitude=speed_lon)


@dataclass
class EquatorialPosition:
    right_ascension: float  # degrés, 0-360
    declination: float  # degrés, -90 à 90


def calc_planet_equatorial(jd_ut: float, planet_id: int) -> EquatorialPosition:
    """Coordonnées équatoriales (ascension droite, déclinaison), nécessaires au calcul des
    lignes d'astrocartographie (MC/IC/ASC/DC) — contrairement au reste du thème qui reste en
    coordonnées écliptiques (longitude/latitude)."""
    (ra, dec, _dist, _speed_ra, _speed_dec, _speed_dist), _flag = swe.calc_ut(
        jd_ut, planet_id, CALC_FLAGS | swe.FLG_EQUATORIAL
    )
    return EquatorialPosition(right_ascension=ra % 360, declination=dec)


def greenwich_sidereal_time_degrees(jd_ut: float) -> float:
    """Temps sidéral de Greenwich (apparent), en degrés (0-360)."""
    return swe.sidtime(jd_ut) * 15 % 360


def jd_ut_for_date_utc_noon(date_str: str) -> float:
    """Jour julien UT à midi UTC pour une date donnée (YYYY-MM-DD) — instant représentatif
    utilisé pour le cache journalier des lignes de transit (cyclocartographie), qui n'a pas
    vocation à la précision à la minute près (un seul calcul partagé par jour)."""
    year, month, day = (int(part) for part in date_str.split("-"))
    return swe.julday(year, month, day, 12.0)


@dataclass
class BodiesResult:
    bodies: dict[str, RawPlanetPosition]
    unavailable_points: list[str]


def calc_all_bodies(jd_ut: float, include_points: list[str]) -> BodiesResult:
    bodies: dict[str, RawPlanetPosition] = {}
    unavailable: list[str] = []
    for name, planet_id in PLANET_IDS.items():
        if name in ("chiron", "lilith_mean") and name not in include_points:
            continue
        try:
            bodies[name] = calc_planet(jd_ut, planet_id)
        except swe.Error:
            # Chiron nécessite un fichier d'éphémérides (ex. seas_18.se1) absent de l'algorithme
            # Moshier intégré. On l'omet plutôt que de faire échouer tout le calcul du thème.
            unavailable.append(name)

    if "north_node" in include_points or "south_node" in include_points:
        node = calc_planet(jd_ut, NORTH_NODE_ID)
        if "north_node" in include_points:
            bodies["north_node"] = node
        if "south_node" in include_points:
            bodies["south_node"] = RawPlanetPosition(
                longitude=(node.longitude + 180) % 360,
                latitude=-node.latitude,
                distance=node.distance,
                speed_longitude=node.speed_longitude,
            )
    return BodiesResult(bodies=bodies, unavailable_points=unavailable)


@dataclass
class HousesResult:
    cusps: list[float]  # 12 cuspides, maison 1 à 12
    ascendant: float
    midheaven: float


def calc_houses(jd_ut: float, latitude: float, longitude: float, house_system: str) -> HousesResult:
    hsys = HOUSE_SYSTEM_CODES.get(house_system, b"P")
    cusps, ascmc = swe.houses(jd_ut, latitude, longitude, hsys)
    return HousesResult(
        cusps=[c % 360 for c in cusps[:12]],
        ascendant=ascmc[0] % 360,
        midheaven=ascmc[1] % 360,
    )
