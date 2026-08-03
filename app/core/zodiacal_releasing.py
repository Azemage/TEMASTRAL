"""Libération zodiacale (Zodiacal Releasing / Aphesis) — technique hellénistique de
timing à partir des Lots de Fortune et d'Esprit (Vettius Valens, reconstituée par R. Hand
/ C. Brennan). Implémente les niveaux L1 (phases, plusieurs années) et L2 (sous-phases,
proportionnellement en mois), avec gestion de la 'Libération du lien' pour les périodes
dont la durée dépasse un tour complet du cycle (~17,58 ans à l'échelle L1).

Voir app/reference_data/zodiacal_releasing_algorithm.json pour l'algorithme source et son
exemple de validation.
"""

from __future__ import annotations

from datetime import date as date_type
from datetime import timedelta

from app.core.reference_data import zodiacal_releasing_algorithm
from app.core.zodiac import SIGNS, SIGNS_FR, sign_index, signs_distance

_ALGO = zodiacal_releasing_algorithm()
SIGN_PERIOD_YEARS: dict[str, int] = _ALGO["step_0_years_table"]["table"]
ANGULAR_POSITIONS = {1, 4, 7, 10}
DAYS_PER_YEAR = 365.25


def _next_sign(sign: str) -> str:
    return SIGNS[(sign_index(sign) + 1) % 12]


def _opposite_sign(sign: str) -> str:
    return SIGNS[(sign_index(sign) + 6) % 12]


def _is_peak_period(parent_sign: str, child_sign: str) -> bool:
    return signs_distance(parent_sign, child_sign) in ANGULAR_POSITIONS


class _DateAnchor:
    """Convertit un décalage en années (float) depuis une date d'ancrage en date calendaire,
    avec un seul arrondi par appel plutôt que d'enchaîner des additions tronquées — évite
    la dérive cumulative qu'introduirait `date + timedelta` répété période après période.
    """

    def __init__(self, anchor: date_type):
        self._anchor = anchor

    def at(self, elapsed_years: float) -> date_type:
        return self._anchor + timedelta(days=round(elapsed_years * DAYS_PER_YEAR))


def compute_l1_periods(start_sign: str, birth_date: date_type, min_end_date: date_type) -> list[dict]:
    """Périodes L1 depuis la naissance jusqu'à couvrir au moins `min_end_date`."""
    anchor = _DateAnchor(birth_date)
    periods = []
    sign = start_sign
    elapsed = 0.0
    while anchor.at(elapsed) < min_end_date:
        duration = float(SIGN_PERIOD_YEARS[sign])
        start_date = anchor.at(elapsed)
        elapsed += duration
        end_date = anchor.at(elapsed)
        periods.append(
            {
                "level": 1,
                "sign": sign,
                "start_date": start_date,
                "end_date": end_date,
                "duration_years": round(duration, 3),
                "parent_sign": None,
                "is_peak_period": False,
                "is_loosing_of_the_bond": False,
            }
        )
        sign = _next_sign(sign)
    return periods


def subdivide(parent_sign: str, parent_start: date_type, parent_duration_years: float, level_n: int) -> list[dict]:
    """Sous-périodes de niveau L(n+1) à l'intérieur d'une période parente L(n).
    level_n=1 calcule L2 (mois), level_n=2 calculerait L3 (semaines) — non exposé pour l'instant.
    """
    divisor = 12**level_n
    anchor = _DateAnchor(parent_start)
    results: list[dict] = []

    def run_lap(start_sign: str, lap_start_elapsed: float, remaining: float, mark_first_as_loosing: bool) -> float:
        sign = start_sign
        elapsed = lap_start_elapsed
        first = True
        for _ in range(12):
            duration = SIGN_PERIOD_YEARS[sign] / divisor
            step = min(duration, remaining)
            start_date = anchor.at(elapsed)
            elapsed += step
            end_date = anchor.at(elapsed)
            results.append(
                {
                    "level": level_n + 1,
                    "sign": sign,
                    "start_date": start_date,
                    "end_date": end_date,
                    "duration_years": round(step, 4),
                    "parent_sign": parent_sign,
                    "is_peak_period": _is_peak_period(parent_sign, sign),
                    "is_loosing_of_the_bond": mark_first_as_loosing and first,
                }
            )
            remaining -= step
            if remaining <= 1e-9:
                return 0.0, elapsed
            sign = _next_sign(sign)
            first = False
        return remaining, elapsed

    remaining_after_lap1, elapsed_after_lap1 = run_lap(parent_sign, 0.0, parent_duration_years, mark_first_as_loosing=False)
    if remaining_after_lap1 > 1e-9:
        # Libération du lien : la période parente dépasse un tour complet, on reprend au
        # signe opposé plutôt que de refermer la boucle sur le signe de départ.
        run_lap(_opposite_sign(parent_sign), elapsed_after_lap1, remaining_after_lap1, mark_first_as_loosing=True)

    return results


def _current_period(periods: list[dict], as_of_date: date_type) -> dict | None:
    for period in periods:
        if period["start_date"] <= as_of_date < period["end_date"]:
            return period
    return periods[-1] if periods else None


def _serialize(period: dict, ruler_map: dict[str, str]) -> dict:
    return {
        "level": period["level"],
        "sign": period["sign"],
        "sign_fr": SIGNS_FR[period["sign"]],
        "start_date": period["start_date"].isoformat(),
        "end_date": period["end_date"].isoformat(),
        "duration_years": period["duration_years"],
        "parent_sign": period["parent_sign"],
        "is_peak_period": period["is_peak_period"],
        "is_loosing_of_the_bond": period["is_loosing_of_the_bond"],
        "ruling_planet": ruler_map[period["sign"]],
    }


def _compute_for_lot(
    start_sign: str,
    birth_date: date_type,
    as_of_date: date_type,
    lookahead_years: float,
    ruler_map: dict[str, str],
) -> dict:
    min_end_date = _DateAnchor(as_of_date).at(lookahead_years)
    l1_periods = compute_l1_periods(start_sign, birth_date, min_end_date)
    current_l1 = _current_period(l1_periods, as_of_date)

    l2_periods: list[dict] = []
    current_l2 = None
    if current_l1 is not None:
        l2_periods = subdivide(current_l1["sign"], current_l1["start_date"], current_l1["duration_years"], level_n=1)
        current_l2 = _current_period(l2_periods, as_of_date)

    return {
        "lot_sign": start_sign,
        "l1_periods": [_serialize(p, ruler_map) for p in l1_periods],
        "current_l1": _serialize(current_l1, ruler_map) if current_l1 else None,
        "current_l1_l2_periods": [_serialize(p, ruler_map) for p in l2_periods],
        "current_l2": _serialize(current_l2, ruler_map) if current_l2 else None,
    }


FORTUNE_LOT_NAME = "Fortune"
SPIRIT_LOT_NAME = "Esprit"


def compute_zodiacal_releasing(
    lot_signs: dict[str, str],
    birth_date: date_type,
    ruler_map: dict[str, str],
    as_of_date: date_type | None = None,
    lookahead_years: float = 5,
) -> dict:
    """Calcule la Libération Zodiacale pour un ensemble quelconque de lots (chacun démarre
    sa propre séquence de phases depuis son signe natal). Le document source ne définit
    formellement la technique que pour les lots Fortune et Esprit (piliers hellénistiques
    classiques, corps/vie matérielle vs esprit/action) ; son extension aux autres lots ici
    est une généralisation du même algorithme, à lire comme exploratoire pour ces lots-là.
    """
    as_of_date = as_of_date or date_type.today()

    effective_signs = dict(lot_signs)
    edge_case_applied = False
    if (
        FORTUNE_LOT_NAME in lot_signs
        and SPIRIT_LOT_NAME in lot_signs
        and lot_signs[FORTUNE_LOT_NAME] == lot_signs[SPIRIT_LOT_NAME]
    ):
        # Cas particulier documenté : Fortune et Esprit dans le même signe -> décaler
        # Esprit d'un signe avant de démarrer le calcul.
        effective_signs[SPIRIT_LOT_NAME] = _next_sign(lot_signs[SPIRIT_LOT_NAME])
        edge_case_applied = True

    return {
        "as_of_date": as_of_date.isoformat(),
        "edge_case_same_sign_applied": edge_case_applied,
        "lots": {
            name: _compute_for_lot(sign, birth_date, as_of_date, lookahead_years, ruler_map)
            for name, sign in effective_signs.items()
        },
    }
