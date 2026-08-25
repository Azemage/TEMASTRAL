"""Points forts hebdomadaires par combinaison — voir docs source
bibliotheque_combinaisons_hebdomadaires.md (v1) et bibliotheque_combinaisons_hebdomadaires2.md
(v2) et app/reference_data/weekly_combinations_library.json.

~10 lignes de texte, ENTIÈREMENT déterministes (banque de phrases/formule/lookup, AUCUN appel
LLM), qui servent (1) d'affichage direct rapide dans l'app et (2) de donnée d'entrée factuelle
injectée dans le prompt de la lecture complète (le LLM synthétise/priorise ces lignes, il ne les
régénère jamais — même principe que les `themes_confirmes` du thème natal).

Note de portée : ces lignes sont du texte français prêt à l'emploi (comme `meaning_template`
ailleurs dans l'app, ex. witchy_calendar_events.json) — pas traduites en 3 langues comme le
reste de l'UI. Cohérent avec le fait qu'elles sont d'abord pensées comme matière première pour
le LLM (qui, lui, traduit dans la langue demandée) ; l'affichage direct en français est un bonus
secondaire, pas la même garantie multilingue que le reste du site.

Quatre sources, assemblées par ordre de priorité (voir compute_weekly_combination_lines) :
1. Combinaisons éditoriales composées (curated_combinations) — le contenu le plus riche.
2. Aspects rapide x lente formés cette semaine — banque de phrases CONCRÈTES par paire (v2,
   section 1), remplaçant l'ancienne formule par assemblage jugée trop répétitive.
3. Degrés remarquables détectés sur les 4 planètes rapides (section 3).
4. Position des planètes rapides dans leur signe (section 2, toujours présentes en dernier).

Les aspects ENTRE planètes rapides elles-mêmes (aspect_rapide_rapide, ex. Lune conjonction
Vénus) restent construits par l'ancienne formule combinable (fast_planet_themes +
aspect_modulators) : le doc v2 ne couvre que les paires rapide->lente, pas les paires
rapide-rapide, pour lesquelles aucune banque de phrases n'a été fournie.
"""

from __future__ import annotations

import zlib
from datetime import date as date_type

from app.core.reference_data import planets_in_signs_full, weekly_combinations_library
from app.core.zodiac import SIGNS_FR

_HARD_ASPECTS = {"square", "opposition"}
_HARMONIOUS_ASPECTS = {"trine", "sextile"}
# Classification bénéfique/exigeante des 4 planètes rapides pour la polarité de la conjonction
# (voir combination_phrase_bank.polarity_rule) — cohérente avec planet_categories.demanding de
# weekly_domain_scoring.json (Mars y est la seule planète rapide classée "exigeante").
_DEMANDING_FAST_PLANETS = {"Mars"}

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
# Section 1a : aspects ENTRE planètes rapides elles-mêmes — formule combinable
# (fast_planet_themes + aspect_modulators), non couverte par la banque de phrases v2.
# ---------------------------------------------------------------------------
def build_fast_fast_combination_lines(aspect_events: list[dict], kind: str) -> list[dict]:
    lib = weekly_combinations_library()
    fast_themes, modulators = lib["fast_planet_themes"], lib["aspect_modulators"]

    lines = []
    for aspect in aspect_events:
        fast, other_raw, aspect_type = aspect["planet_a"], aspect["planet_b"], aspect["aspect_type"]
        if fast not in fast_themes or other_raw not in fast_themes or aspect_type not in modulators:
            continue
        seed = f"{aspect['date']}|{fast}|{other_raw}|{aspect_type}"
        modulator = _stable_choice(modulators[aspect_type], seed)
        text = _capitalize(f"{fast_themes[fast]} {modulator} {fast_themes[other_raw]} cette semaine.")
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
# Section 1b : aspects planète rapide x planète/point lent — banque de phrases
# concrètes par paire (v2, section 1), sélection par rotation déterministe.
# ---------------------------------------------------------------------------
def _polarity_for(aspect_type: str, fast_planet: str) -> str | None:
    if aspect_type in _HARMONIOUS_ASPECTS:
        return "harmonieux"
    if aspect_type in _HARD_ASPECTS or aspect_type == "quincunx":
        return "tendu"
    if aspect_type == "conjunction":
        return "tendu" if fast_planet in _DEMANDING_FAST_PLANETS else "harmonieux"
    return None


def _rotation_index(fast_planet: str, slow_key: str, date_iso: str, n: int) -> int:
    """Sélection par rotation (voir combination_phrase_bank.note) : numéro de semaine ISO de la
    date exacte de l'aspect + hash déterministe (PAS Python hash(), randomisé par processus via
    PYTHONHASHSEED — zlib.crc32 à la place, voir _stable_choice) de la paire rapide/lente. Garde
    une même paire de retomber sur la même variante deux semaines de suite tant qu'il y a au
    moins 2 variantes, tout en restant déterministe (reproductible, testable)."""
    if n <= 1:
        return 0
    iso_week = date_type.fromisoformat(date_iso).isocalendar()[1]
    return (iso_week + zlib.crc32(f"{fast_planet}|{slow_key}".encode("utf-8"))) % n


def build_fast_slow_phrase_lines(aspect_events: list[dict], kind: str) -> list[dict]:
    bank = weekly_combinations_library()["combination_phrase_bank"]["banks"]

    lines = []
    for aspect in aspect_events:
        fast, other_raw, aspect_type = aspect["planet_a"], aspect["planet_b"], aspect["aspect_type"]
        other_key = _slow_point_key(other_raw)
        polarity = _polarity_for(aspect_type, fast)
        variants = bank.get(fast, {}).get(other_key, {}).get(polarity) if polarity else None
        if not variants:
            continue
        index = _rotation_index(fast, other_key, aspect["date"], len(variants))
        lines.append(
            {
                "kind": kind,
                "date": aspect["date"],
                "planet": fast,
                "planet_b": other_raw,
                "aspect_type": aspect_type,
                "aspect_type_fr": aspect["aspect_type_fr"],
                "score": aspect["score"],
                "text": variants[index],
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


def _aspect_targets(aspect_events: list[dict], planet: str, aspect_types: list[str]) -> set[str]:
    """Planètes/points visés par `planet` via l'un des `aspect_types` donnés — nom générique
    malgré `both_hard_aspect_same_target` (premier appelant historique) : sert aussi bien à des
    aspects tendus qu'harmonieux, voir `venus_mars_same_harmonious_aspect`."""
    return {e["planet_b"] for e in aspect_events if e["planet_a"] == planet and e["aspect_type"] in aspect_types}


def _near_lunation(witchy_events: list[dict], event_type: str) -> str | None:
    """Date (isoformat) de l'événement `event_type` ('nouvelle_lune'/'pleine_lune') de la
    semaine s'il y en a un, sinon None."""
    event = next((e for e in witchy_events if e["event_type"] == event_type), None)
    return event["event_date"] if event else None


def _lunation_forms_aspect(ctx: dict, event_type: str, aspect_types: list[str], near_days: int = 2) -> bool:
    """Doc v2, section 4 : Nouvelle/Pleine Lune de la semaine formant un aspect tendu/harmonieux
    à une planète lente, orbe serré. Les aspects rapide->lente de ce moteur sont des croisements
    EXACTS (pas d'orbe variable en continu, voir _scan_pair_aspect_events) : on approxime
    l'orbe serré par une proximité de date (± `near_days` jours) entre la lunaison et l'aspect
    exact de la Lune vers la planète lente concernée."""
    lunation_date = _near_lunation(ctx["witchy_events"], event_type)
    if lunation_date is None:
        return False
    lunation_jd = date_type.fromisoformat(lunation_date).toordinal()
    aspects = ctx["generational_aspects"] + ctx["moon_generational_aspects"]
    return any(
        e["planet_a"] == "Moon"
        and e["aspect_type"] in aspect_types
        and abs(date_type.fromisoformat(e["date"]).toordinal() - lunation_jd) <= near_days
        for e in aspects
    )


def _evaluate_curated_condition(condition: dict, ctx: dict) -> bool:
    kind = condition["type"]
    if kind == "retrograde":
        return _is_retrograde(ctx["fast_planets"], condition["planet"])
    if kind == "slow_in_signs":
        return any(ctx["slow_planet_signs"].get(planet) in condition["signs"] for planet in condition["planets"])
    if kind == "both_hard_aspect_same_target":
        planet_a, planet_b = condition["planets"]
        aspects = ctx["generational_aspects"] + ctx["moon_generational_aspects"]
        targets_a = _aspect_targets(aspects, planet_a, condition["aspect_types"])
        targets_b = _aspect_targets(aspects, planet_b, condition["aspect_types"])
        return bool(targets_a & targets_b)
    if kind == "hard_aspect":
        aspects = ctx["generational_aspects"] + ctx["moon_generational_aspects"]
        return any(
            e["planet_a"] == condition["planet_a"] and e["planet_b"] == condition["planet_b"] and e["aspect_type"] in _HARD_ASPECTS
            for e in aspects
        )
    if kind == "lunation_aspect":
        return _lunation_forms_aspect(ctx, condition["event_type"], condition["aspect_types"])
    if kind == "count_fast_slow_aspects_at_least":
        total = len(ctx["generational_aspects"]) + len(ctx["moon_generational_aspects"])
        return total >= condition["count"]
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
    witchy_events: list[dict],
) -> list[dict]:
    """~10 lignes ordonnées par priorité : (1) combinaisons éditoriales, (2) aspects Mercure/
    Vénus/Mars x lente de la semaine (banque de phrases par paire, v2 section 1), (3) aspects
    entre planètes rapides elles-mêmes (`transit_transit_aspects`, ex. Lune conjonction Vénus —
    formule combinable, réutilisant `fast_planet_themes` pour les DEUX opérandes, la banque de
    phrases v2 ne couvrant pas les paires rapide-rapide), (4) degrés remarquables, (5) aspects
    Lune x lente (la Lune en forme structurellement beaucoup plus souvent — elle change de
    signe tous les ~2,5 jours — donc reléguée en dernier parmi les aspects pour ne pas noyer le
    reste), (6) position des 4 planètes rapides dans leur signe. Les positions (6) sont
    TOUJOURS présentes en entier (voir doc source, section 5.1 point 4), même sans aucun signal
    notable : les catégories 1-5 se partagent le reste du budget de ~10 lignes plutôt que de les
    évincer."""
    ctx = {
        "fast_planets": fast_planets,
        "generational_aspects": generational_aspects,
        "moon_generational_aspects": moon_generational_aspects,
        "slow_planet_signs": slow_planet_signs,
        "witchy_events": witchy_events,
    }

    curated = build_curated_combination_lines(ctx)
    fast_slow_lines = build_fast_slow_phrase_lines(generational_aspects, kind="aspect_rapide_lente")
    fast_fast_lines = build_fast_fast_combination_lines(transit_transit_aspects, kind="aspect_rapide_rapide")
    degree_lines = build_critical_degree_lines(daily_fast_positions)
    moon_aspect_lines = build_fast_slow_phrase_lines(moon_generational_aspects, kind="aspect_rapide_lente")
    position_lines = build_position_lines(moon_path[0]["sign"], fast_planets)

    variable_budget = max(_MAX_LINES - len(position_lines), 0)
    variable = (curated + fast_slow_lines + fast_fast_lines + degree_lines + moon_aspect_lines)[:variable_budget]
    return variable + position_lines
