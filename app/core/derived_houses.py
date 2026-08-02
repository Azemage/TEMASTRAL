"""Maisons dérivées ('maisons de maisons') : pour toute maison de référence R du natif
(ex. M7 = partenaire), les maisons R+1 à R+12 (modulo 12) sont respectivement les
maisons 1 à 12 de la personne représentée par R. Ex. si R=7, ma maison 8 = sa maison 1
(identité), ma maison 9 = sa maison 2 (argent), ... ma maison 7 elle-même = sa maison 12.
"""

from __future__ import annotations

from app.core.reference_data import houses_meanings


def _house_meaning(house_number: int) -> dict:
    return next(h for h in houses_meanings()["houses"] if h["number"] == house_number)


def compute_derived_houses(planets: list[dict]) -> list[dict]:
    """planets : liste des positions planétaires natales (avec 'name' et 'house').
    Retourne, pour chacune des 12 maisons de référence possibles, le mapping complet
    vers les 12 maisons de la personne représentée, avec les planètes natales concernées.
    """
    planets_by_house: dict[int, list[str]] = {}
    for planet in planets:
        house = planet.get("house")
        if house is not None:
            planets_by_house.setdefault(house, []).append(planet["name"])

    results = []
    for reference_house in range(1, 13):
        mapping = []
        for k in range(1, 13):
            natal_house = ((reference_house - 1 + k) % 12) + 1
            meaning = _house_meaning(k)
            mapping.append(
                {
                    "derived_house_number": natal_house,
                    "represents_house": k,
                    "keyword": meaning["keyword"],
                    "themes": meaning["themes"],
                    "planets": planets_by_house.get(natal_house, []),
                }
            )
        results.append({"reference_house": reference_house, "mapping": mapping})

    return results
