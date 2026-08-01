"""Calcul des dispositeurs (maîtrise planétaire) : maîtres, chaînes, réceptions mutuelles."""

from __future__ import annotations

from app.core.reference_data import ruler_map

CLASSIC_PLANETS = [
    "Sun", "Moon", "Mercury", "Venus", "Mars",
    "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto",
]

# Seuils de proportion de chaînes convergeant vers un même dispositeur final,
# au-delà desquels le pattern est jugé notable / fort dans le thème.
CONVERGENCE_NOTABLE_RATIO = 0.5
CONVERGENCE_STRONG_RATIO = 0.8


def _compute_convergence(chains: list[dict]) -> dict:
    """Identifie le(s) dispositeur(s) final(aux) vers lesquels convergent le plus de chaînes.

    Une convergence forte (ex. 9 planètes sur 10 qui se disposent finalement dans la même
    planète) est un pattern astrologique notable : cette planète agit comme 'clé de voûte'
    du thème. Les chaînes en boucle (final_dispositor=None) ne comptent pour aucun dispositeur.
    """
    counts: dict[str, int] = {}
    for chain in chains:
        final = chain["final_dispositor"]
        if final is None:
            continue
        counts[final] = counts.get(final, 0) + 1

    total_chains = len(chains)
    if not counts or total_chains == 0:
        return {
            "final_dispositor_counts": counts,
            "dominant_dispositor": None,
            "dominant_count": 0,
            "total_chains": total_chains,
            "convergence_ratio": 0.0,
            "level": "aucune",
        }

    dominant = max(counts, key=counts.get)
    dominant_count = counts[dominant]
    ratio = dominant_count / total_chains

    if ratio >= CONVERGENCE_STRONG_RATIO:
        level = "forte"
    elif ratio >= CONVERGENCE_NOTABLE_RATIO:
        level = "notable"
    else:
        level = "aucune"

    return {
        "final_dispositor_counts": counts,
        "dominant_dispositor": dominant,
        "dominant_count": dominant_count,
        "total_chains": total_chains,
        "convergence_ratio": round(ratio, 2),
        "level": level,
    }


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
        "convergence": _compute_convergence(chains),
    }
