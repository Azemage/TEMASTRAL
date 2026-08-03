from app import models
from app.core.synastry import compute_synastry


def compute_synastry_for_charts(chart_a: models.NatalChart, chart_b: models.NatalChart, mode: str) -> dict:
    result = compute_synastry(chart_a.computed_chart_data, chart_b.computed_chart_data, mode)
    result["chart_a_id"] = chart_a.id
    result["chart_b_id"] = chart_b.id
    return result
