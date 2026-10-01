from app.core.house_modality import (
    classify_house,
    compute_house_modality_analysis,
    group_houses_by_angle_centered_quadrant,
    group_houses_by_standard_quadrant,
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


def test_standard_quadrant_grouping_starts_at_each_angle():
    groups = group_houses_by_standard_quadrant()
    assert len(groups) == 4
    houses_by_group = {g["key"]: g["houses"] for g in groups}
    assert houses_by_group["le_moi"] == [1, 2, 3]
    assert houses_by_group["le_foyer"] == [4, 5, 6]
    assert houses_by_group["l_autre"] == [7, 8, 9]
    assert houses_by_group["le_collectif"] == [10, 11, 12]


def test_angle_centered_quadrant_grouping_centers_each_angle():
    groups = group_houses_by_angle_centered_quadrant()
    houses_by_group = {g["key"]: g["houses"] for g in groups}
    assert houses_by_group["identite"] == [12, 1, 2]
    assert houses_by_group["racines"] == [3, 4, 5]
    assert houses_by_group["relations"] == [6, 7, 8]
    assert houses_by_group["vie_publique"] == [9, 10, 11]


def test_all_twelve_houses_covered_by_both_quadrant_groupings():
    for grouping_fn in (group_houses_by_standard_quadrant, group_houses_by_angle_centered_quadrant):
        all_houses = sorted(h for g in grouping_fn() for h in g["houses"])
        assert all_houses == list(range(1, 13))
