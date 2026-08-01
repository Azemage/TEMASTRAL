from app.core.chart_calculator import calculate_natal_chart
from app.core.zodiac import SIGNS

BIRTH_KWARGS = dict(
    birth_date="1990-05-15",
    birth_time="14:32:00",
    time_known=True,
    timezone="Europe/Paris",
    latitude=45.7640,
    longitude=4.8357,
)


def test_chart_has_ten_classic_planets_with_valid_positions():
    chart = calculate_natal_chart(**BIRTH_KWARGS, optional_points=[])
    names = {p["name"] for p in chart["planets"]}
    assert names == {
        "Sun", "Moon", "Mercury", "Venus", "Mars",
        "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto",
    }
    for planet in chart["planets"]:
        assert planet["sign"] in SIGNS
        assert 0 <= planet["degree"] < 30
        assert 1 <= planet["house"] <= 12


def test_chart_has_twelve_houses_and_four_angles():
    chart = calculate_natal_chart(**BIRTH_KWARGS)
    assert len(chart["houses"]) == 12
    assert {h["number"] for h in chart["houses"]} == set(range(1, 13))
    assert set(chart["angles"].keys()) == {"ascendant", "midheaven", "descendant", "imum_coeli"}


def test_optional_points_are_included_when_requested():
    chart = calculate_natal_chart(**BIRTH_KWARGS, optional_points=["north_node", "south_node", "chiron"])
    names = {p["name"] for p in chart["planets"]}
    assert {"north_node", "south_node"} <= names

    north = next(p for p in chart["planets"] if p["name"] == "north_node")
    south = next(p for p in chart["planets"] if p["name"] == "south_node")
    # Le Nœud Sud est toujours exactement opposé au Nœud Nord.
    diff = abs(north["absolute_longitude"] - south["absolute_longitude"]) % 360
    assert abs(diff - 180) < 0.01

    # Chiron nécessite des fichiers d'éphémérides non fournis par le calcul Moshier intégré :
    # soit il est présent (fichiers installés), soit signalé comme indisponible, jamais silencieux.
    assert "chiron" in names or "chiron" in chart["unavailable_points"]


def test_elements_and_modality_balance_sum_to_ten_classic_planets():
    chart = calculate_natal_chart(**BIRTH_KWARGS)
    assert sum(chart["elements_balance"].values()) == 10
    assert sum(chart["modality_balance"].values()) == 10


def test_unknown_birth_time_falls_back_to_noon_and_flags_it():
    chart = calculate_natal_chart(**{**BIRTH_KWARGS, "birth_time": None, "time_known": False})
    assert chart["time_known"] is False
    assert len(chart["houses"]) == 12  # toujours calculé, mais à considérer comme approximatif


def test_dispositors_present_for_both_systems():
    chart = calculate_natal_chart(**BIRTH_KWARGS)
    assert len(chart["dispositors_traditional"]["dispositors"]) == 10
    assert len(chart["dispositors_modern"]["dispositors"]) == 10
