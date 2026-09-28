"""Analyse déterministe du DEGRÉ (0-29) qu'occupe un point dans son signe — vient affiner la
lecture du signe/maison sans jamais les remplacer. Quatre couches, chacune avec son propre
statut épistémique (voir doc source degree_theory.json) :
1. Degré d'exaltation — un point exact par planète, un signe précis (héritage babylonien/
   hellénistique/Ptolémée). [Documenté, classique]
2. Degrés critiques — motif répété selon la modalité du signe (cardinal/fixe/mutable), pas
   propre à une planète en particulier. [Documenté, systématisé au XXe siècle]
3. Degré anarétique (29°) et entrée pure (0°) — cas limites, hors du cycle thématique.
   [Documenté, très cité en astrologie moderne]
4. Thème du degré (théorie des degrés, cycle 1-28) — un signe superposé et un thème par degré,
   distinct du signe réel du point. [Documenté comme système, mais d'origine populaire/XXe
   siècle — Symboles Sabians de Jones/Wheeler 1925, popularisés par Rudhyar 1973 — jamais à
   présenter comme une règle classique établie]
5. Prédisposition dissolution/évasion aux degrés 12 et 24 (thème de degré Poissons, deux
   passages) — [Synthèse interprétative, appuyée sur une association de signe bien documentée
   (Poissons/Neptune = dissolution des limites, évasion, idéalisation), voir
   dissolution_predisposition_degrees dans degree_theory.json]. TOUJOURS présentée comme une
   prédisposition/sensibilité à surveiller avec bienveillance, jamais un diagnostic ni une
   fatalité — c'est le seul niveau de synthèse fait ici plutôt que laissé au modèle de
   lecture, car il demandait explicitement d'être conservé plutôt qu'omis."""

from __future__ import annotations

from app.core.reference_data import degree_theory
from app.core.zodiac import MODALITIES, SIGNS_FR


def _exaltation_points() -> dict[str, tuple[str, int]]:
    return {e["planet"]: (e["sign"], e["degree"]) for e in degree_theory()["exaltation_points"]}


def _critical_degrees_by_modality() -> dict[str, set[int]]:
    return {modality: set(degrees) for modality, degrees in degree_theory()["critical_degrees_by_modality"].items()}


def _degree_theme_cycle() -> dict[int, tuple[str, str]]:
    return {entry["degree"]: (entry["sign"], entry["theme"]) for entry in degree_theory()["degree_theme_cycle"]}


def _dissolution_predisposition_notes() -> dict[int, str]:
    entries = degree_theory()["dissolution_predisposition_degrees"]
    return {12: entries["12"], 24: entries["24"]}


def analyze_degree(planet_name: str, sign: str, raw_degree_in_sign: float) -> dict:
    """`raw_degree_in_sign` doit être la valeur NON arrondie (0 <= x < 30) telle que retournée
    par `zodiac.sign_and_degree` — un arrondi préalable pourrait faire glisser un point tout
    proche d'une frontière (ex. 17.996°) vers la mauvaise bande de degré (18 au lieu de 17)."""
    degree_value = int(raw_degree_in_sign)  # floor : raw_degree_in_sign est toujours positif

    result: dict = {
        "planet": planet_name,
        "sign": sign,
        "sign_fr": SIGNS_FR[sign],
        "degree_value": degree_value,
        "is_pure_entry": degree_value == 0,
        "is_anaretic": degree_value == 29,
        "is_critical_degree": degree_value in _critical_degrees_by_modality()[MODALITIES[sign]],
        "degree_theme_sign": None,
        "degree_theme_sign_fr": None,
        "degree_theme_label": None,
        "is_exact_exaltation": False,
        "dissolution_predisposition_note": None,
    }

    theme_cycle = _degree_theme_cycle()
    if degree_value in theme_cycle:
        theme_sign, theme_label = theme_cycle[degree_value]
        result["degree_theme_sign"] = theme_sign
        result["degree_theme_sign_fr"] = SIGNS_FR[theme_sign]
        result["degree_theme_label"] = theme_label

    exaltation = _exaltation_points().get(planet_name)
    if exaltation is not None and exaltation == (sign, degree_value):
        result["is_exact_exaltation"] = True

    dissolution_notes = _dissolution_predisposition_notes()
    if degree_value in dissolution_notes:
        result["dissolution_predisposition_note"] = dissolution_notes[degree_value]

    return result
