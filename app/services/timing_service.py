from datetime import date as date_type
from datetime import timedelta

from app import models
from app.core.aspects import BodyForAspect
from app.core.profections import compute_profection
from app.core.transits import compute_current_transits, compute_upcoming_transits


def _natal_bodies_from_chart(chart: models.NatalChart) -> list[BodyForAspect]:
    data = chart.computed_chart_data
    bodies = [BodyForAspect(name=p["name"], longitude=p["absolute_longitude"]) for p in data["planets"]]
    for angle_name, angle in data["angles"].items():
        bodies.append(BodyForAspect(name=angle_name, longitude=angle["absolute_longitude"]))
    return bodies


def compute_timing(chart: models.NatalChart, as_of_date: date_type | None = None) -> dict:
    as_of_date = as_of_date or date_type.today()
    natal_bodies = _natal_bodies_from_chart(chart)
    transits = compute_current_transits(natal_bodies, as_of_date)

    ascendant_sign = chart.computed_chart_data["angles"]["ascendant"]["sign"]
    profection = compute_profection(chart.birth_date, ascendant_sign, as_of_date)

    return {
        "date": as_of_date,
        "transiting_planets": transits["transiting_planets"],
        "aspects": transits["aspects"],
        "profection": profection,
    }


def compute_forecast(chart: models.NatalChart, start_date: date_type | None = None, months: int = 12) -> dict:
    start_date = start_date or date_type.today()
    end_date = start_date + timedelta(days=months * 30)
    natal_bodies = _natal_bodies_from_chart(chart)
    events = compute_upcoming_transits(natal_bodies, start_date, end_date)
    return {"start_date": start_date, "end_date": end_date, "events": events}
