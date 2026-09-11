"""Position actuelle des planètes classiques dans le zodiaque, indépendante de tout thème natal
— affiche le "ciel du jour" en page d'accueil avant la création d'un thème (roue compacte, sans
maisons puisqu'aucun lieu de naissance n'entre en jeu ici)."""

from __future__ import annotations

from datetime import datetime, timezone

from app.core import ephemeris
from app.core.aspects import BodyForAspect, compute_aspects
from app.core.reference_data import aspects_reference
from app.core.zodiac import SIGNS_FR, sign_and_degree

# Nombre d'aspects majeurs les plus exacts (orbe la plus fine) mis en avant dans les "points
# forts" du jour (voir `top_aspects` ci-dessous) — au-delà, ça devient une liste plate plutôt
# qu'un vrai résumé.
_TOP_ASPECTS_COUNT = 3

DAY_SKY_PLANETS = ["Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto"]

# Mêmes orbes par défaut que ChartSettings.aspect_orbs (app/schemas.py) : ce widget n'expose pas
# de réglage, un seul calcul partagé par tous les visiteurs à un instant donné.
DEFAULT_ASPECT_ORBS = {
    "conjunction": 8,
    "opposition": 8,
    "square": 7,
    "trine": 7,
    "sextile": 5,
    "semi_sextile": 2,
    "semi_square": 2,
    "sesquiquadrate": 2,
    "quincunx": 3,
    "quintile": 2,
}


def compute_day_sky(now: datetime | None = None) -> dict:
    now_utc = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    jd_ut = ephemeris.local_datetime_to_jd_ut(now_utc.strftime("%Y-%m-%d"), now_utc.strftime("%H:%M:%S"), "UTC")

    planets = []
    aspect_bodies: list[BodyForAspect] = []
    for name in DAY_SKY_PLANETS:
        raw = ephemeris.calc_planet(jd_ut, ephemeris.PLANET_IDS[name])
        sign, degree = sign_and_degree(raw.longitude)
        planets.append(
            {
                "name": name,
                "sign": sign,
                "sign_fr": SIGNS_FR[sign],
                "degree": round(degree, 2),
                "absolute_longitude": round(raw.longitude, 4),
                "retrograde": raw.retrograde,
            }
        )
        aspect_bodies.append(BodyForAspect(name=name, longitude=raw.longitude, speed_longitude=raw.speed_longitude))

    aspects = compute_aspects(aspect_bodies, DEFAULT_ASPECT_ORBS, include_minor=True)

    # "Points forts" du jour, purement déterministes (aucun texte interprétatif généré ici,
    # seulement une sélection de faits calculés — c'est le frontend qui les met en mots via
    # i18n.js, sur le même principe que le reste de l'app) : les rétrogrades en cours (un
    # facteur d'ambiance durable, contrairement aux positions qui changent chaque jour) et les
    # quelques aspects majeurs les plus exacts (les plus "actifs" du moment).
    retrograde_planets = [p["name"] for p in planets if p["retrograde"]]
    major_aspect_names = {a["name"] for a in aspects_reference()["major_aspects"]}
    top_aspects = sorted(
        (a for a in aspects if a["type"] in major_aspect_names), key=lambda a: a["orb"]
    )[:_TOP_ASPECTS_COUNT]

    return {
        "datetime_utc": now_utc.isoformat(),
        "planets": planets,
        "aspects": aspects,
        "retrograde_planets": retrograde_planets,
        "top_aspects": top_aspects,
    }
