from datetime import date

from app.core.profections import compute_profection


def test_age_zero_profects_the_first_house_on_ascendant_sign():
    result = compute_profection(date(1990, 5, 15), "Virgo", date(1990, 6, 1))
    assert result["age"] == 0
    assert result["profected_house"] == 1
    assert result["profected_sign"] == "Virgo"
    assert result["year_ruler"] == "Mercury"


def test_profection_advances_one_house_per_year():
    result = date_at_age(1)
    assert result["profected_house"] == 2
    assert result["profected_sign"] == "Libra"  # signe suivant Vierge
    assert result["year_ruler"] == "Venus"


def date_at_age(age: int) -> dict:
    return compute_profection(date(1990, 5, 15), "Virgo", date(1990 + age, 6, 1))


def test_profection_cycles_back_after_twelve_years():
    result = compute_profection(date(1990, 5, 15), "Virgo", date(2026, 8, 2))  # 36 ans = 3x12
    assert result["age"] == 36
    assert result["profected_house"] == 1
    assert result["profected_sign"] == "Virgo"


def test_birthday_not_yet_reached_this_year_uses_previous_age():
    # Né le 15 mai ; le 1er janvier, l'anniversaire de l'année n'a pas encore eu lieu.
    result = compute_profection(date(1990, 5, 15), "Virgo", date(2026, 1, 1))
    assert result["age"] == 35


def test_profected_year_window_spans_from_birthday_to_next_birthday():
    result = compute_profection(date(1990, 5, 15), "Virgo", date(2026, 8, 2))
    assert result["profected_year_start"] == "2026-05-15"
    assert result["profected_year_end"] == "2027-05-15"
