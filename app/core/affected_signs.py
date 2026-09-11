"""Signes natals les plus sensibles à un évènement de la météo de la semaine (aspect entre deux
planètes en transit, ingrès, station), déduits par pure géométrie zodiacale (élément/modalité)
— PAS par comparaison à un thème réel. Sert à personnaliser le climat collectif ("si vous avez
tel placement natal dans un de ces signes, cette semaine vous concerne plus particulièrement")
sans connaître le thème du lecteur, contrairement à la couche personnelle (`personal_highlights`,
qui elle compare vraiment aux planètes natales — voir weekly_weather_domains.py).

Principe : deux signes en carré ou en opposition partagent toujours la même modalité (les 4
signes cardinaux/fixes/mutables sont mutuellement à 90° ou 180°) ; deux signes en trigone
partagent toujours le même élément (les 3 signes d'un élément sont mutuellement à 120°) ; deux
signes en sextile partagent toujours la même polarité mais un élément différent (ex. Bélier/
Gémeaux : feu/air, tous deux masculins). La conjonction et les aspects mineurs (dont l'angle
n'est pas un multiple de 60°) n'ont pas de "groupe" propre : on retombe sur les signes exacts
impliqués."""

from __future__ import annotations

from app.core.zodiac import ELEMENTS, MODALITIES, SIGNS

_POLARITY = {"fire": "positive", "air": "positive", "earth": "negative", "water": "negative"}


def _modality_group(sign: str) -> list[str]:
    modality = MODALITIES[sign]
    return [s for s in SIGNS if MODALITIES[s] == modality]


def _element_group(sign: str) -> list[str]:
    element = ELEMENTS[sign]
    return [s for s in SIGNS if ELEMENTS[s] == element]


def _polarity_group(sign: str) -> list[str]:
    polarity = _POLARITY[ELEMENTS[sign]]
    return [s for s in SIGNS if _POLARITY[ELEMENTS[s]] == polarity]


def affected_signs_for_aspect(sign_a: str, sign_b: str, aspect_type: str) -> dict:
    """Signes natals les plus sensibles à un aspect exact entre deux planètes en transit
    (`primary` seulement : un aspect majeur n'a pas d'axe "secondaire" distinct comme un
    évènement ponctuel — le groupe de signes EST déjà toute l'information)."""
    if aspect_type in ("square", "opposition"):
        return {"primary": _modality_group(sign_a), "secondary": []}
    if aspect_type == "trine":
        return {"primary": _element_group(sign_a), "secondary": []}
    if aspect_type == "sextile":
        return {"primary": _polarity_group(sign_a), "secondary": []}
    # Conjonction (les deux signes sont presque toujours identiques) et aspects mineurs.
    return {"primary": sorted({sign_a, sign_b}, key=SIGNS.index), "secondary": []}


def affected_signs_for_position(sign: str) -> dict:
    """Signes sensibles à un évènement ponctuel (ingrès, station, lunaison...) : le signe
    traversé (`primary`) et son axe opposé (`secondary`), classiquement activé en écho."""
    opposite = SIGNS[(SIGNS.index(sign) + 6) % 12]
    return {"primary": [sign], "secondary": [opposite]}


def emphasis_points(*planets: str | None) -> list[str]:
    """Points natals à regarder en priorité pour un évènement donné, pour la personnalisation
    "si vous avez tel placement..." : les planètes directement impliquées (dédupliquées, dans
    l'ordre), puis l'Ascendant — toujours pertinent, quel que soit l'évènement, car c'est le
    point le plus individualisé du thème."""
    points = [p for p in dict.fromkeys(planets) if p]
    points.append("Ascendant")
    return points
