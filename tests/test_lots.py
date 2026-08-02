from app.core.aspects import BodyForAspect
from app.core.lots import UnknownLotPointError, _evaluate_formula, compute_lots


def _fixed_house(_longitude: float) -> int:
    return 1


def test_evaluate_formula_basic_addition_and_subtraction():
    points = {"ASC": 100.0, "Moon": 50.0, "Sun": 20.0}
    # ASC + Moon - Sun = 100 + 50 - 20 = 130
    assert _evaluate_formula("ASC + Moon - Sun", points) == 130.0


def test_evaluate_formula_wraps_at_360():
    points = {"ASC": 300.0, "Moon": 200.0, "Sun": 10.0}
    # 300 + 200 - 10 = 490 -> 130 (mod 360)
    assert _evaluate_formula("ASC + Moon - Sun", points) == 130.0


def test_evaluate_formula_raises_on_unknown_point():
    try:
        _evaluate_formula("ASC + Unknown - Sun", {"ASC": 0, "Sun": 0})
        assert False, "devrait lever UnknownLotPointError"
    except UnknownLotPointError:
        pass


def test_compute_lots_day_vs_night_formula_are_inverted():
    points = {
        "ASC": 0.0, "MC": 270.0, "Descendant": 180.0, "IC": 90.0,
        "Sun": 40.0, "Moon": 100.0, "Mercury": 40.0, "Venus": 40.0, "Mars": 40.0,
        "Jupiter": 40.0, "Saturn": 40.0,
        "house_cusp_8": 0.0, "house_cusp_9": 0.0, "house_cusp_11": 0.0,
    }
    day_lots = {lot["name"]: lot for lot in compute_lots(points, is_day_chart=True, find_house_fn=_fixed_house)}
    night_lots = {lot["name"]: lot for lot in compute_lots(points, is_day_chart=False, find_house_fn=_fixed_house)}

    # Lot de Fortune : jour = ASC+Moon-Sun = 0+100-40=60 ; nuit = ASC+Sun-Moon = 0+40-100=-60 -> 300
    assert day_lots["Lot de Fortune"]["absolute_longitude"] == 60.0
    assert night_lots["Lot de Fortune"]["absolute_longitude"] == 300.0


def test_lot_amour_depends_on_lot_esprit_already_computed():
    points = {
        "ASC": 0.0, "MC": 0.0, "Descendant": 180.0, "IC": 0.0,
        "Sun": 10.0, "Moon": 50.0, "Mercury": 0.0, "Venus": 30.0, "Mars": 0.0,
        "Jupiter": 0.0, "Saturn": 0.0,
        "house_cusp_8": 0.0, "house_cusp_9": 0.0, "house_cusp_11": 0.0,
    }
    lots = {lot["name"]: lot for lot in compute_lots(points, is_day_chart=True, find_house_fn=_fixed_house)}
    # Lot d'Esprit (jour) = ASC+Sun-Moon = 0+10-50 = -40 -> 320
    assert lots["Lot d'Esprit"]["absolute_longitude"] == 320.0
    # Lot d'Amour (jour) = ASC+Venus-Lot_Esprit = 0+30-320 = -290 -> 70
    assert lots["Lot d'Amour"]["absolute_longitude"] == 70.0


def test_compute_lots_returns_all_fourteen_lots_with_house_and_aspects():
    points = {
        "ASC": 15.0, "MC": 285.0, "Descendant": 195.0, "IC": 105.0,
        "Sun": 54.0, "Moon": 297.0, "Mercury": 38.0, "Venus": 12.0, "Mars": 348.0,
        "Jupiter": 99.0, "Saturn": 295.0,
        "house_cusp_8": 33.0, "house_cusp_9": 67.0, "house_cusp_11": 314.0,
    }
    natal_bodies = [
        BodyForAspect(name="Sun", longitude=54.0),
        BodyForAspect(name="Jupiter", longitude=99.0),
    ]
    lots = compute_lots(points, is_day_chart=True, find_house_fn=lambda lon: 1, natal_bodies=natal_bodies)
    assert len(lots) == 14
    assert all(lot["house"] == 1 for lot in lots)
    assert all("aspects_to_natal" in lot for lot in lots)
