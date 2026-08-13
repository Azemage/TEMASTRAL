from app.core.astrocartography_personalization import (
    compute_dignity,
    compute_natal_condition,
    compute_temporal_pertinence,
    compute_theme_confirme,
    personalize_nearby_lines,
)


# ---------------------------------------------------------------------------
# Couche 2 : dignité + condition natale
# ---------------------------------------------------------------------------
def test_compute_dignity_domicile():
    assert compute_dignity("Sun", "Leo") == "domicile"


def test_compute_dignity_exaltation():
    assert compute_dignity("Jupiter", "Cancer") == "exaltation"


def test_compute_dignity_exil():
    assert compute_dignity("Mars", "Libra") == "exil"


def test_compute_dignity_chute():
    assert compute_dignity("Saturn", "Aries") == "chute"


def test_compute_dignity_peregrin_for_unrelated_sign():
    assert compute_dignity("Venus", "Sagittarius") == "pérégrin"


def test_compute_dignity_returns_peregrin_when_sign_is_none():
    assert compute_dignity("Sun", None) == "pérégrin"


def test_compute_natal_condition_classifies_favorable_aspects():
    planet_signs = {"Venus": "Taurus"}
    planet_retrograde = {"Venus": False}
    aspects = [
        {"planet1": "Venus", "planet2": "Jupiter", "type": "trine", "type_fr": "trigone", "orb": 1.0},
        {"planet1": "Venus", "planet2": "Moon", "type": "sextile", "type_fr": "sextile", "orb": 2.0},
    ]
    condition = compute_natal_condition("Venus", planet_signs, planet_retrograde, aspects)
    assert condition["dignity"] == "domicile"
    assert condition["aspect_quality"] == "favorable"
    assert condition["friction_with_malefic"] is False
    assert condition["retrograde"] is False
    assert [a["other_planet"] for a in condition["aspects"]] == ["Jupiter", "Moon"]  # trié par orbe


def test_compute_natal_condition_flags_friction_with_malefic():
    planet_signs = {"Moon": "Scorpio"}
    planet_retrograde = {"Moon": False}
    aspects = [{"planet1": "Mars", "planet2": "Moon", "type": "square", "type_fr": "carré", "orb": 2.0}]
    condition = compute_natal_condition("Moon", planet_signs, planet_retrograde, aspects)
    assert condition["aspect_quality"] == "challenging"
    assert condition["friction_with_malefic"] is True


def test_compute_natal_condition_ignores_aspects_beyond_five_degrees_orb():
    planet_signs = {"Mercury": "Gemini"}
    planet_retrograde = {"Mercury": False}
    aspects = [{"planet1": "Mercury", "planet2": "Saturn", "type": "square", "type_fr": "carré", "orb": 5.5}]
    condition = compute_natal_condition("Mercury", planet_signs, planet_retrograde, aspects)
    assert condition["aspect_quality"] == "neutral"
    assert condition["friction_with_malefic"] is False


def test_compute_natal_condition_mixed_when_both_qualities_present():
    planet_signs = {"Mars": "Aries"}
    planet_retrograde = {"Mars": True}
    aspects = [
        {"planet1": "Mars", "planet2": "Sun", "type": "trine", "type_fr": "trigone", "orb": 1.0},
        {"planet1": "Mars", "planet2": "Saturn", "type": "opposition", "type_fr": "opposition", "orb": 1.5},
    ]
    condition = compute_natal_condition("Mars", planet_signs, planet_retrograde, aspects)
    assert condition["aspect_quality"] == "mixed"
    assert condition["retrograde"] is True


# ---------------------------------------------------------------------------
# Couche 3 : thèmes confirmés (dispositeur dominant, maître de l'Ascendant, stellium)
# ---------------------------------------------------------------------------
def _base_chart_data(**overrides):
    data = {
        "angles": {"ascendant": {"sign": "Capricorn"}},
        "planets": [
            {"name": "Sun", "sign": "Leo", "house": 5},
            {"name": "Moon", "sign": "Cancer", "house": 4},
            {"name": "Mercury", "sign": "Leo", "house": 5},
            {"name": "Venus", "sign": "Leo", "house": 5},
        ],
        "dispositors_traditional": {"convergence": {"dominant_dispositor": None, "level": "aucune"}},
        "dispositors_modern": {"convergence": {"dominant_dispositor": None, "level": "aucune"}},
        "aspects": [],
    }
    data.update(overrides)
    return data


def test_compute_theme_confirme_dominant_dispositor_strong():
    chart_data = _base_chart_data(
        dispositors_traditional={"convergence": {"dominant_dispositor": "Saturn", "level": "forte"}}
    )
    result = compute_theme_confirme("Saturn", chart_data)
    assert result["present"] is True
    assert any("dispositeur final dominant" in r for r in result["reasons"])


def test_compute_theme_confirme_ascendant_ruler():
    # Ascendant en Capricorne : maître traditionnel = Saturne.
    chart_data = _base_chart_data()
    result = compute_theme_confirme("Saturn", chart_data)
    assert result["present"] is True
    assert "maître de l'Ascendant" in result["reasons"]


def test_compute_theme_confirme_stellium_by_sign():
    # Sun, Mercury, Venus tous en Lion (3 planètes classiques) -> stellium.
    chart_data = _base_chart_data()
    result = compute_theme_confirme("Sun", chart_data)
    assert result["present"] is True
    assert any("stellium" in r for r in result["reasons"])


def test_compute_theme_confirme_absent_when_no_signal():
    chart_data = _base_chart_data()
    result = compute_theme_confirme("Neptune", chart_data)
    assert result["present"] is False
    assert result["reasons"] == []


def test_compute_theme_confirme_ignores_stellium_group_smaller_than_three():
    chart_data = _base_chart_data(
        planets=[{"name": "Sun", "sign": "Leo", "house": 5}, {"name": "Moon", "sign": "Leo", "house": 4}]
    )
    result = compute_theme_confirme("Sun", chart_data)
    assert result["present"] is False


def test_compute_theme_confirme_ignores_house_none_for_stellium():
    chart_data = _base_chart_data(
        planets=[
            {"name": "Sun", "sign": "Leo", "house": None},
            {"name": "Moon", "sign": "Cancer", "house": None},
            {"name": "Mercury", "sign": "Virgo", "house": None},
        ]
    )
    # Aucun stellium par signe (3 signes différents) ; maisons toutes None -> ignorées, pas
    # un faux stellium par regroupement de None.
    result = compute_theme_confirme("Sun", chart_data)
    assert result["present"] is False


# ---------------------------------------------------------------------------
# Couche 4 : pertinence temporelle (profection, Libération Zodiacale)
# ---------------------------------------------------------------------------
def test_compute_temporal_pertinence_year_ruler():
    profection = {"year_ruler": "Mars"}
    result = compute_temporal_pertinence("Mars", profection, None)
    assert result["active"] is True
    assert result["urgency"] == "élevé"


def test_compute_temporal_pertinence_zodiacal_releasing_l1_active():
    zr_data = {"lots": {"Fortune": {"current_l1": {"ruling_planet": "Venus"}, "current_l2": None}}}
    result = compute_temporal_pertinence("Venus", None, zr_data)
    assert result["active"] is True
    assert result["urgency"] == "modéré"
    assert "Fortune" in result["reasons"][0]


def test_compute_temporal_pertinence_inactive_returns_background_potential():
    result = compute_temporal_pertinence("Pluto", {"year_ruler": "Mars"}, None)
    assert result["active"] is False
    assert result["urgency"] == "potentiel de fond"
    assert result["reasons"] == []


def test_compute_temporal_pertinence_handles_missing_lot_gracefully():
    zr_data = {"lots": {}}
    result = compute_temporal_pertinence("Venus", None, zr_data)
    assert result["active"] is False


# ---------------------------------------------------------------------------
# Point d'entrée : personalize_nearby_lines (agrégation + tri par priorité)
# ---------------------------------------------------------------------------
def test_personalize_nearby_lines_sorts_by_priority_descending():
    chart_data = _base_chart_data(
        dispositors_traditional={"convergence": {"dominant_dispositor": "Saturn", "level": "forte"}}
    )
    nearby = [
        {"planet": "Neptune", "line_type": "MC", "distance_km": 50.0},
        {"planet": "Saturn", "line_type": "IC", "distance_km": 400.0},
    ]
    significations = {"Neptune": {"MC": "sens X"}, "Saturn": {"IC": "sens Y"}}
    result = personalize_nearby_lines(nearby, chart_data, significations)
    # Saturne (maître ASC + dispositeur dominant fort) doit primer sur Neptune (aucun signal
    # de thème confirmé), même si Neptune est géographiquement plus proche.
    assert result[0]["planet"] == "Saturn"
    assert result[0]["priority_score"] > result[1]["priority_score"]
    assert result[0]["base_meaning"] == "sens Y"


def test_personalize_nearby_lines_caches_planet_level_data_across_line_types():
    chart_data = _base_chart_data()
    nearby = [
        {"planet": "Sun", "line_type": "MC", "distance_km": 10.0},
        {"planet": "Sun", "line_type": "ASC", "distance_km": 20.0},
    ]
    result = personalize_nearby_lines(nearby, chart_data, {})
    # Même planète -> même theme_confirme_lie (stellium en Lion) sur les deux lignes.
    assert result[0]["theme_confirme_lie"] == result[1]["theme_confirme_lie"]


def test_personalize_nearby_lines_preserves_distance_and_line_type():
    chart_data = _base_chart_data()
    nearby = [{"planet": "Neptune", "line_type": "DC", "distance_km": 123.4}]
    result = personalize_nearby_lines(nearby, chart_data, {})
    assert result[0]["distance_km"] == 123.4
    assert result[0]["line_type"] == "DC"


def test_personalize_nearby_lines_output_is_json_serializable():
    import json

    chart_data = _base_chart_data(
        dispositors_traditional={"convergence": {"dominant_dispositor": "Saturn", "level": "forte"}}
    )
    nearby = [{"planet": "Saturn", "line_type": "MC", "distance_km": 5.0}]
    result = personalize_nearby_lines(nearby, chart_data, {}, profection={"year_ruler": "Saturn"}, zr_data=None)
    json.dumps(result)  # ne doit jamais lever (pas de champ non sérialisable, pas de clé interne "_...")
    assert all(not k.startswith("_") for entry in result for k in entry)
