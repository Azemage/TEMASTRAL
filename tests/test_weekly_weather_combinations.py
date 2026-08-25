"""Bibliothèque de combinaisons hebdomadaires (voir app/core/weekly_weather_combinations.py et
bibliotheque_combinaisons_hebdomadaires.md) — formules déterministes, aucun appel LLM."""

from datetime import date

from app.core.weekly_weather import compute_weekly_collective
from app.core.weekly_weather_combinations import (
    build_aspect_combination_lines,
    build_critical_degree_lines,
    build_curated_combination_lines,
    build_position_lines,
    compute_weekly_combination_lines,
)

_ASPECT = {"date": "2027-02-05", "planet_a": "Venus", "planet_b": "Neptune", "aspect_type": "opposition", "aspect_type_fr": "opposition", "score": 4}


# ---------------------------------------------------------------------------
# Section 1 : formule d'aspect rapide x lente
# ---------------------------------------------------------------------------
def test_build_aspect_combination_lines_assembles_the_formula():
    lines = build_aspect_combination_lines([_ASPECT], kind="aspect_rapide_lente")
    assert len(lines) == 1
    line = lines[0]
    assert line["kind"] == "aspect_rapide_lente"
    assert line["text"].endswith("cette semaine.")
    assert line["text"][0].isupper()
    # Les 3 briques de la formule doivent apparaître dans le texte assemblé.
    assert "relations affectives" in line["text"]  # thème Vénus
    assert "confronte" in line["text"] or "composer" in line["text"]  # modulateur d'opposition
    assert "idéalisation" in line["text"]  # thème Neptune


def test_build_aspect_combination_lines_is_deterministic_not_random():
    a = build_aspect_combination_lines([_ASPECT], kind="aspect_rapide_lente")
    b = build_aspect_combination_lines([_ASPECT], kind="aspect_rapide_lente")
    assert a == b


def test_build_aspect_combination_lines_uses_node_axis_wording():
    aspect = {"date": "2027-02-05", "planet_a": "Mars", "planet_b": "north_node", "aspect_type": "square", "aspect_type_fr": "carré", "score": 4}
    lines = build_aspect_combination_lines([aspect], kind="aspect_rapide_lente")
    assert len(lines) == 1
    assert "zone de confort" in lines[0]["text"] or "croissance" in lines[0]["text"]


def test_build_aspect_combination_lines_skips_unrecognized_aspect_type():
    aspect = {**_ASPECT, "aspect_type": "quintile"}
    assert build_aspect_combination_lines([aspect], kind="aspect_rapide_lente") == []


# ---------------------------------------------------------------------------
# Section 2 : position dans le signe (réutilise planets_in_signs_full.json)
# ---------------------------------------------------------------------------
def test_build_position_lines_covers_moon_and_three_fast_planets():
    fast_planets = [
        {"name": "Mercury", "sign_start": "Gemini"},
        {"name": "Venus", "sign_start": "Taurus"},
        {"name": "Mars", "sign_start": "Aries"},
    ]
    lines = build_position_lines("Cancer", fast_planets)
    assert len(lines) == 4
    planets = {line["planet"] for line in lines}
    assert planets == {"Moon", "Mercury", "Venus", "Mars"}
    moon_line = next(line for line in lines if line["planet"] == "Moon")
    assert "La Lune en Cancer" in moon_line["text"]
    assert ":" in moon_line["text"]  # la synthèse de planets_in_signs_full.json suit le ":"


# ---------------------------------------------------------------------------
# Section 3 : degrés remarquables
# ---------------------------------------------------------------------------
def test_build_critical_degree_lines_detects_anaretic_degree():
    daily = {"Venus": [{"date": "2027-02-03", "sign": "Gemini", "degree": 29.3}]}
    lines = build_critical_degree_lines(daily)
    assert len(lines) == 1
    assert lines[0]["degree_type"] == "anaretic"
    assert lines[0]["planet"] == "Venus"


def test_build_critical_degree_lines_detects_cardinal_critical_degree():
    daily = {"Mars": [{"date": "2027-02-03", "sign": "Aries", "degree": 13.2}]}
    lines = build_critical_degree_lines(daily)
    assert len(lines) == 1
    assert lines[0]["degree_type"] == "cardinal"


def test_build_critical_degree_lines_detects_aries_point_specifically():
    daily = {"Mercury": [{"date": "2027-02-03", "sign": "Aries", "degree": 0.2}]}
    lines = build_critical_degree_lines(daily)
    assert len(lines) == 1
    assert lines[0]["degree_type"] == "aries_point"


def test_build_critical_degree_lines_ignores_ordinary_degrees():
    daily = {"Mars": [{"date": "2027-02-03", "sign": "Aries", "degree": 15.0}]}
    assert build_critical_degree_lines(daily) == []


def test_build_critical_degree_lines_deduplicates_consecutive_days_in_orb():
    daily = {"Mars": [
        {"date": "2027-02-03", "sign": "Aries", "degree": 12.8},
        {"date": "2027-02-04", "sign": "Aries", "degree": 13.3},
    ]}
    lines = build_critical_degree_lines(daily)
    assert len(lines) == 1  # même degré remarquable touché deux jours de suite : une seule ligne


# ---------------------------------------------------------------------------
# Section 4 : combinaisons éditoriales
# ---------------------------------------------------------------------------
def _base_ctx():
    return {
        "fast_planets": [
            {"name": "Mercury", "retrograde_start": False, "retrograde_end": False},
            {"name": "Venus", "retrograde_start": False, "retrograde_end": False},
            {"name": "Mars", "retrograde_start": False, "retrograde_end": False},
        ],
        "slow_planet_signs": {},
        "generational_aspects": [],
        "moon_generational_aspects": [],
    }


def test_curated_combination_mercury_retrograde_in_earth_slow_climate():
    ctx = _base_ctx()
    ctx["fast_planets"][0]["retrograde_start"] = True
    ctx["fast_planets"][0]["retrograde_end"] = True
    ctx["slow_planet_signs"] = {"Jupiter": "Taurus", "Saturn": "Capricorn"}
    lines = build_curated_combination_lines(ctx)
    assert any(line["id"] == "mercury_rx_earth_slow" for line in lines)


def test_curated_combination_venus_mars_same_hard_aspect_target():
    ctx = _base_ctx()
    ctx["generational_aspects"] = [
        {"planet_a": "Venus", "planet_b": "Saturn", "aspect_type": "square"},
        {"planet_a": "Mars", "planet_b": "Saturn", "aspect_type": "opposition"},
    ]
    lines = build_curated_combination_lines(ctx)
    assert any(line["id"] == "venus_mars_same_hard_aspect" for line in lines)


def test_curated_combination_moon_pluto_hard_aspect():
    ctx = _base_ctx()
    ctx["moon_generational_aspects"] = [{"planet_a": "Moon", "planet_b": "Pluto", "aspect_type": "square"}]
    lines = build_curated_combination_lines(ctx)
    assert any(line["id"] == "moon_pluto_hard_aspect" for line in lines)


def test_curated_combination_none_detected_returns_empty_list():
    assert build_curated_combination_lines(_base_ctx()) == []


# ---------------------------------------------------------------------------
# Assemblage final
# ---------------------------------------------------------------------------
def test_compute_weekly_combination_lines_always_includes_all_position_lines():
    """Même sans aucun signal notable (aucun aspect générationnel, aucune combinaison
    éditoriale), les 4 lignes de position doivent rester présentes — voir doc source, section
    5.1 point 4."""
    fast_planets = [
        {"name": "Mercury", "sign_start": "Gemini", "retrograde_start": False, "retrograde_end": False},
        {"name": "Venus", "sign_start": "Taurus", "retrograde_start": False, "retrograde_end": False},
        {"name": "Mars", "sign_start": "Aries", "retrograde_start": False, "retrograde_end": False},
    ]
    moon_path = [{"sign": "Cancer"}]
    lines = compute_weekly_combination_lines(
        fast_planets=fast_planets, moon_path=moon_path, generational_aspects=[], moon_generational_aspects=[],
        transit_transit_aspects=[], daily_fast_positions={}, slow_planet_signs={},
    )
    position_lines = [line for line in lines if line["kind"] == "position_signe"]
    assert len(position_lines) == 4


def test_compute_weekly_combination_lines_covers_fast_fast_aspects_too():
    """Régression : les aspects entre deux planètes rapides (ex. Lune conjonction Vénus,
    transit_transit_aspects) doivent AUSSI recevoir une phrase descriptive, pas seulement les
    aspects vers les planètes lentes — le bug initial ne branchait `transit_transit_aspects`
    nulle part dans compute_weekly_combination_lines, donc ces aspects n'apparaissaient que
    comme un libellé technique nu dans le tableau séparé, jamais dans le résumé de combinaisons."""
    fast_planets = [
        {"name": "Mercury", "sign_start": "Gemini", "retrograde_start": False, "retrograde_end": False},
        {"name": "Venus", "sign_start": "Taurus", "retrograde_start": False, "retrograde_end": False},
        {"name": "Mars", "sign_start": "Aries", "retrograde_start": False, "retrograde_end": False},
    ]
    moon_path = [{"sign": "Cancer"}]
    fast_fast_aspect = {
        "date": "2027-02-05", "planet_a": "Moon", "planet_b": "Venus",
        "aspect_type": "conjunction", "aspect_type_fr": "conjonction", "score": 3,
    }
    lines = compute_weekly_combination_lines(
        fast_planets=fast_planets, moon_path=moon_path, generational_aspects=[], moon_generational_aspects=[],
        transit_transit_aspects=[fast_fast_aspect], daily_fast_positions={}, slow_planet_signs={},
    )
    fast_fast_lines = [line for line in lines if line["kind"] == "aspect_rapide_rapide"]
    assert len(fast_fast_lines) == 1
    assert fast_fast_lines[0]["planet"] == "Moon"
    assert fast_fast_lines[0]["planet_b"] == "Venus"
    assert "cette semaine." in fast_fast_lines[0]["text"]


def test_compute_weekly_collective_combination_lines_are_capped_and_json_serializable():
    import json

    data = compute_weekly_collective(date(2027, 2, 3))
    assert 0 < len(data["combination_lines"]) <= 10
    assert all(line["kind"] == "position_signe" for line in data["combination_lines"][-4:])
    json.dumps(data)


def test_compute_weekly_collective_includes_fast_fast_aspect_lines_for_reference_week():
    """Sur la semaine de référence (2027-02-03, déjà utilisée ailleurs dans ce fichier), au
    moins un aspect rapide-rapide (transit_transit_aspects) doit se traduire en ligne de
    combinaison — vérifie l'intégration bout en bout, pas seulement l'unité ci-dessus."""
    data = compute_weekly_collective(date(2027, 2, 3))
    assert len(data["transit_transit_aspects"]) > 0
    fast_fast_lines = [line for line in data["combination_lines"] if line["kind"] == "aspect_rapide_rapide"]
    assert len(fast_fast_lines) > 0


def test_compute_weekly_collective_combination_lines_prioritize_fast_over_moon_aspects():
    """La Lune forme beaucoup plus d'aspects générationnels par semaine (elle change de signe
    tous les ~2,5 jours) : sans priorisation, elle inonderait le budget de ~10 lignes et
    évincerait les positions garanties — voir compute_weekly_combination_lines."""
    data = compute_weekly_collective(date(2027, 2, 3))
    assert len(data["moon_generational_aspects"]) > 5  # confirme que le risque de submersion est réel cette semaine-là
    position_lines = [line for line in data["combination_lines"] if line["kind"] == "position_signe"]
    assert len(position_lines) == 4  # jamais évincées malgré le grand nombre d'aspects lunaires
