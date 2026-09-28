from app.core.chart_calculator import calculate_natal_chart
from app.core.degrees import analyze_degree

BIRTH_KWARGS = dict(
    birth_date="1990-05-15",
    birth_time="14:32:00",
    time_known=True,
    timezone="Europe/Paris",
    latitude=45.7640,
    longitude=4.8357,
)


def test_exact_exaltation_detected():
    result = analyze_degree("Mercury", "Virgo", 15.4)
    assert result["is_exact_exaltation"] is True


def test_exaltation_not_flagged_for_wrong_planet_or_sign():
    assert analyze_degree("Venus", "Virgo", 15.4)["is_exact_exaltation"] is False
    assert analyze_degree("Mercury", "Gemini", 15.4)["is_exact_exaltation"] is False


def test_critical_degrees_by_modality():
    # Cardinal (Bélier) : 0, 13, 26.
    assert analyze_degree("Mars", "Aries", 13.2)["is_critical_degree"] is True
    assert analyze_degree("Mars", "Aries", 14.0)["is_critical_degree"] is False
    # Fixe (Taureau) : 8-9, 21-22.
    assert analyze_degree("Venus", "Taurus", 8.9)["is_critical_degree"] is True
    assert analyze_degree("Venus", "Taurus", 10.0)["is_critical_degree"] is False
    # Mutable (Gémeaux) : 4, 17.
    assert analyze_degree("Mercury", "Gemini", 17.5)["is_critical_degree"] is True
    assert analyze_degree("Mercury", "Gemini", 18.0)["is_critical_degree"] is False


def test_pure_entry_and_anaretic_degree():
    assert analyze_degree("Sun", "Leo", 0.3)["is_pure_entry"] is True
    assert analyze_degree("Sun", "Leo", 29.9)["is_anaretic"] is True
    entry = analyze_degree("Sun", "Leo", 0.3)
    anaretic = analyze_degree("Sun", "Leo", 29.9)
    # 0° et 29° sont hors du cycle thématique (voir degree_theory.json notes).
    assert entry["degree_theme_label"] is None
    assert anaretic["degree_theme_label"] is None


def test_degree_theme_cycle_matches_reference_examples():
    # Exemples du chapitre de référence : 18° -> thème Vierge, 26° -> thème Taureau.
    result_18 = analyze_degree("Mercury", "Capricorn", 18.7)
    assert result_18["degree_theme_sign"] == "Virgo"
    result_26 = analyze_degree("Mars", "Leo", 26.1)
    assert result_26["degree_theme_sign"] == "Taurus"


def test_degree_value_uses_floor_not_rounding():
    # 17.996° doit rester dans la bande du degré 17, pas glisser vers 18 par arrondi.
    result = analyze_degree("Mercury", "Gemini", 17.996)
    assert result["degree_value"] == 17
    assert result["is_critical_degree"] is True  # 17 est critique (mutable), 18 ne l'est pas


def test_chart_calculator_includes_degree_analysis_for_every_planet():
    chart = calculate_natal_chart(**BIRTH_KWARGS, optional_points=[])
    names = {d["planet"] for d in chart["degree_analysis"]}
    assert names == {p["name"] for p in chart["planets"]}
    for entry in chart["degree_analysis"]:
        assert 0 <= entry["degree_value"] <= 29
        assert 1 <= entry["house"] <= 12
