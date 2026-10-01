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

    # Chiron nécessite le fichier d'éphémérides seas_18.se1 (app/ephe/), fourni avec le dépôt —
    # doit donc être réellement disponible, pas seulement signalé comme indisponible.
    assert "chiron" in names
    assert chart["unavailable_points"] == []


def test_asteroid_points_are_included_when_requested():
    """Cérès/Pallas/Junon/Vesta partagent le même fichier d'éphémérides que Chiron
    (seas_18.se1) — voir points_mineurs_significations.json et app/core/ephemeris.py."""
    optional = ["ceres", "pallas", "juno", "vesta"]
    chart = calculate_natal_chart(**BIRTH_KWARGS, optional_points=optional)
    names = {p["name"] for p in chart["planets"]}
    assert set(optional) <= names
    assert chart["unavailable_points"] == []
    for asteroid in optional:
        p = next(pl for pl in chart["planets"] if pl["name"] == asteroid)
        assert p["sign"] in SIGNS
        assert 0 <= p["degree"] < 30


def test_asteroid_points_are_absent_when_not_requested():
    chart = calculate_natal_chart(**BIRTH_KWARGS, optional_points=[])
    names = {p["name"] for p in chart["planets"]}
    assert names.isdisjoint({"ceres", "pallas", "juno", "vesta", "chiron", "lilith_mean"})


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


def test_character_traits_derived_from_sun_moon_ascendant():
    chart = calculate_natal_chart(**BIRTH_KWARGS)
    traits = chart["character_traits"]
    assert len(traits["keywords"]) > 0
    assert len(traits["sources"]) == 10
    origins = {s["origin"] for s in traits["sources"]}
    assert origins == {
        "sun", "moon", "ascendant", "mercury", "venus", "mars", "jupiter", "saturn",
        "dominant_element", "dominant_modality",
    }
    assert len(traits["generational_placements"]) == 3
    assert {p["planet"] for p in traits["generational_placements"]} == {"Uranus", "Neptune", "Pluto"}


# ---------------------------------------------------------------------
# Ascendant fixé manuellement (rectification) : maisons en signes intégraux, latitude/
# longitude ignorées (0.0/0.0 volontairement absurdes ici pour prouver qu'elles sont bien
# ignorées quand ascendant_override_longitude est fourni).
# ---------------------------------------------------------------------
def test_ascendant_override_produces_whole_sign_houses():
    chart = calculate_natal_chart(
        birth_date="1990-05-15", birth_time="14:32:00", time_known=True, timezone="Europe/Paris",
        latitude=0.0, longitude=0.0, ascendant_override_longitude=222.0,  # 12° Scorpion
    )
    assert chart["ascendant_manually_set"] is True
    assert chart["angles"]["ascendant"]["sign"] == "Scorpio"
    assert chart["angles"]["ascendant"]["degree"] == 12.0
    # Maisons de signes intégraux : chaque cuspide tombe exactement à 0° d'un signe.
    assert [h["degree"] for h in chart["houses"]] == [0.0] * 12
    assert [h["sign"] for h in chart["houses"]] == [
        "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces", "Aries",
        "Taurus", "Gemini", "Cancer", "Leo", "Virgo", "Libra",
    ]


def test_ascendant_override_absent_uses_normal_house_calculation():
    chart = calculate_natal_chart(**BIRTH_KWARGS)
    assert chart["ascendant_manually_set"] is False


# ---------------------------------------------------------------------
# Modalité angulaire/succédente/cadente des maisons (intégration dans le thème complet)
# ---------------------------------------------------------------------
def test_chart_includes_house_modality_analysis_and_quadrants():
    chart = calculate_natal_chart(**BIRTH_KWARGS)
    analysis = chart["house_modality_analysis"]
    assert sum(analysis["counts_by_modality"].values()) == 10  # 10 planètes classiques
    assert analysis["dominant_modality_simple"] in {"angular", "succedent", "cadent"}
    assert analysis["dominant_modality_weighted"] in {"angular", "succedent", "cadent"}
    quadrants = chart["house_quadrants"]
    assert len(quadrants) == 4
    assert {g["key"] for g in quadrants} == {"identite", "racines", "relations", "vie_publique"}
    assert sum(g["planet_count"] for g in quadrants) == 10
    assert any(g["is_most_loaded"] for g in quadrants)
