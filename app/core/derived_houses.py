"""Maisons dérivées ('maisons de maisons') : pour toute maison de référence N du natif
(ex. M7 = partenaire), N devient elle-même la maison 1 (identité) de la personne
représentée, N+1 sa maison 2 (ressources), ..., jusqu'à N-1 (modulo 12) qui est sa
maison 12. Pas de décalage d'un cran : la maison de référence est la maison 1 de la
personne représentée, pas la maison précédant celle-ci.

    derive_house(N, k) = ((N - 1 + k - 1) mod 12) + 1

où N = maison de référence, k = numéro de maison recherché chez la personne représentée.
Cette même fonction sert aussi de bloc de base à la dérivation de second ordre (voir
app.core.reference_data.derived_house_relations) : une relation de second ordre n'est
qu'un chaînage de deux appels à cette fonction, jamais une formule séparée.
"""

from __future__ import annotations

from app.core.reference_data import derived_house_relations, houses_meanings


def derive_house(reference_house: int, house_sought: int) -> int:
    """Maison natale correspondant à la maison `house_sought` (1-12) de la personne
    représentée par la maison de référence `reference_house` (1-12)."""
    return ((reference_house - 1 + house_sought - 1) % 12) + 1


def _house_meaning(house_number: int) -> dict:
    return next(h for h in houses_meanings()["houses"] if h["number"] == house_number)


def resolve_relation(relation_key: str) -> dict:
    """Résout une clé de relation (config `derived_house_relations.json`) vers sa maison
    de référence finale. Gère le premier ordre, les presets de second ordre (chaînage
    générique de deux appels à `derive_house`, jamais de cas codés en dur), et le
    sélecteur libre avancé sous la forme 'custom:N1:N2'."""
    if relation_key.startswith("custom:"):
        _, n1_str, n2_str = relation_key.split(":")
        n1, n2 = int(n1_str), int(n2_str)
        return {
            "relation_key": relation_key,
            "label": f"Relation personnalisée (maison {n2} de la maison {n1})",
            "reference_house": derive_house(n1, n2),
            "order": "second",
            "path_description": f"maison {n2} de la personne représentée par la maison {n1}",
            "prompt": None,
        }

    config = derived_house_relations()

    for rel in config["first_order"]:
        if rel["key"] == relation_key:
            return {
                "relation_key": relation_key,
                "label": rel["label"],
                "reference_house": rel["reference_house"],
                "order": "first",
                "path_description": None,
                "prompt": rel["prompt"],
            }

    for rel in config["second_order"]:
        if rel["key"] == relation_key:
            return {
                "relation_key": relation_key,
                "label": rel["label"],
                "reference_house": derive_house(rel["n1"], rel["n2"]),
                "order": "second",
                "path_description": rel["path_description"],
                "prompt": None,
            }

    raise KeyError(f"Relation inconnue : {relation_key}")


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
            natal_house = derive_house(reference_house, k)
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
