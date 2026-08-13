"""Personnalisation des lignes d'astrocartographie par croisement avec le thème natal.

Une même ligne (ex. Jupiter-MC) ne signifie pas la même chose pour deux personnes : ce module
joint des données DÉJÀ calculées ailleurs dans l'app (dignités, aspects natals, dispositeurs,
profection annuelle, Libération Zodiacale) à chaque ligne proche du lieu analysé, en 3 couches
qui s'ajoutent à la signification générique de base :

1. Condition natale de la planète (dignité, aspects, rétrogradation) — la MÊME ligne ne "tient
   pas sa promesse" de la même façon selon l'état de la planète au natal.
2. Thèmes confirmés du thème (dispositeur final dominant, maître de l'Ascendant, stellium) —
   la couche la plus personnalisante : si la planète de la ligne est déjà un pilier de
   l'identité de la personne (pas juste "une planète parmi d'autres"), la ligne mérite une
   mise en avant nettement plus forte.
3. Pertinence temporelle (maître de l'année de profection, période de Libération Zodiacale
   active) — le thème natal ne change jamais, mais certaines lignes sont activées MAINTENANT
   plutôt qu'à titre de potentiel de fond valable "un jour".

Le score de priorité qui en résulte est une simple somme pondérée (fonction déterministe, pas
une décision du LLM) — il sert uniquement à trier/prioriser l'affichage, jamais à remplacer
l'interprétation elle-même, qui reste du ressort du modèle de langage.
"""

from __future__ import annotations

from app.core.dispositors import CLASSIC_PLANETS
from app.core.reference_data import dignities as dignities_reference
from app.core.reference_data import ruler_map

HARMONIOUS_ASPECT_TYPES = {"trine", "sextile"}
CHALLENGING_ASPECT_TYPES = {"square", "opposition"}

# Poids (arbitraires mais documentés) des différents signaux composant le score de priorité.
_DIGNITY_WEIGHT = 1
_MAX_ASPECT_WEIGHT = 3
_RETROGRADE_WEIGHT = 0.5
_DOMINANT_DISPOSITOR_STRONG_WEIGHT = 4
_DOMINANT_DISPOSITOR_NOTABLE_WEIGHT = 2
_ASCENDANT_RULER_WEIGHT = 3
_STELLIUM_WEIGHT = 3
_YEAR_RULER_WEIGHT = 3
_ZODIACAL_RELEASING_ACTIVE_WEIGHT = 2

# Lots classiques (piliers hellénistiques) considérés pour la couche de Libération Zodiacale —
# pas les 17 lots du thème, qui rendraient presque toutes les planètes "actives" en permanence
# et diluer.aient le signal.
_ZODIACAL_RELEASING_LOTS = ("Fortune", "Esprit")


def compute_dignity(planet: str, sign: str | None) -> str:
    """'domicile' | 'exaltation' | 'exil' | 'chute' | 'pérégrin'."""
    if sign is None:
        return "pérégrin"
    entry = next((d for d in dignities_reference()["dignities"] if d["planet"] == planet), None)
    if entry is None:
        return "pérégrin"
    if sign in entry["domicile"]:
        return "domicile"
    if sign == entry["exaltation"]:
        return "exaltation"
    if sign in entry["detriment"]:
        return "exil"
    if sign == entry["fall"]:
        return "chute"
    return "pérégrin"


def _planet_aspects(planet: str, aspects: list[dict]) -> list[dict]:
    """Aspects natals impliquant `planet`, triés du plus serré au plus large."""
    result = []
    for aspect in aspects:
        if aspect["planet1"] == planet:
            other = aspect["planet2"]
        elif aspect["planet2"] == planet:
            other = aspect["planet1"]
        else:
            continue
        if aspect["type"] in HARMONIOUS_ASPECT_TYPES:
            quality = "harmonious"
        elif aspect["type"] in CHALLENGING_ASPECT_TYPES:
            quality = "challenging"
        else:
            quality = "neutral"
        result.append(
            {
                "other_planet": other,
                "type": aspect["type"],
                "type_fr": aspect["type_fr"],
                "orb": aspect["orb"],
                "quality": quality,
            }
        )
    return sorted(result, key=lambda a: a["orb"])


def compute_natal_condition(
    planet: str, planet_signs: dict[str, str], planet_retrograde: dict[str, bool], aspects: list[dict]
) -> dict:
    """Couche 2 : dignité, rétrogradation, et qualité d'ensemble des aspects natals de la
    planète (orbe <= 5° pour compter comme significatif). `friction_with_malefic` signale
    spécifiquement un aspect dur à Mars/Saturne, le cas le plus important à nommer plutôt
    qu'ignorer d'après le principe de personnalisation."""
    sign = planet_signs.get(planet)
    dignity = compute_dignity(planet, sign)
    planet_aspects = _planet_aspects(planet, aspects)
    significant = [a for a in planet_aspects if a["quality"] != "neutral" and a["orb"] <= 5]
    has_harmonious = any(a["quality"] == "harmonious" for a in significant)
    has_challenging = any(a["quality"] == "challenging" for a in significant)
    friction_with_malefic = any(
        a["quality"] == "challenging" and a["other_planet"] in ("Mars", "Saturn") for a in significant
    )

    if has_harmonious and has_challenging:
        aspect_quality = "mixed"
    elif has_challenging:
        aspect_quality = "challenging"
    elif has_harmonious:
        aspect_quality = "favorable"
    else:
        aspect_quality = "neutral"

    return {
        "dignity": dignity,
        "retrograde": planet_retrograde.get(planet, False),
        "aspects": planet_aspects,
        "aspect_quality": aspect_quality,
        "friction_with_malefic": friction_with_malefic,
        "_priority_weight": (
            (_DIGNITY_WEIGHT if dignity != "pérégrin" else 0)
            + min(len(significant), _MAX_ASPECT_WEIGHT)
            + (_RETROGRADE_WEIGHT if planet_retrograde.get(planet, False) else 0)
        ),
    }


def _stellium_groups(planets: list[dict], key: str) -> list[set[str]]:
    groups: dict[object, list[str]] = {}
    for p in planets:
        if p["name"] not in CLASSIC_PLANETS:
            continue
        value = p.get(key)
        if value is None:
            continue
        groups.setdefault(value, []).append(p["name"])
    return [set(names) for names in groups.values() if len(names) >= 3]


def _is_in_stellium(planet: str, planets: list[dict]) -> bool:
    """Amas d'au moins 3 planètes classiques dans le même signe OU la même maison."""
    return any(planet in group for key in ("sign", "house") for group in _stellium_groups(planets, key))


def compute_theme_confirme(planet: str, chart_data: dict) -> dict:
    """Couche 3 (la plus personnalisante) : la planète est-elle déjà un pilier identifié de
    l'identité du thème (dispositeur final dominant, maître de l'Ascendant, membre d'un
    stellium) ? `reasons` est une liste de justifications en français, prête à être citée
    telle quelle par le prompt LLM."""
    reasons: list[str] = []
    weight = 0.0

    for system_key, system_label in (("dispositors_traditional", "traditionnel"), ("dispositors_modern", "moderne")):
        convergence = chart_data[system_key]["convergence"]
        if convergence["dominant_dispositor"] != planet:
            continue
        if convergence["level"] == "forte":
            reasons.append(f"dispositeur final dominant du thème (système {system_label}, convergence forte)")
            weight += _DOMINANT_DISPOSITOR_STRONG_WEIGHT
        elif convergence["level"] == "notable":
            reasons.append(f"dispositeur final dominant du thème (système {system_label}, convergence notable)")
            weight += _DOMINANT_DISPOSITOR_NOTABLE_WEIGHT

    ascendant_sign = chart_data["angles"]["ascendant"]["sign"]
    ascendant_rulers = {ruler_map("traditional").get(ascendant_sign), ruler_map("modern").get(ascendant_sign)}
    if planet in ascendant_rulers:
        reasons.append("maître de l'Ascendant")
        weight += _ASCENDANT_RULER_WEIGHT

    if _is_in_stellium(planet, chart_data["planets"]):
        reasons.append("fait partie d'un amas planétaire (stellium) du thème")
        weight += _STELLIUM_WEIGHT

    return {"present": bool(reasons), "reasons": reasons, "_priority_weight": weight}


def compute_temporal_pertinence(planet: str, profection: dict | None, zr_data: dict | None) -> dict:
    """Couche 4 : cette planète est-elle activée par une technique de timing MAINTENANT (à la
    date de référence de la lecture) ? Sans activation, la ligne reste un potentiel de fond
    valable mais pas une fenêtre d'actualité à signaler comme telle."""
    reasons: list[str] = []
    weight = 0.0

    if profection and profection.get("year_ruler") == planet:
        reasons.append("maître de l'année de profection en cours")
        weight += _YEAR_RULER_WEIGHT

    if zr_data:
        for lot_name in _ZODIACAL_RELEASING_LOTS:
            lot_zr = zr_data.get("lots", {}).get(lot_name)
            if not lot_zr:
                continue
            current_l1 = lot_zr.get("current_l1")
            if current_l1 and current_l1["ruling_planet"] == planet:
                reasons.append(f"période L1 de Libération Zodiacale actuellement active (Lot de {lot_name})")
                weight += _ZODIACAL_RELEASING_ACTIVE_WEIGHT
            current_l2 = lot_zr.get("current_l2")
            if current_l2 and current_l2["ruling_planet"] == planet:
                reasons.append(f"sous-période L2 de Libération Zodiacale actuellement active (Lot de {lot_name})")
                weight += _ZODIACAL_RELEASING_ACTIVE_WEIGHT

    if weight >= _YEAR_RULER_WEIGHT:
        urgency = "élevé"
    elif weight > 0:
        urgency = "modéré"
    else:
        urgency = "potentiel de fond"

    return {"active": bool(reasons), "reasons": reasons, "urgency": urgency, "_priority_weight": weight}


def personalize_nearby_lines(
    nearby_lines: list[dict],
    chart_data: dict,
    significations: dict,
    profection: dict | None = None,
    zr_data: dict | None = None,
) -> list[dict]:
    """Point d'entrée principal : enrichit chaque ligne proche (`{"planet","line_type",
    "distance_km"}`, déjà calculée par `analyze_nearby_lines`) des 3 couches de personnalisation
    ci-dessus, calcule un score de priorité déterministe, et trie le résultat du plus au moins
    prioritaire. Les couches 2/3/4 sont propres à la PLANÈTE (pas au type de ligne) : mises en
    cache pour n'être calculées qu'une fois même si les 4 lignes ASC/DC/MC/IC d'une même
    planète sont toutes proches du lieu."""
    planet_signs = {p["name"]: p["sign"] for p in chart_data["planets"] if p["name"] in CLASSIC_PLANETS}
    planet_retrograde = {p["name"]: p.get("retrograde", False) for p in chart_data["planets"]}
    aspects = chart_data["aspects"]

    natal_condition_cache: dict[str, dict] = {}
    theme_confirme_cache: dict[str, dict] = {}
    temporal_cache: dict[str, dict] = {}

    personalized = []
    for match in nearby_lines:
        planet = match["planet"]
        if planet not in natal_condition_cache:
            natal_condition_cache[planet] = compute_natal_condition(planet, planet_signs, planet_retrograde, aspects)
        if planet not in theme_confirme_cache:
            theme_confirme_cache[planet] = compute_theme_confirme(planet, chart_data)
        if planet not in temporal_cache:
            temporal_cache[planet] = compute_temporal_pertinence(planet, profection, zr_data)

        natal_condition = natal_condition_cache[planet]
        theme_confirme = theme_confirme_cache[planet]
        temporal = temporal_cache[planet]
        priority_score = round(
            natal_condition["_priority_weight"] + theme_confirme["_priority_weight"] + temporal["_priority_weight"], 2
        )

        personalized.append(
            {
                "planet": planet,
                "line_type": match["line_type"],
                "distance_km": match["distance_km"],
                "base_meaning": significations.get(planet, {}).get(match["line_type"], ""),
                "natal_condition": {k: v for k, v in natal_condition.items() if not k.startswith("_")},
                "theme_confirme_lie": {k: v for k, v in theme_confirme.items() if not k.startswith("_")},
                "pertinence_temporelle": {k: v for k, v in temporal.items() if not k.startswith("_")},
                "priority_score": priority_score,
            }
        )

    personalized.sort(key=lambda p: p["priority_score"], reverse=True)
    return personalized
