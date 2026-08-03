from datetime import date, timedelta

from app.core.zodiacal_releasing import (
    SIGN_PERIOD_YEARS,
    compute_l1_periods,
    compute_zodiacal_releasing,
    subdivide,
)


def _assert_close(actual: date, expected: date, max_days: int = 2):
    # L'arithmétique en années fractionnaires (365.25 j/an) cumule de légers écarts
    # d'arrondi sur plusieurs périodes ; on tolère quelques jours plutôt que le jour exact.
    assert abs((actual - expected).days) <= max_days, f"{actual} trop loin de {expected}"

RULER_MAP = {
    "Aries": "Mars", "Taurus": "Venus", "Gemini": "Mercury", "Cancer": "Moon",
    "Leo": "Sun", "Virgo": "Mercury", "Libra": "Venus", "Scorpio": "Mars",
    "Sagittarius": "Jupiter", "Capricorn": "Saturn", "Aquarius": "Saturn", "Pisces": "Jupiter",
}


def test_l1_sequence_matches_validated_example():
    # Cahier de validation : Lot en Cancer né le 1995-01-01 -> Cancer(25) puis Lion(19) puis Vierge(20).
    birth_date = date(1995, 1, 1)
    periods = compute_l1_periods("Cancer", birth_date, date(2060, 1, 1))

    assert periods[0]["sign"] == "Cancer"
    assert periods[0]["start_date"] == date(1995, 1, 1)
    _assert_close(periods[0]["end_date"], date(2020, 1, 1))

    assert periods[1]["sign"] == "Leo"
    _assert_close(periods[1]["start_date"], date(2020, 1, 1))
    _assert_close(periods[1]["end_date"], date(2039, 1, 1))

    assert periods[2]["sign"] == "Virgo"
    _assert_close(periods[2]["end_date"], date(2059, 1, 1))


def test_l2_subdivision_matches_validated_example_first_six_signs():
    # Sous-période L2 à l'intérieur de Lion (2020-2039, 19 ans) : vérifie les 6 premiers
    # signes et durées contre l'exemple validé du document source (division par 12).
    periods = subdivide("Leo", date(2020, 1, 1), 19.0, level_n=1)
    signs_and_durations = [(p["sign"], round(p["duration_years"], 3)) for p in periods[:6]]

    assert signs_and_durations == [
        ("Leo", round(19 / 12, 3)),
        ("Virgo", round(20 / 12, 3)),
        ("Libra", round(8 / 12, 3)),
        ("Scorpio", round(15 / 12, 3)),
        ("Sagittarius", round(12 / 12, 3)),
        ("Capricorn", round(27 / 12, 3)),
    ]


def test_l2_subdivision_durations_sum_to_parent_duration():
    periods = subdivide("Leo", date(2020, 1, 1), 19.0, level_n=1)
    _assert_close(periods[-1]["end_date"], date(2020, 1, 1) + timedelta(days=round(19 * 365.25)))


def test_peak_period_flagged_for_angular_positions_relative_to_immediate_parent():
    # Depuis un parent en Bélier : positions 1,4,7,10 = Bélier, Cancer, Balance, Capricorne.
    periods = subdivide("Aries", date(2000, 1, 1), float(SIGN_PERIOD_YEARS["Aries"]), level_n=1)
    peak_signs = {p["sign"] for p in periods if p["is_peak_period"]}
    non_peak_signs = {p["sign"] for p in periods if not p["is_peak_period"]}
    assert {"Aries", "Cancer", "Libra", "Capricorn"} <= peak_signs
    assert "Taurus" in non_peak_signs  # 2e position, pas angulaire


def test_loosing_of_the_bond_triggers_for_long_parent_periods():
    # Aquarius = 30 ans, largement au-dessus du seuil de tour complet (~17.58) -> doit
    # déclencher une Libération du lien qui reprend au signe opposé (Leo).
    periods = subdivide("Aquarius", date(2000, 1, 1), float(SIGN_PERIOD_YEARS["Aquarius"]), level_n=1)
    loosing_periods = [p for p in periods if p["is_loosing_of_the_bond"]]
    assert len(loosing_periods) == 1
    assert loosing_periods[0]["sign"] == "Leo"  # signe opposé du Verseau

    total_duration = sum(p["duration_years"] for p in periods)
    assert abs(total_duration - 30.0) < 0.01


def test_no_loosing_of_the_bond_for_short_parent_periods():
    # Taurus = 8 ans, bien en-dessous du seuil (~17.58) -> jamais de Libération du lien.
    periods = subdivide("Taurus", date(2000, 1, 1), float(SIGN_PERIOD_YEARS["Taurus"]), level_n=1)
    assert not any(p["is_loosing_of_the_bond"] for p in periods)


def test_compute_zodiacal_releasing_returns_all_requested_lots_with_current_phase():
    result = compute_zodiacal_releasing(
        lot_signs={"Fortune": "Taurus", "Esprit": "Cancer", "Éros": "Libra"},
        birth_date=date(1990, 5, 15),
        ruler_map=RULER_MAP,
        as_of_date=date(2026, 8, 2),
    )
    assert result["edge_case_same_sign_applied"] is False
    assert set(result["lots"].keys()) == {"Fortune", "Esprit", "Éros"}
    for lot_result in result["lots"].values():
        assert lot_result["current_l1"] is not None
        assert lot_result["current_l2"] is not None
        assert lot_result["current_l1"]["start_date"] <= "2026-08-02" < lot_result["current_l1"]["end_date"]


def test_edge_case_same_sign_shifts_spirit_forward_by_one_sign():
    result = compute_zodiacal_releasing(
        lot_signs={"Fortune": "Leo", "Esprit": "Leo"},
        birth_date=date(1990, 5, 15),
        ruler_map=RULER_MAP,
        as_of_date=date(1990, 6, 1),
    )
    assert result["edge_case_same_sign_applied"] is True
    assert result["lots"]["Esprit"]["lot_sign"] == "Virgo"  # signe suivant Lion
    assert result["lots"]["Fortune"]["lot_sign"] == "Leo"


def test_same_sign_edge_case_does_not_apply_to_other_lot_pairs():
    # Le décalage documenté ne concerne que Fortune/Esprit ; deux autres lots dans le même
    # signe démarrent chacun leur propre séquence sans être modifiés.
    result = compute_zodiacal_releasing(
        lot_signs={"Éros": "Leo", "Mariage": "Leo"},
        birth_date=date(1990, 5, 15),
        ruler_map=RULER_MAP,
        as_of_date=date(1990, 6, 1),
    )
    assert result["edge_case_same_sign_applied"] is False
    assert result["lots"]["Éros"]["lot_sign"] == "Leo"
    assert result["lots"]["Mariage"]["lot_sign"] == "Leo"


def test_ruling_planet_included_in_serialized_periods():
    result = compute_zodiacal_releasing(
        lot_signs={"Fortune": "Leo", "Esprit": "Cancer"},
        birth_date=date(1990, 5, 15),
        ruler_map=RULER_MAP,
        as_of_date=date(1990, 6, 1),
    )
    assert result["lots"]["Fortune"]["current_l1"]["ruling_planet"] == "Sun"
