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


def test_draconic_north_node_falls_at_zero_aries():
    chart = calculate_natal_chart(**BIRTH_KWARGS, optional_points=["north_node"])
    node = next(p for p in chart["draconic"]["planets"] if p["name"] == "north_node")
    assert node["sign"] == "Aries"
    assert node["degree"] < 0.01 or node["degree"] > 29.99  # arrondi flottant autour de 0°


def test_draconic_houses_and_aspects_identical_to_natal():
    chart = calculate_natal_chart(**BIRTH_KWARGS)
    natal_house_by_planet = {p["name"]: p["house"] for p in chart["planets"]}
    draconic_house_by_planet = {p["name"]: p["house"] for p in chart["draconic"]["planets"]}
    # Une rotation globale ne change aucune distance angulaire planète<->cuspide : la maison
    # occupée par chaque planète doit être rigoureusement identique au thème natal.
    assert draconic_house_by_planet == natal_house_by_planet
    # Même principe pour les aspects (distance planète<->planète inchangée) : réutilisés tels
    # quels, pas recalculés.
    assert chart["draconic"]["aspects"] == chart["aspects"]


def test_draconic_signs_differ_from_natal_but_stay_valid():
    chart = calculate_natal_chart(**BIRTH_KWARGS)
    natal_signs = {p["name"]: p["sign"] for p in chart["planets"]}
    draconic_signs = {p["name"]: p["sign"] for p in chart["draconic"]["planets"]}
    for name, sign in draconic_signs.items():
        assert sign in SIGNS
    # Le thème choisi pour ce test a un Nœud Nord natal hors 0° Bélier, donc au moins un point
    # doit changer de signe entre natal et draconique (sinon la rotation serait nulle).
    assert natal_signs != draconic_signs


def test_draconic_elements_and_modality_balance_sum_to_ten_classic_planets():
    chart = calculate_natal_chart(**BIRTH_KWARGS)
    assert sum(chart["draconic"]["elements_balance"].values()) == 10
    assert sum(chart["draconic"]["modality_balance"].values()) == 10


def test_draconic_available_even_without_north_node_selected():
    """La rotation doit fonctionner même si les Nœuds n'ont pas été sélectionnés à la création
    du thème (recalcul direct du Nœud Nord, voir compute_draconic_chart)."""
    chart = calculate_natal_chart(**BIRTH_KWARGS, optional_points=[])
    assert chart["draconic"]["planets"]
    assert {h["number"] for h in chart["draconic"]["houses"]} == set(range(1, 13))
