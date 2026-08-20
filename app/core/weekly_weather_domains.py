"""Notation de la météo de la semaine par domaine de vie (amour/argent/santé/travail
quotidien) — voir doc source notation_hebdomadaire_domaines.json et
app/reference_data/weekly_domain_scoring.json. Calcul ENTIÈREMENT déterministe (code, pas
LLM) : la mise en mots du conseil/avertissement à partir de `top_positive_signal`/
`top_negative_signal` reste déléguée au LLM (voir interpretation_service.py).

Combine deux composantes, jamais confondues :
- PERSONNELLE (`personal_highlights`) : transits vers le thème natal réel de la personne — les
  mêmes données que le Pronostic hebdomadaire (voir timing_service.select_events_for_horizon).
- COLLECTIVE (`generational_aspects`) : aspects rapide (Mercure/Vénus/Mars) -> générationnelle
  (Jupiter à Pluton) de la semaine, indépendants du thème natal — voir
  weekly_weather.compute_weekly_collective — pondérés plus légèrement (`collective_multiplier`)
  qu'un transit vraiment personnel.
"""

from __future__ import annotations

from datetime import date as date_type

from app.core.reference_data import weekly_domain_scoring


def _planet_category(planet_name: str, categories: dict) -> str:
    for category, planets in categories.items():
        if category == "note" or planet_name not in planets:
            continue
        return category
    return "neutral"


def _signal_label(planet: str, aspect_type_fr: str, other_point: str) -> str:
    return f"{planet} transit {aspect_type_fr} {other_point}"


def _personal_modifiers(events: list[dict], config: dict, start_iso: str) -> list[dict]:
    """Un modificateur par transit personnel dont le type d'aspect est reconnu (aspects
    majeurs — la quinconce est prévue dans le barème mais n'est actuellement jamais produite par
    le moteur de transits, voir app/core/transits.py)."""
    table = config["modifier_by_aspect_and_category"]
    categories = config["planet_categories"]
    results = []
    for event in events:
        per_category = table.get(event["type"])
        if per_category is None:
            continue
        category = _planet_category(event["transiting_planet"], categories)
        base = per_category[category]
        # Pas de notion explicite d'orbe croissant/décroissant dans les données disponibles :
        # on approxime "applicatif" par "le pic de l'aspect n'a pas encore eu lieu au début de
        # la semaine" (l'aspect est encore en train de se resserrer), "séparatif" sinon (le pic
        # est déjà passé, l'orbe se rouvre) — cohérent avec la définition classique.
        applying = event["peak_date"] >= start_iso
        weight = config["applying_multiplier"] if applying else config["separating_multiplier"]
        results.append(
            {
                "score": base * weight,
                "label": _signal_label(event["transiting_planet"], event["type_fr"], f"{event['natal_point']} natal"),
                "natal_point": event["natal_point"],
            }
        )
    return results


def _collective_modifiers(events: list[dict], config: dict) -> list[dict]:
    table = config["modifier_by_aspect_and_category"]
    categories = config["planet_categories"]
    results = []
    for event in events:
        per_category = table.get(event["aspect_type"])
        if per_category is None:
            continue
        category = _planet_category(event["planet_a"], categories)
        base = per_category[category]
        results.append(
            {
                "score": base * config["collective_multiplier"],
                "label": _signal_label(event["planet_a"], event["aspect_type_fr"], f"{event['planet_b']} (climat collectif)"),
                "fast_planet": event["planet_a"],
            }
        )
    return results


def _area_matches_personal(area: dict, natal_point: str, natal_planet_houses: dict[str, int]) -> bool:
    if natal_point in area["planets_ref"]:
        return True
    house = natal_planet_houses.get(natal_point)
    return house is not None and house in area["houses_ref"]


def _area_matches_collective(area: dict, fast_planet: str) -> bool:
    return fast_planet in area["planets_ref"]


def _note_for_score(total: float, final_scale: list[dict]) -> tuple[int, str]:
    for tier in final_scale:
        lo, hi = tier["min_score"], tier["max_score"]
        if (lo is None or total >= lo) and (hi is None or total <= hi):
            return tier["note"], tier["label"]
    return 3, "semaine stable"  # filet de sécurité, ne devrait jamais servir (final_scale couvre -inf..+inf)


def compute_weekly_domain_scores(
    natal_planet_houses: dict[str, int],
    personal_highlights: list[dict],
    generational_aspects: list[dict],
    start_date: date_type,
) -> dict[str, dict]:
    """Note 1-5 par domaine de vie (amour/argent/santé/travail_quotidien) pour la semaine
    `start_date`. `natal_planet_houses` : nom de planète natale -> numéro de maison natale
    (voir chart.computed_chart_data['planets'])."""
    config = weekly_domain_scoring()
    start_iso = start_date.isoformat()

    personal_mods = _personal_modifiers(personal_highlights, config, start_iso)
    collective_mods = _collective_modifiers(generational_aspects, config)

    result = {}
    for area in config["life_areas"]:
        matched = [m for m in personal_mods if _area_matches_personal(area, m["natal_point"], natal_planet_houses)]
        matched += [m for m in collective_mods if _area_matches_collective(area, m["fast_planet"])]

        total = sum(m["score"] for m in matched)
        note, label = _note_for_score(total, config["final_scale"])

        positive = max((m for m in matched if m["score"] > 0), key=lambda m: m["score"], default=None)
        negative = min((m for m in matched if m["score"] < 0), key=lambda m: m["score"], default=None)

        result[area["code"]] = {
            "note": note,
            "label": label,
            "top_positive_signal": positive["label"] if positive else None,
            "top_negative_signal": negative["label"] if negative else None,
        }
    return result
