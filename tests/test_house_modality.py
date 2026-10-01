from app.core.house_modality import (
    classify_house,
    compute_house_modality_analysis,
    compute_quadrant_loads,
    planet_weight_for,
)


def test_classify_house_matches_documented_kentra_epanaphora_apoklima():
    assert {classify_house(h) for h in (1, 4, 7, 10)} == {"angular"}
    assert {classify_house(h) for h in (2, 5, 8, 11)} == {"succedent"}
    assert {classify_house(h) for h in (3, 6, 9, 12)} == {"cadent"}


def test_planet_weight_matches_preferred_scale():
    # Luminaires > personnelles > sociales > lentes/générationnelles.
    assert planet_weight_for("Sun") == 4
    assert planet_weight_for("Moon") == 4
    assert planet_weight_for("Mercury") == 3
    assert planet_weight_for("Venus") == 3
    assert planet_weight_for("Mars") == 3
    assert planet_weight_for("Jupiter") == 2
    assert planet_weight_for("Saturn") == 2
    assert planet_weight_for("Uranus") == 1
    assert planet_weight_for("Neptune") == 1
    assert planet_weight_for("Pluto") == 1


def test_planet_weight_unknown_planet_returns_zero():
    assert planet_weight_for("ceres") == 0


def test_compute_house_modality_analysis_counts_and_dominant():
    planets = [
        {"name": "Sun", "house": 1},
        {"name": "Moon", "house": 4},
        {"name": "Mercury", "house": 10},
        {"name": "Venus", "house": 2},
        {"name": "Mars", "house": 6},
        {"name": "Jupiter", "house": 9},
        {"name": "Saturn", "house": 12},
        {"name": "Uranus", "house": 3},
        {"name": "Neptune", "house": 5},
        {"name": "Pluto", "house": 11},
    ]
    result = compute_house_modality_analysis(planets)
    assert result["counts_by_modality"] == {"angular": 3, "succedent": 3, "cadent": 4}
    assert result["dominant_modality_simple"] == "cadent"
    assert sum(result["counts_by_modality"].values()) == 10
    assert len(result["per_planet"]) == 10
    assert result["dominant_modality_weighted"] in {"angular", "succedent", "cadent"}
    assert "reading" in result and result["reading"]
    assert "methodological_note" in result


def test_compute_house_modality_analysis_respects_planet_subset():
    planets = [{"name": "Sun", "house": 1}, {"name": "Moon", "house": 6}, {"name": "chiron", "house": 12}]
    result = compute_house_modality_analysis(planets, planet_names=["Sun", "Moon"])
    assert sum(result["counts_by_modality"].values()) == 2  # chiron exclu (hors défaut)


def test_dominant_can_differ_between_simple_and_weighted():
    # 3 planètes lentes/générationnelles (poids 1 chacune) en maisons cadentes vs le Soleil et
    # la Lune (poids 4 chacune) en maisons angulaires : plus nombreuses mais individuellement
    # moins "personnelles" -> comptage simple favorise cadent, score pondéré favorise angular.
    planets = [
        {"name": "Uranus", "house": 3},
        {"name": "Neptune", "house": 6},
        {"name": "Pluto", "house": 9},
        {"name": "Sun", "house": 1},
        {"name": "Moon", "house": 10},
    ]
    result = compute_house_modality_analysis(
        planets, planet_names=["Uranus", "Neptune", "Pluto", "Sun", "Moon"]
    )
    assert result["counts_by_modality"]["cadent"] == 3
    assert result["counts_by_modality"]["angular"] == 2
    assert result["dominant_modality_simple"] == "cadent"
    # Score pondéré : angular = 4+4=8, cadent = 1+1+1=3 -> dominant pondéré = angular.
    assert result["weighted_score_by_modality"]["angular"] == 8
    assert result["weighted_score_by_modality"]["cadent"] == 3
    assert result["dominant_modality_weighted"] == "angular"


def test_quadrant_loads_centers_each_angle():
    groups = compute_quadrant_loads([])
    houses_by_group = {g["key"]: g["houses"] for g in groups}
    assert houses_by_group["identite"] == [12, 1, 2]
    assert houses_by_group["racines"] == [3, 4, 5]
    assert houses_by_group["relations"] == [6, 7, 8]
    assert houses_by_group["vie_publique"] == [9, 10, 11]


def test_quadrant_loads_cover_all_twelve_houses():
    all_houses = sorted(h for g in compute_quadrant_loads([]) for h in g["houses"])
    assert all_houses == list(range(1, 13))


def test_quadrant_loads_counts_planets_and_flags_most_loaded():
    planets = [
        {"name": "Sun", "house": 1},  # identite (12-1-2)
        {"name": "Moon", "house": 1},  # identite
        {"name": "Mercury", "house": 4},  # racines (3-4-5)
        {"name": "Venus", "house": 7},  # relations (6-7-8)
        {"name": "Mars", "house": 10},  # vie_publique (9-10-11)
    ]
    groups = compute_quadrant_loads(planets, planet_names=["Sun", "Moon", "Mercury", "Venus", "Mars"])
    by_key = {g["key"]: g for g in groups}
    assert by_key["identite"]["planet_count"] == 2
    assert set(by_key["identite"]["planets"]) == {"Sun", "Moon"}
    assert by_key["racines"]["planet_count"] == 1
    assert by_key["identite"]["is_most_loaded"] is True
    assert by_key["racines"]["is_most_loaded"] is False
    # Trié du plus chargé au moins chargé.
    assert groups[0]["key"] == "identite"


def test_quadrant_loads_ties_flag_all_tied_groups_as_most_loaded():
    planets = [{"name": "Sun", "house": 1}, {"name": "Moon", "house": 4}]
    groups = compute_quadrant_loads(planets, planet_names=["Sun", "Moon"])
    by_key = {g["key"]: g for g in groups}
    assert by_key["identite"]["is_most_loaded"] is True
    assert by_key["racines"]["is_most_loaded"] is True
    assert by_key["relations"]["is_most_loaded"] is False
    assert by_key["vie_publique"]["is_most_loaded"] is False


def test_quadrant_loads_empty_chart_has_no_most_loaded():
    groups = compute_quadrant_loads([])
    assert all(g["planet_count"] == 0 for g in groups)
    assert all(g["is_most_loaded"] is False for g in groups)
