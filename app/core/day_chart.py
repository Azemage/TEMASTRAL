"""Carte du jour ('day chart') : structure identique à un thème natal (positions, aspects,
dispositeurs), sans Ascendant ni maisons puisqu'aucun lieu n'est associé à une date seule — voir
modes_de_lecture.mode_detail_journee de app/reference_data/witchy_calendar_events.json.

AUCUN nouveau moteur de calcul : réutilise directement app.core.aspects (mêmes aspects que pour
un thème natal, entre TOUTES les planètes), app.core.dispositors (mêmes dispositeurs), et
app.core.astrocartography_personalization.compute_theme_confirme (même mécanisme de "thèmes
confirmés", relu ici comme le climat énergétique collectif de la journée plutôt que l'identité
d'une personne — voir reinterpretation_conceptuelle du document source)."""

from __future__ import annotations

from app.core import ephemeris
from app.core.aspects import BodyForAspect, compute_aspects
from app.core.astrocartography_personalization import compute_theme_confirme
from app.core.dispositors import CLASSIC_PLANETS, compute_dispositors
from app.core.zodiac import SIGNS_FR, sign_and_degree

_DEFAULT_ASPECT_ORBS: dict[str, float] = {}


def compute_day_chart(date_str: str) -> dict:
    """date_str : 'YYYY-MM-DD'. Positions calculées à midi UT (même convention que le cache
    journalier des lignes de transit d'astrocartographie — voir
    ephemeris.jd_ut_for_date_utc_noon), représentatives pour une lecture au jour près."""
    jd_ut = ephemeris.jd_ut_for_date_utc_noon(date_str)
    bodies_result = ephemeris.calc_all_bodies(jd_ut, include_points=[])

    planets: list[dict] = []
    planet_signs: dict[str, str] = {}
    aspect_bodies: list[BodyForAspect] = []
    for name, raw in bodies_result.bodies.items():
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
        if name in CLASSIC_PLANETS:
            planet_signs[name] = sign

    aspects = compute_aspects(aspect_bodies, _DEFAULT_ASPECT_ORBS, include_minor=True)

    dispositors_traditional = compute_dispositors(planet_signs, "traditional")
    dispositors_modern = compute_dispositors(planet_signs, "modern")

    # compute_theme_confirme suppose la forme d'un thème natal complet (angles.ascendant.sign,
    # planets avec "house"). Une carte du jour n'a ni Ascendant ni maisons : on passe un signe
    # d'Ascendant absent (None, qu'aucune planète ne peut jamais égaler) pour désactiver
    # silencieusement la couche "maître de l'Ascendant", et des "house" absentes pour désactiver
    # le stellium par maison — seul le stellium par signe reste pertinent pour une journée.
    pseudo_chart = {
        "dispositors_traditional": dispositors_traditional,
        "dispositors_modern": dispositors_modern,
        "angles": {"ascendant": {"sign": None}},
        "planets": [{"name": p["name"], "sign": p["sign"], "house": None} for p in planets],
    }
    themes_confirmes_du_jour = {
        planet: {k: v for k, v in compute_theme_confirme(planet, pseudo_chart).items() if not k.startswith("_")}
        for planet in CLASSIC_PLANETS
        if planet in planet_signs
    }
    # Ne garder que les planètes avec au moins un thème confirmé : "climat énergétique collectif
    # de cette journée" plutôt que 10 blocs vides à charge du prompt LLM.
    themes_confirmes_du_jour = {
        planet: data for planet, data in themes_confirmes_du_jour.items() if data["present"]
    }

    return {
        "date": date_str,
        "planets": planets,
        "aspects": aspects,
        "dispositors_traditional": dispositors_traditional,
        "dispositors_modern": dispositors_modern,
        "themes_confirmes_du_jour": themes_confirmes_du_jour,
    }
