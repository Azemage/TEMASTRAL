from app.core import ephemeris
from app.core.chart_calculator import calculate_natal_chart
from app.core.lifespan_estimate import (
    _adjust_for_aspects,
    _dignity_score_at,
    _year_level,
    estimate_lifespan,
    find_alcocoden,
    find_hyleg,
)

BIRTH_KWARGS = dict(
    birth_date="1990-05-15",
    birth_time="14:32:00",
    time_known=True,
    timezone="Europe/Paris",
    latitude=45.7640,
    longitude=4.8357,
)


def _chart():
    return calculate_natal_chart(**BIRTH_KWARGS)


# ---------------------------------------------------------------------
# Dignité essentielle en un point donné (pas à la position propre de la planète)
# ---------------------------------------------------------------------
def test_dignity_score_sums_independent_layers():
    # Mars à 2° Bélier : domicile (Mars) + décan 1 Bélier (Mars) = 5 + 1 = 6.
    # Terme 0-6° Bélier = Jupiter (pas Mars), donc pas de point de terme ici.
    assert _dignity_score_at("Mars", "Aries", 2.0, is_day_chart=True) == 6


def test_dignity_score_exact_exaltation():
    # Soleil à 19° Bélier : exaltation exacte (+4), pas domicile/décan/terme au même point.
    score = _dignity_score_at("Sun", "Aries", 19.0, is_day_chart=True)
    assert score >= 4


def test_dignity_score_zero_when_no_essential_dignity():
    # Mercure à 2° Bélier n'a aucune dignité essentielle en ce point (ni domicile, ni
    # exaltation, ni triplicité feu — jour/nuit/participant sont Soleil/Jupiter/Saturne —,
    # ni terme 0-6° = Jupiter, ni décan 1 = Mars).
    assert _dignity_score_at("Mercury", "Aries", 2.0, is_day_chart=True) == 0


def test_dignity_score_triplicity_depends_on_sect():
    # Bélier = feu. Jour -> Soleil régent de secte ; nuit -> Jupiter.
    day_score = _dignity_score_at("Sun", "Aries", 2.0, is_day_chart=True)
    night_score = _dignity_score_at("Jupiter", "Aries", 2.0, is_day_chart=False)
    assert day_score > 0
    assert night_score > 0


# ---------------------------------------------------------------------
# Hyleg : hiérarchie à 4 niveaux
# ---------------------------------------------------------------------
def test_find_hyleg_always_returns_a_point_in_a_hylegiacal_house():
    chart = _chart()
    hyleg = find_hyleg(chart, prenatal_syzygy_longitude=chart["angles"]["ascendant"]["absolute_longitude"])
    assert hyleg["house"] in {1, 7, 9, 10, 11}


def test_find_hyleg_falls_back_to_ascendant_when_nothing_else_qualifies():
    # Thème synthétique où rien n'est en maison hylégiacale : doit retomber sur l'Ascendant.
    chart = {
        "is_day_chart": True,
        "planets": [{"name": "Sun", "house": 2, "absolute_longitude": 10.0, "sign": "Aries", "degree": 10.0}],
        "lots": [{"name": "Fortune", "house": 3, "absolute_longitude": 40.0, "sign": "Taurus", "degree": 10.0}],
        "houses": [{"number": i + 1, "absolute_longitude": (i * 30.0)} for i in range(12)],
        "angles": {"ascendant": {"absolute_longitude": 0.0, "sign": "Aries", "degree": 0.0}},
    }
    # Sizygie prénatale placée elle aussi en maison non-hylégiacale (maison 2, [30°,60°)).
    hyleg = find_hyleg(chart, prenatal_syzygy_longitude=45.0)
    assert hyleg["name"] == "Ascendant"
    assert hyleg["house"] == 1


# ---------------------------------------------------------------------
# Alcocoden
# ---------------------------------------------------------------------
def test_find_alcocoden_returns_none_when_nothing_aspects_hyleg():
    hyleg = {"name": "Ascendant", "longitude": 0.0, "sign": "Aries", "degree": 0.0, "house": 1}
    chart = {
        "is_day_chart": True,
        "planets": [{"name": "Saturn", "absolute_longitude": 44.0, "sign": "Taurus", "degree": 14.0}],
    }
    assert find_alcocoden(hyleg, chart) is None


def test_find_alcocoden_picks_highest_dignity_among_aspecting_planets():
    # Hyleg à 0° Bélier. Mars (domicile + décan Bélier) en carré exact (90°) depuis 0° Cancer ;
    # Vénus (aucune dignité en Bélier) en trigone exact (120°) depuis 0° Sagittaire.
    hyleg = {"name": "Ascendant", "longitude": 0.0, "sign": "Aries", "degree": 0.0, "house": 1}
    chart = {
        "is_day_chart": True,
        "planets": [
            {"name": "Mars", "absolute_longitude": 90.0, "sign": "Cancer", "degree": 0.0},
            {"name": "Venus", "absolute_longitude": 240.0, "sign": "Sagittarius", "degree": 0.0},
        ],
    }
    alcocoden = find_alcocoden(hyleg, chart)
    assert alcocoden["name"] == "Mars"
    assert alcocoden["dignity_score_at_hyleg"] > 0


def test_adjust_for_aspects_benefic_adds_scaled_by_own_dignity():
    # Vénus en trigone au Soleil (Alcocoden) : dignité de Vénus en Taureau 0° = domicile(5) +
    # triplicité terre/jour(3) + terme 0-8°(2) = 10/15 -> facteur 0.667 ; années mineures de
    # Vénus = 8 -> delta = 8 * 10/15 ≈ 5.33.
    chart = {
        "is_day_chart": True,
        "aspects": [{"planet1": "Sun", "planet2": "Venus", "type": "trine"}],
        "planets": [{"name": "Venus", "sign": "Taurus", "degree": 0.0}],
    }
    total, details = _adjust_for_aspects(0, "Sun", chart)
    assert total == 5.33
    assert details == [{"planet": "Venus", "aspect_type": "trine", "delta_years": 5.33}]


def test_adjust_for_aspects_malefic_subtracts():
    chart = {
        "is_day_chart": True,
        "aspects": [{"planet1": "Sun", "planet2": "Mars", "type": "square"}],
        "planets": [{"name": "Mars", "sign": "Aries", "degree": 2.0}],
    }
    total, details = _adjust_for_aspects(20, "Sun", chart)
    assert total < 20
    assert details[0]["delta_years"] < 0


# ---------------------------------------------------------------------
# Niveau d'années (menores/medios/mayores)
# ---------------------------------------------------------------------
def test_year_level_major_when_angular_and_well_dignified():
    chart = {"planets": [{"name": "Jupiter", "house": 10, "sign": "Cancer"}]}  # Jupiter exalté en Cancer
    assert _year_level("Jupiter", chart) == "major"


def test_year_level_minor_when_cadent_and_poorly_dignified():
    chart = {"planets": [{"name": "Jupiter", "house": 6, "sign": "Gemini"}]}  # Jupiter en détriment en Gémeaux
    assert _year_level("Jupiter", chart) == "minor"


# ---------------------------------------------------------------------
# Intégration : le pipeline complet ne doit jamais planter et porte toujours l'avertissement
# ---------------------------------------------------------------------
def test_estimate_lifespan_always_includes_warning_and_valid_structure():
    chart = _chart()
    jd_ut = ephemeris.local_datetime_to_jd_ut(
        BIRTH_KWARGS["birth_date"], BIRTH_KWARGS["birth_time"], BIRTH_KWARGS["timezone"]
    )
    result = estimate_lifespan(chart, jd_ut)
    assert "warning" in result
    assert "available" in result
    if result["available"]:
        assert result["year_level"] in {"minor", "medium", "major"}
        assert result["estimated_years"] > 0
