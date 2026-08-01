"""Calcul des dispositeurs (maîtrise planétaire) : maîtres, chaînes, réceptions mutuelles."""

from __future__ import annotations

from app.core.reference_data import ruler_map

CLASSIC_PLANETS = [
    "Sun", "Moon", "Mercury", "Venus", "Mars",
    "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto",
]


def compute_dispositors(planet_signs: dict[str, str], system: str) -> dict:
    """planet_signs : {nom_planète: signe_occupé} pour les 10 planètes classiques.
    system : 'traditional' ou 'modern', détermine la chaîne de maîtrise suivie.
    """
    rmap = ruler_map(system)
    traditional_map = ruler_map("traditional")
    modern_map = ruler_map("modern")

    dispositors = []
    for planet in CLASSIC_PLANETS:
        if planet not in planet_signs:
            continue
        sign = planet_signs[planet]
        ruler = rmap.get(sign)
        dispositors.append(
            {
                "planet": planet,
                "sign_occupied": sign,
                "rulers": {"traditional": traditional_map.get(sign), "modern": modern_map.get(sign)},
                "self_disposed": ruler == planet,
            }
        )

    chains = []
    for planet in CLASSIC_PLANETS:
        if planet not in planet_signs:
            continue
        chain = [planet]
        current = planet
        chain_type = "linear"
        final: str | None = None
        for _ in range(len(CLASSIC_PLANETS) + 1):
            sign = planet_signs.get(current)
            if sign is None:
                break
            ruler = rmap.get(sign)
            if ruler is None:
                break
            if ruler == current:
                final = ruler
                break
            if ruler in chain:
                chain.append(ruler)
                chain_type = "loop"
                final = None
                break
            chain.append(ruler)
            current = ruler
        chains.append({"chain": chain, "final_dispositor": final, "type": chain_type})

    mutual_receptions = []
    seen_pairs: set[frozenset[str]] = set()
    for p1 in CLASSIC_PLANETS:
        if p1 not in planet_signs:
            continue
        sign1 = planet_signs[p1]
        r1 = rmap.get(sign1)
        if r1 is None or r1 == p1 or r1 not in planet_signs:
            continue
        sign2 = planet_signs[r1]
        r2 = rmap.get(sign2)
        if r2 == p1:
            pair_key = frozenset({p1, r1})
            if pair_key not in seen_pairs:
                seen_pairs.add(pair_key)
                mutual_receptions.append({"planets": [p1, r1], "signs": [sign1, sign2], "system": system})

    return {
        "dispositors": dispositors,
        "dispositor_chains": chains,
        "mutual_receptions": mutual_receptions,
    }
