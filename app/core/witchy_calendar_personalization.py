"""Personnalisation optionnelle (V2) des événements du calendrier ésotérique par croisement
avec le thème natal — voir app/reference_data/witchy_calendar_events.json,
personnalisation_optionnelle. Deux mécanismes indépendants, chacun applicable à une catégorie
d'événements différente :

1. Aspect natal (événements PONCTUELS : lunaisons, éclipses, stations) — la position exacte
   de l'événement forme-t-elle un aspect serré avec une planète ou un angle natal ?
2. Maison natale (événements qui DURENT : ingrès de planète lente, grande conjonction) — dans
   quelle maison natale tombe la position de l'événement, colorant tout un secteur de vie
   pendant sa durée ?

Dans les deux cas, si la cible touchée (mécanisme 1) ou le maître de la maison touchée
(mécanisme 2) fait partie des thèmes confirmés du thème (dispositeur final dominant, maître de
l'Ascendant, stellium — voir astrocartography_personalization.compute_theme_confirme, réutilisé
tel quel ici), l'impact personnel est amplifié.
"""

from __future__ import annotations

from app.core.aspects import angular_separation
from app.core.astrocartography_personalization import compute_theme_confirme
from app.core.chart_calculator import find_house
from app.core.dispositors import CLASSIC_PLANETS
from app.core.reference_data import ruler_map

PUNCTUAL_EVENT_TYPES = {
    "nouvelle_lune",
    "pleine_lune",
    "eclipse_solaire",
    "eclipse_lunaire",
    "station_retrograde",
    "station_directe",
}
DURATION_EVENT_TYPES = {"ingres", "grande_conjonction"}

# Voir personnalisation_optionnelle.mecanisme_1_aspect_natal du document source.
_NATAL_ASPECT_ORBS = {"conjunction": 2.0, "opposition": 2.0, "square": 1.5, "trine": 1.5, "sextile": 1.5}
_NATAL_ASPECT_ANGLES = {"conjunction": 0, "sextile": 60, "square": 90, "trine": 120, "opposition": 180}
_NATAL_TARGETS = [
    "Sun", "Moon", "Mercury", "Venus", "Mars",
    "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto",
    "Ascendant", "Midheaven",
]
# Un aspect à un luminaire ou à l'Ascendant est toujours signalé en priorité (voir
# priorite_cibles du document source) — plus intuitif pour l'utilisateur qu'une planète lente.
_PRIORITY_TARGETS = {"Sun", "Moon", "Ascendant"}


def _natal_points(chart_data: dict) -> dict[str, float]:
    points = {p["name"]: p["absolute_longitude"] for p in chart_data["planets"] if p["name"] in _NATAL_TARGETS}
    points["Ascendant"] = chart_data["angles"]["ascendant"]["absolute_longitude"]
    points["Midheaven"] = chart_data["angles"]["midheaven"]["absolute_longitude"]
    return points


def _mechanism_1_aspect_natal(event_longitude: float, chart_data: dict) -> dict | None:
    """Aspect natal le plus pertinent (priorité aux luminaires/Ascendant, puis à l'orbe la plus
    serrée) formé par la position exacte de l'événement, ou None si aucun n'entre dans l'orbe."""
    best: dict | None = None
    for target_name, target_lon in _natal_points(chart_data).items():
        sep = angular_separation(event_longitude, target_lon)
        for aspect_type, angle in _NATAL_ASPECT_ANGLES.items():
            orb = abs(sep - angle)
            if orb > _NATAL_ASPECT_ORBS[aspect_type]:
                continue
            priority = 0 if target_name in _PRIORITY_TARGETS else 1
            candidate = {"target": target_name, "aspect_type": aspect_type, "orb": round(orb, 2), "_priority": priority}
            if best is None or (candidate["_priority"], candidate["orb"]) < (best["_priority"], best["orb"]):
                best = candidate
    return best


def _mechanism_2_maison_natale(event_longitude: float, chart_data: dict) -> tuple[int, str | None]:
    """Maison natale où tombe la position de l'événement, et le maître traditionnel du signe
    occupant cette cuspide (pour tester l'amplification par thème confirmé)."""
    cusps = [h["absolute_longitude"] for h in chart_data["houses"]]
    house_number = find_house(event_longitude, cusps)
    house = next(h for h in chart_data["houses"] if h["number"] == house_number)
    ruler = ruler_map("traditional").get(house["sign"])
    return house_number, ruler


def _empty_impact() -> dict:
    return {
        "detecte": False,
        "mecanisme": None,
        "cible_touchee": None,
        "orbe_ou_maison": None,
        "theme_confirme_amplifie": False,
    }


def personalize_witchy_events(events: list[dict], chart_data: dict) -> list[dict]:
    """Attache à chaque événement un bloc `impact_personnel` (voir structure_de_sortie du
    document source). N'y touche PAS aux `event_longitude` manquants (défensif, ne devrait pas
    arriver pour les types gérés)."""
    personalized: list[dict] = []
    for event in events:
        impact = _empty_impact()
        event_longitude = event.get("event_longitude")
        event_type = event["event_type"]

        if event_longitude is not None and event_type in PUNCTUAL_EVENT_TYPES:
            match = _mechanism_1_aspect_natal(event_longitude, chart_data)
            if match is not None:
                impact["detecte"] = True
                impact["mecanisme"] = "aspect_natal"
                impact["cible_touchee"] = match["target"]
                impact["orbe_ou_maison"] = f"{match['orb']}°"
                if match["target"] in CLASSIC_PLANETS:
                    impact["theme_confirme_amplifie"] = compute_theme_confirme(match["target"], chart_data)["present"]

        elif event_longitude is not None and event_type in DURATION_EVENT_TYPES:
            house_number, ruler = _mechanism_2_maison_natale(event_longitude, chart_data)
            impact["detecte"] = True
            impact["mecanisme"] = "maison_natale"
            impact["cible_touchee"] = f"maison {house_number}"
            impact["orbe_ou_maison"] = f"maison {house_number}"
            if ruler in CLASSIC_PLANETS:
                impact["theme_confirme_amplifie"] = compute_theme_confirme(ruler, chart_data)["present"]

        personalized.append({**event, "impact_personnel": impact})
    return personalized


def personalize_day_chart(day_chart: dict, chart_data: dict) -> list[dict]:
    """Mode détail journée (voir modes_de_lecture.mode_detail_journee.personnalisation_conservee
    du document source) : applique le mécanisme 1 (aspect_natal, déjà générique sur n'importe
    quelle longitude) à CHAQUE planète de la carte du jour plutôt qu'à un seul événement
    ponctuel — les "résonances personnelles" de la journée entière. Le mécanisme 2 (maison
    natale) ne s'applique pas ici : une carte du jour n'a pas de maisons (voir day_chart.py)."""
    resonances = []
    for planet in day_chart["planets"]:
        name = planet["name"]
        if name not in CLASSIC_PLANETS:
            continue
        match = _mechanism_1_aspect_natal(planet["absolute_longitude"], chart_data)
        if match is None:
            continue
        theme_confirme_amplifie = (
            compute_theme_confirme(match["target"], chart_data)["present"]
            if match["target"] in CLASSIC_PLANETS
            else False
        )
        resonances.append(
            {
                "planete_du_jour": name,
                "cible_natale_touchee": match["target"],
                "aspect_type": match["aspect_type"],
                "orbe": match["orb"],
                "theme_confirme_amplifie": theme_confirme_amplifie,
            }
        )
    resonances.sort(key=lambda r: r["orbe"])
    return resonances
