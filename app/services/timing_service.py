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


def select_significant_events(events: list[dict], min_count: int = 5, max_count: int = 20) -> list[dict]:
    """Réduit la liste brute d'événements à venir (potentiellement des centaines, la Lune et
    les autres planètes rapides étant désormais incluses) aux plus significatifs, en
    s'appuyant sur `intensity` : commence par le seuil le plus strict et l'assouplit tant
    qu'il n'y a pas assez d'événements à proposer au modèle."""
    candidates = events
    for min_intensity in (4, 3, 2, 1):
        candidates = [e for e in events if e["intensity"] >= min_intensity]
        if len(candidates) >= min_count or min_intensity == 1:
            break
    candidates = sorted(candidates, key=lambda e: (-e["intensity"], e["peak_orb"]))[:max_count]
    return sorted(candidates, key=lambda e: e["peak_date"])


TIMING_HORIZON_DAYS = {"week": 7, "month": 30, "year": 365}


def select_events_for_horizon(events: list[dict], horizon: str, as_of_date: date_type, max_count: int = 20) -> list[dict]:
    """Filtre les événements dont la fenêtre active recoupe l'horizon demandé, avec une
    sélection adaptée à l'échelle de temps : sur un an, on privilégie les signaux les plus
    intenses (grands arcs) comme `select_significant_events` ; sur une semaine, on garde tout
    (y compris les transits lunaires mineurs, qui sont justement ce qui donne la texture
    concrète à cette échelle) ; le mois est un compromis entre les deux."""
    window_end = (as_of_date + timedelta(days=TIMING_HORIZON_DAYS.get(horizon, 365))).isoformat()
    as_of_iso = as_of_date.isoformat()
    in_window = [e for e in events if e["window_start"] <= window_end and e["window_end"] >= as_of_iso]

    if horizon == "week":
        return sorted(in_window, key=lambda e: e["peak_date"])[:max_count]
    if horizon == "month":
        candidates = [e for e in in_window if e["intensity"] >= 2] or in_window
        candidates = sorted(candidates, key=lambda e: (-e["intensity"], e["peak_orb"]))[:max_count]
        return sorted(candidates, key=lambda e: e["peak_date"])
    return select_significant_events(in_window, max_count=max_count)
