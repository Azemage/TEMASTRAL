from app import models
from app.core import ephemeris
from app.core.chart_calculator import DEFAULT_TIME_WHEN_UNKNOWN
from app.core.lifespan_estimate import estimate_lifespan


def compute_lifespan_estimate(chart: models.NatalChart) -> dict:
    """Recalcule le jour julien UT de naissance à partir du thème stocké (non conservé dans
    `computed_chart_data`) puis applique la technique du Hyleg/Alcocoden — voir
    app/core/lifespan_estimate.py pour la technique elle-même et son avertissement de source."""
    birth_time = chart.birth_time.isoformat() if chart.birth_time_known and chart.birth_time else DEFAULT_TIME_WHEN_UNKNOWN
    jd_ut = ephemeris.local_datetime_to_jd_ut(chart.birth_date.isoformat(), birth_time, chart.birth_timezone)
    return estimate_lifespan(chart.computed_chart_data, jd_ut)
