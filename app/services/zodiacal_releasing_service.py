from datetime import date as date_type

from app import models
from app.core.reference_data import ruler_map
from app.core.zodiacal_releasing import compute_zodiacal_releasing


def compute_zodiacal_releasing_for_chart(
    chart: models.NatalChart,
    as_of_date: date_type | None = None,
    lookahead_years: float = 5,
) -> dict:
    """Calcule les phases de Libération Zodiacale pour tous les lots du thème (le Lot de
    Fortune et le Lot d'Esprit démarrent chacun leur propre séquence, avec le décalage
    documenté s'ils tombent dans le même signe ; les autres lots suivent le même algorithme
    de façon indépendante)."""
    lot_signs = {lot["name"]: lot["sign"] for lot in chart.computed_chart_data["lots"]}
    return compute_zodiacal_releasing(
        lot_signs=lot_signs,
        birth_date=chart.birth_date,
        ruler_map=ruler_map("traditional"),
        as_of_date=as_of_date,
        lookahead_years=lookahead_years,
    )
