"""Météo astrologique de la semaine — voir app/reference_data (docs sources non copiées telles
quelles ici, résumées) : echelles_temporelles_lecture.json (mode_semaine) et
meteo_hebdomadaire_par_signe.md.

Deux couches déterministes, indépendantes du thème natal (le même calcul pour tout le monde une
semaine donnée, sur le même principe de cache global que le calendrier ésotérique) :

1. `compute_weekly_collective` — Lune (parcours signe par signe + ingrès), Mercure/Vénus/Mars
   (position de départ/fin, rétrogradation, ingrès), aspects exacts entre ces 4 planètes formés
   PENDANT la semaine (transit-transit, pas transit-natal), aspects exacts entre une planète
   rapide (Mercure/Vénus/Mars) et une planète générationnelle (Jupiter à Pluton) formés PENDANT
   la semaine (`generational_aspects` — même principe transit-transit, voir
   _compute_generational_aspects et weekly_weather_domains.py pour son usage dans la notation
   par domaine), événements du calendrier ésotérique tombant dans la semaine (réutilise
   directement compute_witchy_calendar/compute_station_events, AUCUN recalcul), et une liste de
   points forts (`highlights`) notés (même esprit que le score 1-5 du calendrier witchy) pour
   repérer les éléments les plus significatifs de la semaine.
2. `compute_generic_weekly_by_sign` — le "thème générique par signe" des horoscopes de presse :
   chaque signe est traité comme son propre Ascendant (maisons en signes intégraux), et la
   maison générique touchée par l'événement principal de la semaine détermine la tonalité de
   chaque signe. Réutilise `zodiac.signs_distance` (même formule mod-12 que les maisons
   dérivées) et `houses_meanings.json` — aucun nouveau moteur de calcul.

La couche PERSONNALISÉE (impact sur le thème natal réel) n'est PAS ici : elle réutilise
directement `timing_service.compute_timing`/`compute_forecast`, déjà spécifiés pour le Pronostic
hebdomadaire — voir interpretation_service.py, reading_type='weekly_weather'.
"""

from __future__ import annotations

from datetime import date as date_type
from datetime import timedelta
from itertools import combinations

import swisseph as swe

from app.core import ephemeris
from app.core.aspects import angular_separation
from app.core.reference_data import aspects_reference, houses_meanings
from app.core.root_finding import scan_zero_crossings
from app.core.witchy_calendar import STATION_PLANETS, compute_station_events, compute_witchy_calendar
from app.core.zodiac import SIGNS, SIGNS_FR, sign_and_degree, signs_distance

MOON_PLANETS = ["Moon"]
FAST_PLANETS = ["Mercury", "Venus", "Mars"]
# Chiron et l'axe des Nœuds (représenté par north_node seul — un aspect à l'un est
# automatiquement le même aspect à l'autre, voir bibliotheque_combinaisons_hebdomadaires.md)
# sont des points LENTS comme Jupiter à Pluton : mêmes techniques transit-transit ci-dessous
# (voir notation_hebdomadaire_domaines.json, points_mineurs_note).
GENERATIONAL_PLANETS = ["Jupiter", "Saturn", "Uranus", "Neptune", "Pluto", "chiron", "north_node"]
WEEK_DAYS = 7

# Poids heuristiques (mêmes ordres de grandeur que le calendrier witchy, mais propres à
# l'échelle hebdomadaire) : un ingrès lunaire est fréquent (~3/semaine) donc le cas le moins
# marquant de la semaine (plancher réel 1, pas artificiellement remonté à 2 — voir
# app/core/witchy_calendar.py::_score_from_raw pour le même principe), un ingrès de planète
# rapide est plus rare donc plus notable. Les stations réutilisent directement le score déjà
# calculé par compute_station_events (catalogue witchy), aucune valeur nouvelle.
_MOON_INGRESS_SCORE = 1
_FAST_INGRESS_SCORE = 2
_ASPECT_TYPE_SCORE = {"conjunction": 3, "opposition": 3, "square": 3, "trine": 2, "sextile": 2}
# Un aspect rapide -> générationnelle (voir _compute_generational_aspects) est structurellement
# plus rare/marquant qu'un aspect entre deux planètes rapides (la planète lente immobilise le
# thème sur toute sa durée de transit, contrairement à un aspect rapide-rapide vite dépassé) :
# noté un cran au-dessus du même type d'aspect entre planètes rapides, mêmes bornes 1-4.
_ASPECT_TYPE_SCORE_GENERATIONAL = {"conjunction": 4, "opposition": 4, "square": 4, "trine": 3, "sextile": 3}

_ASPECT_TARGETS = {
    "conjunction": [0.0],
    "sextile": [60.0, 300.0],
    "square": [90.0, 270.0],
    "trine": [120.0, 240.0],
    "opposition": [180.0],
}
_ASPECT_TYPE_FR = {
    "conjunction": "conjonction", "sextile": "sextile", "square": "carré",
    "trine": "trigone", "opposition": "opposition",
}
_ASPECT_SCAN_STEP_DAYS = 0.5


def _jd_at_noon(d: date_type) -> float:
    return ephemeris.jd_ut_for_date_utc_noon(d.isoformat())


def _longitude(jd_ut: float, planet_id: int) -> float:
    return ephemeris.calc_planet(jd_ut, planet_id).longitude % 360


def _planet_id(name: str) -> int:
    """Le nœud nord n'a pas d'entrée dans ephemeris.PLANET_IDS (voir calc_all_bodies, qui le
    traite à part pour dériver aussi le nœud sud) — on le résout ici séparément plutôt que de
    dupliquer cette logique."""
    if name == "north_node":
        return ephemeris.NORTH_NODE_ID
    return ephemeris.PLANET_IDS[name]


def _position_dict(name: str, jd_ut: float) -> dict:
    raw = ephemeris.calc_planet(jd_ut, _planet_id(name))
    sign, degree = sign_and_degree(raw.longitude)
    return {
        "name": name,
        "sign": sign,
        "sign_fr": SIGNS_FR[sign],
        "degree": round(degree, 2),
        "absolute_longitude": round(raw.longitude, 4),
        "retrograde": raw.speed_longitude < 0,
    }


def _week_dates(start_date: date_type) -> list[date_type]:
    return [start_date + timedelta(days=i) for i in range(WEEK_DAYS)]


def _compute_moon_path(dates: list[date_type]) -> tuple[list[dict], list[dict]]:
    """Position lunaire pour chaque jour de la semaine, et les ingrès (changements de signe)
    détectés entre deux jours consécutifs — granularité journalière, cohérente avec l'échelle
    'météo' de la fonctionnalité (pas besoin de l'instant exact à la minute près)."""
    path = [_position_dict("Moon", _jd_at_noon(d)) | {"date": d.isoformat()} for d in dates]
    ingresses = []
    for prev, curr in zip(path, path[1:]):
        if prev["sign"] != curr["sign"]:
            ingresses.append({"date": curr["date"], "from_sign": prev["sign"], "to_sign": curr["sign"]})
    return path, ingresses


def _daily_positions(planet: str, dates: list[date_type]) -> list[dict]:
    return [_position_dict(planet, _jd_at_noon(d)) for d in dates]


def compute_daily_fast_positions(dates: list[date_type]) -> dict[str, list[dict]]:
    """Position jour par jour de la Lune et des 3 planètes rapides — utilisé pour la détection
    des degrés remarquables (voir weekly_weather_combinations.py, orbe serré donc besoin d'un
    échantillon quotidien plutôt que du seul début/fin de semaine)."""
    return {
        planet: [position | {"date": d.isoformat()} for position, d in zip(_daily_positions(planet, dates), dates)]
        for planet in MOON_PLANETS + FAST_PLANETS
    }


def _compute_fast_planets(dates: list[date_type]) -> list[dict]:
    """Pour Mercure/Vénus/Mars : position de début/fin de semaine, rétrogradation, et ingrès
    éventuel détecté par comparaison jour par jour (comme pour la Lune, granularité journalière
    suffisante — ces planètes ne peuvent pas changer de signe deux fois dans la même semaine)."""
    results = []
    for planet in FAST_PLANETS:
        daily = _daily_positions(planet, dates)
        ingress = None
        for i in range(1, len(daily)):
            prev, curr = daily[i - 1], daily[i]
            if prev["sign"] != curr["sign"]:
                ingress = {"date": dates[i].isoformat(), "from_sign": prev["sign"], "to_sign": curr["sign"]}
                break
        start, end = daily[0], daily[-1]
        results.append(
            {
                "name": planet,
                "sign_start": start["sign"],
                "degree_start": start["degree"],
                "retrograde_start": start["retrograde"],
                "sign_end": end["sign"],
                "degree_end": end["degree"],
                "retrograde_end": end["retrograde"],
                "ingress": ingress,
            }
        )
    return results


def _scan_pair_aspect_events(start_jd: float, end_jd: float, planet_a: str, planet_b: str, score_table: dict) -> list[dict]:
    """Aspects majeurs qui deviennent EXACTS (orbe = 0, croisement détecté) entre deux planètes
    en transit pendant la semaine — transit-transit, pas transit-natal (voir
    enrichissement_contextuel_mode_apercu du calendrier witchy pour le même principe appliqué
    ailleurs). Fenêtre courte (7 jours) : coût de calcul négligeable, même balayé pour de
    nombreuses paires (voir _compute_exact_transit_transit_aspects et
    _compute_generational_aspects, qui appellent cette fonction pour chaque paire)."""
    id_a, id_b = _planet_id(planet_a), _planet_id(planet_b)

    def directed_diff(t: float, a=id_a, b=id_b) -> float:
        return (_longitude(t, b) - _longitude(t, a)) % 360

    events = []
    for aspect_type, targets in _ASPECT_TARGETS.items():
        for target in targets:

            def f(t, tgt=target, dd=directed_diff):
                return ((dd(t) - tgt + 180) % 360) - 180

            for jd in scan_zero_crossings(f, start_jd, end_jd, step=_ASPECT_SCAN_STEP_DAYS):
                year, month, day, _hour = swe.revjul(jd)
                events.append(
                    {
                        "date": f"{year:04d}-{month:02d}-{day:02d}",
                        "planet_a": planet_a,
                        "planet_b": planet_b,
                        "aspect_type": aspect_type,
                        "aspect_type_fr": _ASPECT_TYPE_FR[aspect_type],
                        "score": score_table[aspect_type],
                    }
                )
    return events


def _compute_exact_transit_transit_aspects(start_jd: float, end_jd: float) -> list[dict]:
    """Aspects exacts entre deux des 4 planètes rapides (Lune/Mercure/Vénus/Mars) pendant la
    semaine — voir _scan_pair_aspect_events."""
    events = []
    for planet_a, planet_b in combinations(MOON_PLANETS + FAST_PLANETS, 2):
        events += _scan_pair_aspect_events(start_jd, end_jd, planet_a, planet_b, _ASPECT_TYPE_SCORE)
    events.sort(key=lambda e: e["date"])
    return events


def _compute_generational_aspects(start_jd: float, end_jd: float) -> list[dict]:
    """Technique 'Aspects planète rapide vers planète lente/générationnelle' (voir
    echelles_temporelles_lecture.json, mode_semaine) : Mercure/Vénus/Mars (rapides, `planet_a`)
    en aspect majeur EXACT cette semaine avec Jupiter à Pluton (`planet_b`, quasi immobiles à
    cette échelle). La Lune est volontairement exclue ici (elle bouge trop vite pour que ces
    aspects soient un signal hebdomadaire distinctif — voir doc source). Ne colore jamais le
    thème personnel : c'est un événement COLLECTIF, pertinent pour tout le monde cette
    semaine-là (voir weekly_weather_domains.py pour son usage dans la notation par domaine)."""
    events = []
    for fast in FAST_PLANETS:
        for slow in GENERATIONAL_PLANETS:
            events += _scan_pair_aspect_events(start_jd, end_jd, fast, slow, _ASPECT_TYPE_SCORE_GENERATIONAL)
    events.sort(key=lambda e: e["date"])
    return events


def _compute_moon_generational_aspects(start_jd: float, end_jd: float) -> list[dict]:
    """Même technique que _compute_generational_aspects, mais pour la Lune : distinct de
    `generational_aspects` (qui reste Mercure/Vénus/Mars — voir sa docstring, la Lune y est
    exclue par conception car trop rapide pour un signal de notation collective). Ici, la Lune
    reste pertinente pour la bibliothèque de combinaisons hebdomadaires (voir
    weekly_weather_combinations.py, bibliotheque_combinaisons_hebdomadaires.md section 1.2, où
    la Lune fait bien partie des 4 planètes rapides de la formule de phrase)."""
    events = []
    for slow in GENERATIONAL_PLANETS:
        events += _scan_pair_aspect_events(start_jd, end_jd, "Moon", slow, _ASPECT_TYPE_SCORE_GENERATIONAL)
    events.sort(key=lambda e: e["date"])
    return events


def _compute_slow_planet_signs(start_date: date_type) -> dict[str, str]:
    """Signe de chaque planète générationnelle en DÉBUT de semaine (quasi immobile à cette
    échelle, un seul instantané suffit) — utilisé par les combinaisons éditoriales (ex. 'Jupiter
    en signe d'eau', voir weekly_weather_combinations.py)."""
    jd = _jd_at_noon(start_date)
    return {planet: _position_dict(planet, jd)["sign"] for planet in GENERATIONAL_PLANETS}


def _witchy_events_in_range(start_date: date_type, end_date: date_type) -> list[dict]:
    """Événements du calendrier ésotérique déjà calculés (compute_witchy_calendar, AUCUN
    recalcul) dont la date tombe dans la semaine — gère la semaine à cheval sur deux années."""
    years = {start_date.year, end_date.year}
    all_events = [e for year in years for e in compute_witchy_calendar(year)]
    start_iso, end_iso = start_date.isoformat(), end_date.isoformat()
    return sorted((e for e in all_events if start_iso <= e["event_date"] <= end_iso), key=lambda e: e["event_date"])


def _fast_station_events(start_date: date_type, end_date: date_type) -> list[dict]:
    """Stations rétrogrades/directes de Mercure/Vénus/Mars dans la semaine — réutilise
    compute_station_events (calendrier witchy) tel quel, filtré aux 3 planètes rapides et à la
    fenêtre (le score déjà calculé par le catalogue witchy est repris sans modification)."""
    start_jd = _jd_at_noon(start_date)
    end_jd = _jd_at_noon(end_date) + 1
    all_stations = compute_station_events(start_jd, end_jd)
    return [e for e in all_stations if e["planet"] in FAST_PLANETS and e["planet"] in STATION_PLANETS]


def _assemble_highlights(
    moon_ingresses: list[dict],
    fast_planets: list[dict],
    stations: list[dict],
    witchy_events: list[dict],
    aspects: list[dict],
    generational_aspects: list[dict],
    moon_generational_aspects: list[dict],
) -> list[dict]:
    highlights: list[dict] = []
    for ingress in moon_ingresses:
        highlights.append(
            {
                "date": ingress["date"], "kind": "ingres_lune", "planet": "Moon",
                "sign": ingress["to_sign"], "from_sign": ingress["from_sign"], "score": _MOON_INGRESS_SCORE,
            }
        )
    for planet in fast_planets:
        if planet["ingress"]:
            highlights.append(
                {
                    "date": planet["ingress"]["date"], "kind": "ingres_rapide", "planet": planet["name"],
                    "sign": planet["ingress"]["to_sign"], "from_sign": planet["ingress"]["from_sign"],
                    "score": _FAST_INGRESS_SCORE,
                }
            )
    for station in stations:
        highlights.append(
            {
                "date": station["event_date"], "kind": "station", "planet": station["planet"],
                "sign": station["sign"], "direction": station["direction"],
                "meaning_template": station["meaning_template"], "score": station["score"],
            }
        )
    for event in witchy_events:
        highlights.append(
            {
                "date": event["event_date"], "kind": event["event_type"], "planet": event.get("planet"),
                "sign": event.get("sign"), "meaning_template": event.get("meaning_template"),
                "score": event["score"],
            }
        )
    for aspect in aspects:
        highlights.append(
            {
                "date": aspect["date"], "kind": "aspect_exact", "planet": aspect["planet_a"],
                "planet_b": aspect["planet_b"], "aspect_type": aspect["aspect_type"],
                "aspect_type_fr": aspect["aspect_type_fr"], "sign": None, "score": aspect["score"],
            }
        )
    for aspect in generational_aspects + moon_generational_aspects:
        highlights.append(
            {
                "date": aspect["date"], "kind": "aspect_generational", "planet": aspect["planet_a"],
                "planet_b": aspect["planet_b"], "aspect_type": aspect["aspect_type"],
                "aspect_type_fr": aspect["aspect_type_fr"], "sign": None, "score": aspect["score"],
            }
        )
    highlights.sort(key=lambda h: (-h["score"], h["date"]))
    return highlights


def compute_weekly_collective(start_date: date_type) -> dict:
    """Point d'entrée principal : toute la couche collective (indépendante du thème natal) de
    la météo de la semaine débutant à `start_date` (7 jours, start_date inclus)."""
    dates = _week_dates(start_date)
    end_date = dates[-1]
    start_jd, end_jd = _jd_at_noon(start_date), _jd_at_noon(end_date)

    moon_path, moon_ingresses = _compute_moon_path(dates)
    fast_planets = _compute_fast_planets(dates)
    stations = _fast_station_events(start_date, end_date)
    witchy_events = _witchy_events_in_range(start_date, end_date)
    aspects = _compute_exact_transit_transit_aspects(start_jd, end_jd)
    generational_aspects = _compute_generational_aspects(start_jd, end_jd)
    moon_generational_aspects = _compute_moon_generational_aspects(start_jd, end_jd)
    highlights = _assemble_highlights(
        moon_ingresses, fast_planets, stations, witchy_events, aspects, generational_aspects, moon_generational_aspects
    )

    main_event = next((h for h in highlights if h.get("sign")), None)
    if main_event is None:
        main_event = {"kind": "lune_transit", "planet": "Moon", "sign": moon_path[0]["sign"], "score": 0}

    # Bibliothèque de combinaisons hebdomadaires (voir weekly_weather_combinations.py et
    # bibliotheque_combinaisons_hebdomadaires.md) : import local pour éviter tout risque de
    # cycle (ce module importe déjà pas mal de choses de weekly_weather.py).
    from app.core.weekly_weather_combinations import compute_weekly_combination_lines

    slow_planet_signs = _compute_slow_planet_signs(start_date)
    daily_fast_positions = compute_daily_fast_positions(dates)
    combination_lines = compute_weekly_combination_lines(
        fast_planets=fast_planets,
        moon_path=moon_path,
        generational_aspects=generational_aspects,
        moon_generational_aspects=moon_generational_aspects,
        daily_fast_positions=daily_fast_positions,
        slow_planet_signs=slow_planet_signs,
    )

    return {
        "period_start": start_date.isoformat(),
        "period_end": end_date.isoformat(),
        "moon_path": moon_path,
        "moon_ingresses": moon_ingresses,
        "fast_planets": fast_planets,
        "stations": stations,
        "witchy_events": witchy_events,
        "transit_transit_aspects": aspects,
        "generational_aspects": generational_aspects,
        "moon_generational_aspects": moon_generational_aspects,
        "combination_lines": combination_lines,
        "highlights": highlights,
        "main_event": {"kind": main_event["kind"], "planet": main_event.get("planet"), "sign": main_event["sign"]},
    }


_HOUSE_ASPECT_NATURE_SCORE = {
    "harmonieux": 5,  # sextile/trigone (maisons 3/5/9/11) — le lien le plus fluide
    "variable": 4,  # conjonction (maison 1) — "sous les projecteurs", énergie forte mais neutre
    "mineur": 3,  # semi-sextile (maisons 2/12) — lien discret, ni facile ni difficile
    "tendu": 2,  # carré/opposition (maisons 4/7/10) — actif, avec friction réelle
    "mineur inconfortable": 1,  # quinconce (maisons 6/8) — ajustement, le lien le plus faible
}
# Chaque nature astrologique de aspects.json (mêmes 5 valeurs qu'ailleurs dans l'app) a
# désormais sa propre note, du plancher réel 1 au plafond 5 — pas de valeur ex æquo qui
# comprimerait artificiellement le milieu de l'échelle. "tendu" (carré/opposition, un aspect
# MAJEUR même s'il est difficile) reste jugé plus rude qu'un "mineur" (semi-sextile, discret)
# pour une tonalité hebdomadaire générale, mais moins que "mineur inconfortable" (quinconce,
# aucune affinité de signe/élément entre les deux maisons — le lien le plus dissonant).


def _house_score(generic_house: int) -> int:
    """Note 1-5 d'une maison générique, PAS une nouvelle doctrine : relit simplement la maison
    comme l'aspect qu'elle représente structurellement depuis la maison 1 (maison N = (N-1)*30°),
    et réutilise le champ `nature` déjà défini pour cet aspect dans aspects.json (harmonieux =
    trigone/sextile, tendu = carré/opposition, mineur inconfortable = quinconce...) — même
    vocabulaire que partout ailleurs dans l'app, aucune notion nouvelle introduite."""
    angle = (generic_house - 1) * 30
    separation = angle if angle <= 180 else 360 - angle
    ref = aspects_reference()
    aspect_def = next(a for a in ref["major_aspects"] + ref["minor_aspects"] if a["angle"] == separation)
    return _HOUSE_ASPECT_NATURE_SCORE[aspect_def["nature"]]


def compute_generic_weekly_by_sign(main_event_sign: str) -> list[dict]:
    """Couche 3 (voir meteo_hebdomadaire_par_signe.md) : pour chacun des 12 signes traité comme
    son propre Ascendant générique, la maison générique (signes intégraux) touchée par le signe
    de l'événement principal de la semaine, avec le thème de vie associé (houses_meanings.json)
    et une note déterministe 1-5 (voir `_house_score`) permettant de comparer les 12 signes entre
    eux. Aucun nouveau moteur pour la maison elle-même : `signs_distance` implémente déjà
    exactement la formule mod-12 requise (même principe que les maisons dérivées, voir
    derived_houses.py)."""
    houses_by_number = {h["number"]: h for h in houses_meanings()["houses"]}
    result = []
    for sign in SIGNS:
        generic_house = signs_distance(sign, main_event_sign)
        house = houses_by_number[generic_house]
        result.append(
            {
                "sign": sign,
                "sign_fr": SIGNS_FR[sign],
                "generic_house": generic_house,
                "house_keyword": house["keyword"],
                "house_themes": house["themes"],
                "is_main_event_sign": sign == main_event_sign,
                "score": _house_score(generic_house),
            }
        )
    return result
