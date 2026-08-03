import pytest

from app.core.chart_calculator import calculate_natal_chart
from app.core.synastry import (
    SUPPORTED_RELATIONSHIP_MODES,
    _midpoint_longitude,
    compute_composite_chart,
    compute_house_overlay,
    compute_inter_aspects,
    compute_synastry,
)


def _chart_a():
    return calculate_natal_chart(
        birth_date="1990-05-15", birth_time="14:32:00", time_known=True,
        timezone="Europe/Paris", latitude=45.7640, longitude=4.8357,
    )


def _chart_b():
    return calculate_natal_chart(
        birth_date="1988-11-02", birth_time="08:15:00", time_known=True,
        timezone="Europe/Paris", latitude=48.8566, longitude=2.3522,
    )


def test_midpoint_takes_the_shorter_arc():
    assert _midpoint_longitude(10, 20) == pytest.approx(15)
    assert _midpoint_longitude(350, 10) == pytest.approx(0, abs=1e-9) or _midpoint_longitude(350, 10) == pytest.approx(360)


def test_midpoint_is_symmetric():
    a, b = 42.3, 291.7
    assert _midpoint_longitude(a, b) == pytest.approx(_midpoint_longitude(b, a))


def test_compute_synastry_rejects_unsupported_mode():
    a, b = _chart_a(), _chart_b()
    with pytest.raises(ValueError):
        compute_synastry(a, b, "person_company")


def test_compute_synastry_returns_all_three_techniques():
    a, b = _chart_a(), _chart_b()
    result = compute_synastry(a, b, "romantic")
    assert result["relationship_mode"] == "romantic"
    assert len(result["inter_aspects"]) > 0
    assert len(result["house_overlay"]["a_planets_in_b_houses"]) == len(a["planets"])
    assert len(result["house_overlay"]["b_planets_in_a_houses"]) == len(b["planets"])
    assert set(result["composite_chart"]["points"].keys()) == {
        "Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto",
    }
    assert "ascendant" in result["composite_chart"]
    assert result["charts_time_known"] == {"chart_a": True, "chart_b": True}


def test_inter_aspects_never_pair_two_planets_from_the_same_chart():
    a, b = _chart_a(), _chart_b()
    aspects = compute_inter_aspects(a, b, "romantic")
    a_names = {p["name"] for p in a["planets"]}
    b_names = {p["name"] for p in b["planets"]}
    for aspect in aspects:
        # planet_a vient toujours du thème A, planet_b toujours du thème B (par construction
        # de compute_cross_aspects), jamais une paire interne à un seul thème.
        assert aspect["planet_a"] in a_names
        assert aspect["planet_b"] in b_names


def test_inter_aspects_sorted_by_weight_then_orb():
    a, b = _chart_a(), _chart_b()
    aspects = compute_inter_aspects(a, b, "romantic")
    weighted = [asp for asp in aspects if asp["significator_matches"]]
    unweighted = [asp for asp in aspects if not asp["significator_matches"]]
    if weighted and unweighted:
        # Tous les aspects pondérés doivent apparaître avant les non pondérés dans la liste triée.
        assert aspects.index(weighted[-1]) < aspects.index(unweighted[0])


def test_inter_aspects_saturn_personal_planet_and_specific_mars_saturn_rule_both_apply():
    # Le document source liste "Saturn-personal_planets" (générique) ET "Mars-Saturn"
    # (spécifique) séparément pour le mode romantique : un aspect Mars-Saturn doit remonter
    # les deux significations, pas une seule qui écraserait l'autre.
    a, b = _chart_a(), _chart_b()
    aspects = compute_inter_aspects(a, b, "romantic", orb=180)  # orbe large : force la détection d'un aspect Mars-Saturn
    mars_saturn = [
        asp for asp in aspects if {asp["planet_a"], asp["planet_b"]} == {"Mars", "Saturn"}
    ]
    assert mars_saturn
    weights = {m["weight"] for m in mars_saturn[0]["significator_matches"]}
    assert "très fort" in weights  # via Saturn-personal_planets
    assert "moyen" in weights  # via la règle spécifique Mars-Saturn


def test_house_overlay_house_7_flagged_as_key_placement_in_romantic_mode():
    a, b = _chart_a(), _chart_b()
    overlay = compute_house_overlay(a, b, "romantic")
    house_7_entries = [e for e in overlay["a_planets_in_b_houses"] + overlay["b_planets_in_a_houses"] if e["house"] == 7]
    assert house_7_entries
    assert all(e["key_meaning"] is not None for e in house_7_entries)


def test_house_overlay_no_key_meaning_for_unlisted_house():
    a, b = _chart_a(), _chart_b()
    overlay = compute_house_overlay(a, b, "romantic")
    # La maison 6 n'est pas listée dans key_placements_by_mode.romantic : doit rester None.
    house_6_entries = [e for e in overlay["a_planets_in_b_houses"] if e["house"] == 6]
    for entry in house_6_entries:
        assert entry["key_meaning"] is None


def test_composite_chart_sun_is_midpoint_of_both_suns():
    a, b = _chart_a(), _chart_b()
    composite = compute_composite_chart(a, b)
    sun_a = next(p for p in a["planets"] if p["name"] == "Sun")["absolute_longitude"]
    sun_b = next(p for p in b["planets"] if p["name"] == "Sun")["absolute_longitude"]
    expected = _midpoint_longitude(sun_a, sun_b)
    assert composite["points"]["Sun"]["absolute_longitude"] == pytest.approx(round(expected, 4))


@pytest.mark.parametrize("mode", sorted(SUPPORTED_RELATIONSHIP_MODES))
def test_compute_synastry_works_for_every_supported_mode(mode):
    a, b = _chart_a(), _chart_b()
    result = compute_synastry(a, b, mode)
    assert result["relationship_mode"] == mode
