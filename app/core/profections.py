"""Profections annuelles (technique hellénistique, signes intégraux).

Chaque année de vie, la maison profectée avance d'un signe à partir de l'Ascendant :
0 an = maison 1 (signe de l'Ascendant), 1 an = maison 2, ... 11 ans = maison 12, 12 ans =
retour à la maison 1, etc. La 'planète de l'année' (year lord) est le maître traditionnel
du signe profecté.
"""

from __future__ import annotations

from datetime import date as date_type

from app.core.reference_data import ruler_map
from app.core.zodiac import SIGNS, SIGNS_FR


def _age_in_completed_years(birth_date: date_type, as_of_date: date_type) -> int:
    age = as_of_date.year - birth_date.year
    had_birthday = (as_of_date.month, as_of_date.day) >= (birth_date.month, birth_date.day)
    if not had_birthday:
        age -= 1
    return age


def _profected_year_start(birth_date: date_type, as_of_date: date_type, age: int) -> date_type:
    year = birth_date.year + age
    try:
        return birth_date.replace(year=year)
    except ValueError:
        # Anniversaire un 29 février dans une année non bissextile.
        return birth_date.replace(year=year, day=28)


def compute_profection(
    birth_date: date_type,
    ascendant_sign: str,
    as_of_date: date_type | None = None,
) -> dict:
    as_of_date = as_of_date or date_type.today()
    age = _age_in_completed_years(birth_date, as_of_date)

    ascendant_index = SIGNS.index(ascendant_sign)
    profected_sign = SIGNS[(ascendant_index + age) % 12]
    profected_house = (age % 12) + 1
    year_ruler = ruler_map("traditional")[profected_sign]

    year_start = _profected_year_start(birth_date, as_of_date, age)
    try:
        year_end = year_start.replace(year=year_start.year + 1)
    except ValueError:
        year_end = year_start.replace(year=year_start.year + 1, day=28)

    return {
        "as_of_date": as_of_date.isoformat(),
        "age": age,
        "profected_house": profected_house,
        "profected_sign": profected_sign,
        "profected_sign_fr": SIGNS_FR[profected_sign],
        "year_ruler": year_ruler,
        "profected_year_start": year_start.isoformat(),
        "profected_year_end": year_end.isoformat(),
    }
