"""Points forts hebdomadaires par combinaison — voir doc source
bibliotheque_combinaisons_hebdomadaires.md et app/reference_data/weekly_combinations_library.json.

~10 lignes de texte, ENTIÈREMENT déterministes (formule + lookup, AUCUN appel LLM), qui servent
(1) d'affichage direct rapide dans l'app et (2) de donnée d'entrée factuelle injectée dans le
prompt de la lecture complète (le LLM synthétise/priorise ces lignes, il ne les régénère jamais
— même principe que les `themes_confirmes` du thème natal).

Note de portée : ces lignes sont du texte français prêt à l'emploi (comme `meaning_template`
ailleurs dans l'app, ex. witchy_calendar_events.json) — pas traduites en 3 langues comme le
reste de l'UI. Cohérent avec le fait qu'elles sont d'abord pensées comme matière première pour
le LLM (qui, lui, traduit dans la langue demandée) ; l'affichage direct en français est un bonus
secondaire, pas la même garantie multilingue que le reste du site.

Quatre sources, assemblées par ordre de priorité (voir compute_weekly_combination_lines) :
1. Combinaisons éditoriales composées (curated_combinations) — le contenu le plus riche.
2. Aspects rapide x lente formés cette semaine (formule combinable, section 1 du doc source).
3. Degrés remarquables détectés sur les 4 planètes rapides (section 3).
4. Position des planètes rapides dans leur signe (section 2, toujours présentes en dernier).
"""

from __future__ import annotations

import zlib
from datetime import date as date_type

from app.core.reference_data import planets_in_signs_full, weekly_combinations_library
from app.core.zodiac import SIGNS_FR

_HARD_ASPECTS = {"square", "opposition"}

_FR_PLANET_NAMES = {
    "Moon": "La Lune", "Mercury": "Mercure", "Venus": "Vénus", "Mars": "Mars",
    "Jupiter": "Jupiter", "Saturn": "Saturne", "Uranus": "Uranus", "Neptune": "Neptune",
    "Pluto": "Pluton", "chiron": "Chiron", "north_node": "l'axe des Nœuds",
}

_MAX_LINES = 10


def _fr_name(planet: str) -> str:
    return _FR_PLANET_NAMES.get(planet, planet)


def _stable_choice(options: list[str], seed: str) -> str:
    """Sélection déterministe (PAS aléatoire) d'une variante de phrasé parmi plusieurs — stable
    pour une combinaison exacte donnée (même semaine, mêmes planètes, même aspect), pour rester
    reproductible d'un appel à l'autre (voir aspect_modulators.note de la bibliothèque)."""
    if len(options) == 1:
        return options[0]
    return options[zlib.crc32(seed.encode("utf-8")) % len(options)]


def _slow_point_key(planet_name: str) -> str:
    return "node_axis" if planet_name in ("north_node", "south_node") else planet_name


def _capitalize(sentence: str) -> str:
    return sentence[0].upper() + sentence[1:] if sentence else sentence


# ---------------------------------------------------------------------------
# Section 1 : formule combinable planète rapide x planète lente
# ---------------------------------------------------------------------------
def _theme_for(planet_key: str, fast_themes: dict, slow_themes: dict) -> str | None:
    """Le second opérande d'un aspect peut être une planète lente (Jupiter à Pluton, Chiron,
    l'axe des Nœuds) OU une autre planète rapide (voir build_aspect_combination_lines, appelée
    aussi sur transit_transit_aspects — les aspects Lune/Mercure/Vénus/Mars entre elles n'ont
    pas moins besoin d'une phrase que les aspects vers les planètes lentes) : on cherche d'abord
    dans slow_themes, puis on retombe sur fast_themes."""
    return slow_themes.get(planet_key, fast_themes.get(planet_key))


def build_aspect_combination_lines(aspect_events: list[dict], kind: str) -> list[dict]:
    lib = weekly_combinations_library()
    fast_themes, slow_themes, modulators = lib["fast_planet_themes"], lib["slow_point_themes"], lib["aspect_modulators"]

    lines = []
    for aspect in aspect_events:
        fast, other_raw, aspect_type = aspect["planet_a"], aspect["planet_b"], aspect["aspect_type"]
        other_key = _slow_point_key(other_raw)
        other_theme = _theme_for(other_key, fast_themes, slow_themes)
        if fast not in fast_themes or other_theme is None or aspect_type not in modulators:
            continue
        seed = f"{aspect['date']}|{fast}|{other_raw}|{aspect_type}"
        modulator = _stable_choice(modulators[aspect_type], seed)
        text = _capitalize(f"{fast_themes[fast]} {modulator} {other_theme} cette semaine.")
        lines.append(
            {
                "kind": kind,
                "date": aspect["date"],
                "planet": fast,
                "planet_b": other_raw,
                "aspect_type": aspect_type,
                "aspect_type_fr": aspect["aspect_type_fr"],
                "score": aspect["score"],
                "text": text,
            }
        )
    lines.sort(key=lambda line: line["date"])
    return lines


# ---------------------------------------------------------------------------
# Section 2 : position des planètes rapides dans leur signe (réutilise
# planets_in_signs_full.json tel quel, aucun nouveau contenu)
# ---------------------------------------------------------------------------
def build_position_lines(moon_start_sign: str, fast_planets: list[dict]) -> list[dict]:
    signs_full = planets_in_signs_full()
    entries = [("Moon", moon_start_sign)] + [(p["name"], p["sign_start"]) for p in fast_planets]

    lines = []
    for planet, sign in entries:
        entry = signs_full.get(planet, {}).get(sign)
        if not entry:
            continue
        text = f"{_fr_name(planet)} en {SIGNS_FR[sign]} cette semaine : {entry['synthesis']}"
        lines.append({"kind": "position_signe", "planet": planet, "sign": sign, "text": text})
    return lines


# ---------------------------------------------------------------------------
# Section 3 : degrés remarquables
# ---------------------------------------------------------------------------
def _critical_degree_signal(sign: str, degree: float, cfg: dict) -> dict | None:
    orb = cfg["orb"]
    if sign in cfg["cardinal_signs"]:
        degrees, kind = cfg["cardinal_degrees"], "cardinal"
    elif sign in cfg["fixed_signs"]:
        degrees, kind = cfg["fixed_degrees"], "fixed"
    else:
        degrees, kind = cfg["mutable_degrees"], "mutable"
    for target_degree in degrees:
        if abs(degree - target_degree) <= orb:
            degree_type = "aries_point" if (sign == "Aries" and target_degree == 0) else kind
            return {"degree_type": degree_type, "meaning": cfg["meanings"][degree_type]}
    if abs(degree - cfg["anaretic_degree"]) <= orb:
        return {"degree_type": "anaretic", "meaning": cfg["meanings"]["anaretic"]}
    return None


def build_critical_degree_lines(daily_fast_positions: dict[str, list[dict]]) -> list[dict]:
    cfg = weekly_combinations_library()["critical_degrees"]
    lines = []
    seen: set[tuple[str, str]] = set()
    for planet, daily in daily_fast_positions.items():
        for position in daily:
            signal = _critical_degree_signal(position["sign"], position["degree"], cfg)
            if signal is None:
                continue
            key = (planet, signal["degree_type"])
            if key in seen:  # une planète peut rester dans l'orbe plusieurs jours de suite
                continue
            seen.add(key)
            text = (
                f"{_fr_name(planet)} touche un degré remarquable en {SIGNS_FR[position['sign']]} "
                f"le {position['date']} : {signal['meaning']}."
            )
            lines.append(
                {
                    "kind": "degre_remarquable", "date": position["date"], "planet": planet,
                    "sign": position["sign"], "degree_type": signal["degree_type"], "text": text,
                }
            )
    lines.sort(key=lambda line: line["date"])
    return lines


# ---------------------------------------------------------------------------
# Section 4 : combinaisons éditoriales composées (donnée de configuration)
# ---------------------------------------------------------------------------
def _is_retrograde(fast_planets: list[dict], planet: str) -> bool:
    p = next((p for p in fast_planets if p["name"] == planet), None)
    return bool(p and (p["retrograde_start"] or p["retrograde_end"]))


def _hard_aspect_targets(aspect_events: list[dict], planet: str, aspect_types: list[str]) -> set[str]:
    return {e["planet_b"] for e in aspect_events if e["planet_a"] == planet and e["aspect_type"] in aspect_types}


def _evaluate_curated_condition(condition: dict, ctx: dict) -> bool:
    kind = condition["type"]
    if kind == "retrograde":
        return _is_retrograde(ctx["fast_planets"], condition["planet"])
    if kind == "slow_in_signs":
        return any(ctx["slow_planet_signs"].get(planet) in condition["signs"] for planet in condition["planets"])
    if kind == "both_hard_aspect_same_target":
        planet_a, planet_b = condition["planets"]
        aspects = ctx["generational_aspects"] + ctx["moon_generational_aspects"]
        targets_a = _hard_aspect_targets(aspects, planet_a, condition["aspect_types"])
        targets_b = _hard_aspect_targets(aspects, planet_b, condition["aspect_types"])
        return bool(targets_a & targets_b)
    if kind == "hard_aspect":
        aspects = ctx["generational_aspects"] + ctx["moon_generational_aspects"]
        return any(
            e["planet_a"] == condition["planet_a"] and e["planet_b"] == condition["planet_b"] and e["aspect_type"] in _HARD_ASPECTS
            for e in aspects
        )
    return False


def build_curated_combination_lines(ctx: dict) -> list[dict]:
    lib = weekly_combinations_library()
    lines = []
    for combo in lib["curated_combinations"]["combinations"]:
        if all(_evaluate_curated_condition(c, ctx) for c in combo["conditions"]):
            lines.append({"kind": "combinaison_editoriale", "id": combo["id"], "score": combo["score"], "text": combo["text"]})
    return lines


# ---------------------------------------------------------------------------
# Assemblage final (section 5.1 du doc source)
# ---------------------------------------------------------------------------
def compute_weekly_combination_lines(
    fast_planets: list[dict],
    moon_path: list[dict],
    generational_aspects: list[dict],
    moon_generational_aspects: list[dict],
    transit_transit_aspects: list[dict],
    daily_fast_positions: dict[str, list[dict]],
    slow_planet_signs: dict[str, str],
) -> list[dict]:
    """~10 lignes ordonnées par priorité : (1) combinaisons éditoriales, (2) aspects Mercure/
    Vénus/Mars x lente de la semaine, (3) aspects entre planètes rapides elles-mêmes
    (`transit_transit_aspects`, ex. Lune conjonction Vénus — la même formule de phrase que (2),
    réutilisant `fast_planet_themes` pour les DEUX opérandes plutôt que `slow_point_themes`),
    (4) degrés remarquables, (5) aspects Lune x lente (la Lune en forme structurellement
    beaucoup plus souvent — elle change de signe tous les ~2,5 jours — donc reléguée en dernier
    parmi les aspects pour ne pas noyer le reste), (6) position des 4 planètes rapides dans leur
    signe. Les positions (6) sont TOUJOURS présentes en entier (voir doc source, section 5.1
    point 4), même sans aucun signal notable : les catégories 1-5 se partagent le reste du
    budget de ~10 lignes plutôt que de les évincer."""
    ctx = {
        "fast_planets": fast_planets,
        "generational_aspects": generational_aspects,
        "moon_generational_aspects": moon_generational_aspects,
        "slow_planet_signs": slow_planet_signs,
    }

    curated = build_curated_combination_lines(ctx)
    fast_slow_lines = build_aspect_combination_lines(generational_aspects, kind="aspect_rapide_lente")
    fast_fast_lines = build_aspect_combination_lines(transit_transit_aspects, kind="aspect_rapide_rapide")
    degree_lines = build_critical_degree_lines(daily_fast_positions)
    moon_aspect_lines = build_aspect_combination_lines(moon_generational_aspects, kind="aspect_rapide_lente")
    position_lines = build_position_lines(moon_path[0]["sign"], fast_planets)

    variable_budget = max(_MAX_LINES - len(position_lines), 0)
    variable = (curated + fast_slow_lines + fast_fast_lines + degree_lines + moon_aspect_lines)[:variable_budget]
    return variable + position_lines
