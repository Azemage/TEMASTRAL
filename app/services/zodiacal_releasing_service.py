from datetime import date as date_type

from app import models
from app.core.reference_data import ruler_map
from app.core.zodiacal_releasing import compute_zodiacal_releasing


def compute_zodiacal_releasing_for_chart(chart: models.NatalChart, as_of_date: date_type | None = None) -> dict:
    lots = {lot["name"]: lot for lot in chart.computed_chart_data["lots"]}
    fortune_sign = lots["Lot de Fortune"]["sign"]
    spirit_sign = lots["Lot d'Esprit"]["sign"]
    return compute_zodiacal_releasing(
        fortune_sign=fortune_sign,
        spirit_sign=spirit_sign,
        birth_date=chart.birth_date,
        ruler_map=ruler_map("traditional"),
        as_of_date=as_of_date,
    )
