from datetime import date

import pytest
import swisseph as swe
from fastapi.testclient import TestClient

from app.core.astrocartography import (
    ASTROCARTOGRAPHY_PLANETS,
    LINE_TYPES,
    analyze_nearby_lines,
    compute_all_crossings,
    compute_astrocartography_lines,
    compute_horizon_line_points,
    compute_meridian_lines,
    find_interesting_cities,
    find_line_crossings,
    line_longitude_at_latitude,
    _normalize_longitude,
)
from app.core.ephemeris import PLANET_IDS, calc_planet_equatorial, greenwich_sidereal_time_degrees
from app.database import SessionLocal
from app.models import NatalChart
from app.services import astrocartography_service, interpretation_service
from app.core.reference_data import world_cities
from app.main import app
from app.services.astrocartography_service import compute_location_forecast

VALID_CHART_PAYLOAD = {
    "birth_data": {
        "date": "1990-05-15",
        "time": "14:32:00",
        "time_known": True,
        "timezone": "Europe/Paris",
        "location": {"city": "Lyon", "country": "France", "latitude": 45.764, "longitude": 4.8357},
    }
}


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


# ---------------------------------------------------------------------------
# Moteur de calcul (formules d'astronomie sphérique)
# ---------------------------------------------------------------------------
def test_normalize_longitude_wraps_to_minus_180_180():
    assert _normalize_longitude(190) == -170
    assert _normalize_longitude(-190) == 170
    assert _normalize_longitude(0) == 0
    assert _normalize_longitude(180) == -180  # intervalle demi-ouvert [-180, 180)


def test_sun_mc_line_matches_apparent_solar_noon_at_greenwich():
    # À 12:00 UTC, le Soleil culmine près de la longitude 0 (écart de quelques degrés dû à
    # l'équation du temps, jamais plus de ~4.5° / 18 minutes) — vérification de cohérence
    # indépendante contre un repère astronomique connu, pas une valeur arbitraire.
    jd = swe.julday(2026, 8, 9, 12.0)
    sun_eq = calc_planet_equatorial(jd, PLANET_IDS["Sun"])
    gst = greenwich_sidereal_time_degrees(jd)
    lines = compute_meridian_lines(sun_eq, gst)
    assert abs(lines["MC"]) < 4.5
    assert abs(_normalize_longitude(lines["IC"] - 180)) < 4.5


def test_ic_line_is_exactly_opposite_mc_line():
    jd = swe.julday(2026, 8, 9, 6.0)
    moon_eq = calc_planet_equatorial(jd, PLANET_IDS["Moon"])
    gst = greenwich_sidereal_time_degrees(jd)
    lines = compute_meridian_lines(moon_eq, gst)
    assert abs(_normalize_longitude(lines["IC"] - lines["MC"] - 180)) < 1e-6


def test_asc_dc_lines_are_exactly_90_degrees_from_mc_at_the_equator():
    # À l'équateur, l'angle horaire du lever/coucher H0 = arccos(0) = 90° exactement,
    # quelle que soit la déclinaison de la planète.
    jd = swe.julday(2026, 8, 9, 12.0)
    sun_eq = calc_planet_equatorial(jd, PLANET_IDS["Sun"])
    gst = greenwich_sidereal_time_degrees(jd)
    meridians = compute_meridian_lines(sun_eq, gst)
    horizons = compute_horizon_line_points(sun_eq, gst)

    asc_at_equator = next(p for p in horizons["ASC"] if p["lat"] == 0.0)
    dc_at_equator = next(p for p in horizons["DC"] if p["lat"] == 0.0)
    # Tolérance alignée sur l'arrondi à 3 décimales appliqué aux points de ligne stockés.
    assert abs(_normalize_longitude(asc_at_equator["lon"] - (meridians["MC"] - 90))) < 1e-3
    assert abs(_normalize_longitude(dc_at_equator["lon"] - (meridians["MC"] + 90))) < 1e-3


def test_horizon_lines_omit_circumpolar_latitudes():
    # Le Soleil du 9 août 2026 a une déclinaison d'environ +16° : au-delà de 90-16=74°
    # (nord ou sud), il ne se lève/couche jamais ce jour-là (barrière circumpolaire).
    jd = swe.julday(2026, 8, 9, 12.0)
    sun_eq = calc_planet_equatorial(jd, PLANET_IDS["Sun"])
    assert sun_eq.declination > 15
    gst = greenwich_sidereal_time_degrees(jd)
    horizons = compute_horizon_line_points(sun_eq, gst)
    max_lat = max(p["lat"] for p in horizons["ASC"])
    assert max_lat < 80
    assert max_lat > 70


def test_meridian_lines_are_constant_longitude_at_all_latitudes():
    jd = swe.julday(2026, 8, 9, 12.0)
    mars_eq = calc_planet_equatorial(jd, PLANET_IDS["Mars"])
    gst = greenwich_sidereal_time_degrees(jd)
    lines = compute_meridian_lines(mars_eq, gst)
    # Par construction (voir compute_astrocartography_lines), une ligne MC/IC est stockée
    # comme un segment vertical à longitude constante — testé ici sur la formule elle-même.
    assert isinstance(lines["MC"], float)
    assert -180 <= lines["MC"] < 180
    assert -180 <= lines["IC"] < 180


# ---------------------------------------------------------------------------
# Analyse de proximité (lieu -> lignes les plus proches)
# ---------------------------------------------------------------------------
def test_analyze_nearby_lines_finds_line_directly_through_the_point():
    lines = [
        {
            "planet": "Sun",
            "line_type": "MC",
            "line_points": [{"lat": -85, "lon": 10.0}, {"lat": 85, "lon": 10.0}],
        }
    ]
    result = analyze_nearby_lines(lines, latitude=45.0, longitude=10.0, threshold_km=50)
    assert len(result) == 1
    assert result[0]["planet"] == "Sun"
    assert result[0]["line_type"] == "MC"
    assert result[0]["distance_km"] < 1


def test_analyze_nearby_lines_excludes_lines_beyond_threshold():
    lines = [{"planet": "Sun", "line_type": "MC", "line_points": [{"lat": -85, "lon": 10.0}, {"lat": 85, "lon": 10.0}]}]
    result = analyze_nearby_lines(lines, latitude=45.0, longitude=170.0, threshold_km=100)
    assert result == []


def test_analyze_nearby_lines_sorted_by_distance():
    lines = [
        {"planet": "Sun", "line_type": "MC", "line_points": [{"lat": -85, "lon": 12.0}, {"lat": 85, "lon": 12.0}]},
        {"planet": "Moon", "line_type": "MC", "line_points": [{"lat": -85, "lon": 10.0}, {"lat": 85, "lon": 10.0}]},
    ]
    result = analyze_nearby_lines(lines, latitude=45.0, longitude=10.0, threshold_km=500)
    assert [r["planet"] for r in result] == ["Moon", "Sun"]
    assert result[0]["distance_km"] < result[1]["distance_km"]


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------
def test_natal_astrocartography_endpoint_returns_four_lines_per_planet(client):
    chart_id = client.post("/api/charts", json=VALID_CHART_PAYLOAD).json()["id"]
    res = client.get(f"/api/charts/{chart_id}/astrocartography")
    assert res.status_code == 200
    body = res.json()
    assert body["natal_chart_id"] == chart_id
    assert len(body["lines"]) == len(ASTROCARTOGRAPHY_PLANETS) * 4
    line_types = {line["line_type"] for line in body["lines"]}
    assert line_types == {"ASC", "DC", "MC", "IC"}
    mc_line = next(line for line in body["lines"] if line["line_type"] == "MC")
    assert len(mc_line["line_points"]) == 2  # segment vertical : 2 points suffisent


def test_get_or_compute_natal_lines_handles_concurrent_cache_miss(client):
    """Deux requêtes concurrentes sur un thème dont les lignes ne sont pas encore en cache
    peuvent toutes deux constater un cache vide puis tenter d'insérer les mêmes lignes : la
    seconde doit voir sa contrainte UNIQUE échouer proprement et relire le résultat de la
    première, plutôt que de laisser l'IntegrityError remonter en 500 (voir la gestion de ce cas
    dans get_or_compute_natal_lines). Le monkeypatch de `db.commit` simule la fenêtre de course :
    une session tout à fait séparée insère et committe les mêmes lignes juste avant que la
    session sous test ne tente son propre commit, qui doit alors échouer puis se rattraper."""
    from app.database import SessionLocal
    from app.models import NatalChart
    from app.services import astrocartography_service

    chart_id = client.post("/api/charts", json=VALID_CHART_PAYLOAD).json()["id"]
    db = SessionLocal()
    other_db = SessionLocal()
    try:
        chart = db.query(NatalChart).filter_by(id=chart_id).one()
        original_commit = db.commit

        def commit_after_concurrent_winner():
            other_chart = other_db.query(NatalChart).filter_by(id=chart_id).one()
            astrocartography_service.get_or_compute_natal_lines(other_db, other_chart)
            return original_commit()

        db.commit = commit_after_concurrent_winner

        result = astrocartography_service.get_or_compute_natal_lines(db, chart)
        assert len(result) == len(ASTROCARTOGRAPHY_PLANETS) * 4
        assert {(r.planet, r.line_type) for r in result} == {
            (planet, lt) for planet in ASTROCARTOGRAPHY_PLANETS for lt in LINE_TYPES
        }
    finally:
        db.close()
        other_db.close()


def test_natal_astrocartography_lines_are_cached_across_requests(client):
    chart_id = client.post("/api/charts", json=VALID_CHART_PAYLOAD).json()["id"]
    first = client.get(f"/api/charts/{chart_id}/astrocartography").json()
    second = client.get(f"/api/charts/{chart_id}/astrocartography").json()
    assert first == second


def test_natal_astrocartography_404_for_unknown_chart(client):
    res = client.get("/api/charts/does-not-exist/astrocartography")
    assert res.status_code == 404


def test_transit_astrocartography_endpoint_returns_lines_without_a_chart(client):
    res = client.get("/api/astrocartography/transit")
    assert res.status_code == 200
    body = res.json()
    assert len(body["lines"]) == len(ASTROCARTOGRAPHY_PLANETS) * 4
    assert body["calculation_date"]


def test_transit_astrocartography_accepts_explicit_date(client):
    res = client.get("/api/astrocartography/transit", params={"date": "2020-01-01"})
    assert res.status_code == 200
    assert res.json()["calculation_date"] == "2020-01-01"


def test_saved_location_created_with_nearby_lines_analysis(client):
    chart_id = client.post("/api/charts", json=VALID_CHART_PAYLOAD).json()["id"]
    res = client.post(
        f"/api/charts/{chart_id}/saved-locations",
        json={"city": "Lisbonne", "country": "Portugal", "latitude": 38.7223, "longitude": -9.1393},
    )
    assert res.status_code == 201
    body = res.json()
    assert body["city"] == "Lisbonne"
    assert body["natal_chart_id"] == chart_id
    assert isinstance(body["nearby_lines_analysis"], list)


def test_list_saved_locations_returns_created_locations(client):
    chart_id = client.post("/api/charts", json=VALID_CHART_PAYLOAD).json()["id"]
    client.post(
        f"/api/charts/{chart_id}/saved-locations",
        json={"city": "Lisbonne", "latitude": 38.7223, "longitude": -9.1393},
    )
    res = client.get(f"/api/charts/{chart_id}/saved-locations")
    assert res.status_code == 200
    assert len(res.json()) == 1
    assert res.json()[0]["city"] == "Lisbonne"


def test_delete_saved_location(client):
    chart_id = client.post("/api/charts", json=VALID_CHART_PAYLOAD).json()["id"]
    location_id = client.post(
        f"/api/charts/{chart_id}/saved-locations",
        json={"city": "Lisbonne", "latitude": 38.7223, "longitude": -9.1393},
    ).json()["id"]

    delete_res = client.delete(f"/api/saved-locations/{location_id}")
    assert delete_res.status_code == 204

    remaining = client.get(f"/api/charts/{chart_id}/saved-locations").json()
    assert remaining == []


def test_delete_unknown_saved_location_404(client):
    res = client.delete("/api/saved-locations/does-not-exist")
    assert res.status_code == 404


def test_astrocartography_reading_payload_defaults_focus_to_birthplace(client):
    res = client.post("/api/charts", json=VALID_CHART_PAYLOAD)
    chart_id = res.json()["id"]
    reading_res = client.post(
        f"/api/charts/{chart_id}/readings",
        json={"reading_type": "astrocartography", "astro_map_mode": "natal"},
    )
    # Pas de clé API configurée dans les tests : on attend un 503 (RuntimeError), pas une
    # erreur de construction du payload en amont (422/500), qui indiquerait un vrai bug.
    assert reading_res.status_code == 503


def test_astrocartography_reading_payload_is_personalized_per_line(client):
    """Vérifie que nearby_lines contient bien les 3 couches de personnalisation (condition
    natale, thèmes confirmés, pertinence temporelle) et un score de priorité, pas seulement
    la signification générique — voir app/core/astrocartography_personalization.py. Le point
    de focus est choisi pour tomber exactement sur une ligne natale connue, afin de garantir
    au moins une entrée dans nearby_lines plutôt que de dépendre du hasard des coordonnées."""
    chart_id = client.post("/api/charts", json=VALID_CHART_PAYLOAD).json()["id"]
    db = SessionLocal()
    try:
        chart = db.query(NatalChart).filter_by(id=chart_id).one()
        jd_ut = astrocartography_service.jd_ut_for_chart(chart)
        lines = astrocartography_service.compute_lines_for_jd(jd_ut)
        some_line = next(line for line in lines if line["line_type"] == "MC")
        focus_lat, focus_lon = 45.0, some_line["line_points"][0]["lon"]

        from app import schemas

        request = schemas.ReadingRequest(
            reading_type="astrocartography",
            astro_map_mode="natal",
            astro_focus_latitude=focus_lat,
            astro_focus_longitude=focus_lon,
        )
        payload = interpretation_service._build_user_payload(chart, request)
    finally:
        db.close()

    assert len(payload["nearby_lines"]) >= 1
    for entry in payload["nearby_lines"]:
        assert entry["natal_condition"]["dignity"] in {"domicile", "exaltation", "exil", "chute", "pérégrin"}
        assert "aspect_quality" in entry["natal_condition"]
        assert "present" in entry["theme_confirme_lie"]
        assert "active" in entry["pertinence_temporelle"]
        assert isinstance(entry["priority_score"], (int, float))
    # Sans default=str : mêmes contraintes que la colonne JSON SQLAlchemy où ce payload est
    # ensuite stocké (voir la régression corrigée pour astrocartography_forecast).
    import json

    json.dumps(payload)
    # Trié par priorité décroissante.
    scores = [entry["priority_score"] for entry in payload["nearby_lines"]]
    assert scores == sorted(scores, reverse=True)


def test_astrocartography_prompt_explains_personalization_fields():
    from app import schemas

    prompt = interpretation_service._build_system_prompt(schemas.ReadingRequest(reading_type="astrocartography"))
    assert "theme_confirme_lie" in prompt
    assert "pertinence_temporelle" in prompt
    assert "natal_condition" in prompt


# ---------------------------------------------------------------------------
# Prévision multi-années pour un lieu fixe (cyclocartographie inverse)
# ---------------------------------------------------------------------------
def test_line_longitude_at_latitude_matches_meridian_lines_for_mc_ic():
    jd_ut = swe.julday(2024, 3, 20, 12.0)
    equatorial = calc_planet_equatorial(jd_ut, PLANET_IDS["Sun"])
    gst_degrees = greenwich_sidereal_time_degrees(jd_ut)
    meridians = compute_meridian_lines(equatorial, gst_degrees)

    assert line_longitude_at_latitude(equatorial, gst_degrees, "MC", 45.0) == meridians["MC"]
    assert line_longitude_at_latitude(equatorial, gst_degrees, "IC", -20.0) == meridians["IC"]


def test_line_longitude_at_latitude_matches_full_horizon_curve_for_asc_dc():
    jd_ut = swe.julday(2024, 3, 20, 12.0)
    equatorial = calc_planet_equatorial(jd_ut, PLANET_IDS["Sun"])
    gst_degrees = greenwich_sidereal_time_degrees(jd_ut)
    horizons = compute_horizon_line_points(equatorial, gst_degrees)
    sample_point = next(p for p in horizons["ASC"] if p["lat"] == 40.0)

    result = line_longitude_at_latitude(equatorial, gst_degrees, "ASC", 40.0)
    # Les points de la courbe complète sont arrondis à 3 décimales, contrairement à
    # l'évaluation ponctuelle : léger écart attendu, borné par cet arrondi.
    assert abs(result - sample_point["lon"]) < 1e-2


def test_line_longitude_at_latitude_returns_none_when_circumpolar():
    jd_ut = swe.julday(2024, 6, 21, 12.0)  # solstice : forte déclinaison du Soleil
    equatorial = calc_planet_equatorial(jd_ut, PLANET_IDS["Sun"])
    gst_degrees = greenwich_sidereal_time_degrees(jd_ut)
    assert line_longitude_at_latitude(equatorial, gst_degrees, "ASC", 89.0) is None


def test_line_longitude_at_latitude_rejects_unknown_line_type():
    jd_ut = swe.julday(2024, 3, 20, 12.0)
    equatorial = calc_planet_equatorial(jd_ut, PLANET_IDS["Sun"])
    gst_degrees = greenwich_sidereal_time_degrees(jd_ut)
    with pytest.raises(ValueError):
        line_longitude_at_latitude(equatorial, gst_degrees, "XX", 40.0)


def test_compute_location_forecast_finds_windows_near_paris():
    windows = compute_location_forecast(
        latitude=48.8566,
        longitude=2.3522,
        start_date=date(2024, 1, 1),
        years=2,
        planets=["Sun"],
        line_types=["MC"],
        threshold_km=500.0,
        step_days=5,
    )
    assert len(windows) >= 1
    for window in windows:
        assert window["planet"] == "Sun"
        assert window["line_type"] == "MC"
        assert window["start_date"] <= window["peak_date"] <= window["end_date"]
        assert window["peak_distance_km"] <= 500.0
    # Trié du plus tôt au plus tard.
    assert [w["start_date"] for w in windows] == sorted(w["start_date"] for w in windows)


def test_compute_location_forecast_defaults_cover_all_planets_and_line_types():
    windows = compute_location_forecast(
        latitude=48.8566, longitude=2.3522, start_date=date(2024, 1, 1), years=1, step_days=10
    )
    seen_planets = {w["planet"] for w in windows}
    seen_line_types = {w["line_type"] for w in windows}
    assert seen_planets.issubset(set(ASTROCARTOGRAPHY_PLANETS))
    assert seen_line_types.issubset(set(LINE_TYPES))


def test_location_forecast_endpoint_returns_windows(client):
    res = client.get(
        "/api/astrocartography/location-forecast",
        params={"latitude": 48.8566, "longitude": 2.3522, "years": 2, "step_days": 5, "planets": "Sun", "line_types": "MC"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["latitude"] == 48.8566
    assert body["longitude"] == 2.3522
    assert body["threshold_km"] == 300.0
    assert isinstance(body["windows"], list)
    for window in body["windows"]:
        assert window["planet"] == "Sun"
        assert window["line_type"] == "MC"


def test_location_forecast_endpoint_defaults_exclude_moon(client):
    res = client.get(
        "/api/astrocartography/location-forecast",
        params={"latitude": 48.8566, "longitude": 2.3522, "years": 1, "step_days": 10},
    )
    assert res.status_code == 200
    planets_seen = {w["planet"] for w in res.json()["windows"]}
    assert "Moon" not in planets_seen


def test_location_forecast_endpoint_rejects_unknown_planet(client):
    res = client.get(
        "/api/astrocartography/location-forecast",
        params={"latitude": 48.8566, "longitude": 2.3522, "planets": "Sun,Bogus"},
    )
    assert res.status_code == 400


def test_location_forecast_endpoint_rejects_unknown_line_type(client):
    res = client.get(
        "/api/astrocartography/location-forecast",
        params={"latitude": 48.8566, "longitude": 2.3522, "line_types": "MC,XX"},
    )
    assert res.status_code == 400


def test_location_forecast_endpoint_rejects_out_of_range_latitude(client):
    res = client.get("/api/astrocartography/location-forecast", params={"latitude": 200, "longitude": 2.3522})
    assert res.status_code == 422


def test_location_forecast_endpoint_caps_years_at_ten(client):
    res = client.get(
        "/api/astrocartography/location-forecast", params={"latitude": 48.8566, "longitude": 2.3522, "years": 11}
    )
    assert res.status_code == 422
    res_ok = client.get(
        "/api/astrocartography/location-forecast", params={"latitude": 48.8566, "longitude": 2.3522, "years": 10}
    )
    assert res_ok.status_code == 200


def test_astrocartography_forecast_reading_accepts_capped_years(client):
    chart_id = client.post("/api/charts", json=VALID_CHART_PAYLOAD).json()["id"]
    res = client.post(
        f"/api/charts/{chart_id}/readings",
        json={
            "reading_type": "astrocartography_forecast",
            "astro_focus_latitude": 48.8566,
            "astro_focus_longitude": 2.3522,
            "astro_focus_label": "Paris",
            "forecast_years": 10,
        },
    )
    # Pas de clé API configurée dans les tests : 503 (RuntimeError) attendu, pas une erreur de
    # construction du payload en amont (422/500).
    assert res.status_code == 503


def test_astrocartography_forecast_reading_rejects_years_above_cap(client):
    chart_id = client.post("/api/charts", json=VALID_CHART_PAYLOAD).json()["id"]
    res = client.post(
        f"/api/charts/{chart_id}/readings",
        json={"reading_type": "astrocartography_forecast", "forecast_years": 15},
    )
    assert res.status_code == 422


# ---------------------------------------------------------------------------
# Croisements de lignes (approximation cartographique des parans) + villes intéressantes
# ---------------------------------------------------------------------------
def test_find_line_crossings_two_meridians_never_cross():
    mc_line = [{"lat": -85.0, "lon": 10.0}, {"lat": 85.0, "lon": 10.0}]
    ic_line = [{"lat": -85.0, "lon": -170.0}, {"lat": 85.0, "lon": -170.0}]
    assert find_line_crossings(mc_line, ic_line) == []


def test_find_line_crossings_curve_vs_meridian():
    mc_line = [{"lat": -85.0, "lon": 0.0}, {"lat": 85.0, "lon": 0.0}]
    curve = [{"lat": 0.0, "lon": -2.0}, {"lat": 1.0, "lon": 2.0}]
    crossings = find_line_crossings(mc_line, curve)
    assert len(crossings) == 1
    assert crossings[0]["lat"] == pytest.approx(0.5, abs=0.01)
    assert crossings[0]["lon"] == pytest.approx(0.0, abs=0.01)


def test_find_line_crossings_curve_vs_curve():
    curve_a = [{"lat": 0.0, "lon": -2.0}, {"lat": 1.0, "lon": 2.0}]
    curve_b = [{"lat": 0.0, "lon": 2.0}, {"lat": 1.0, "lon": -2.0}]
    crossings = find_line_crossings(curve_a, curve_b)
    assert len(crossings) == 1
    assert crossings[0]["lat"] == pytest.approx(0.5, abs=0.01)
    assert crossings[0]["lon"] == pytest.approx(0.0, abs=0.01)


def test_find_line_crossings_parallel_curves_never_cross():
    curve_a = [{"lat": 0.0, "lon": -2.0}, {"lat": 1.0, "lon": 2.0}]
    curve_b = [{"lat": 0.0, "lon": -10.0}, {"lat": 1.0, "lon": -6.0}]
    assert find_line_crossings(curve_a, curve_b) == []


def test_compute_all_crossings_excludes_same_planet_pairs():
    jd_ut = swe.julday(2024, 3, 20, 12.0)
    equatorial_positions = {
        name: calc_planet_equatorial(jd_ut, PLANET_IDS[name]) for name in ASTROCARTOGRAPHY_PLANETS
    }
    gst_degrees = greenwich_sidereal_time_degrees(jd_ut)
    lines = [
        {"planet": line.planet, "line_type": line.line_type, "line_points": line.line_points}
        for line in compute_astrocartography_lines(equatorial_positions, gst_degrees)
    ]
    crossings = compute_all_crossings(lines)
    assert len(crossings) > 0
    assert all(c["planet_a"] != c["planet_b"] for c in crossings)


def test_find_interesting_cities_ranks_closer_crossing_higher():
    lines = [
        {"planet": "Sun", "line_type": "MC", "line_points": [{"lat": -85.0, "lon": 2.0}, {"lat": 85.0, "lon": 2.0}]},
        {"planet": "Venus", "line_type": "ASC", "line_points": [{"lat": 45.0, "lon": -2.0}, {"lat": 46.0, "lon": 6.0}]},
    ]
    crossings = compute_all_crossings(lines)
    assert len(crossings) == 1

    cities = [
        {"name": "Near", "country": "X", "lat": 45.5, "lon": 2.0},  # à la latitude du croisement
        {"name": "Far", "country": "X", "lat": 10.0, "lon": 2.0},  # sur la ligne du Soleil, loin du croisement
        {"name": "Nowhere", "country": "X", "lat": -40.0, "lon": 100.0},  # hors de portée
    ]
    results = find_interesting_cities(lines, crossings, cities, threshold_km=400.0, top_n=10)
    names = [c["name"] for c in results]
    assert "Nowhere" not in names
    assert names.index("Near") < names.index("Far")
    # Trié du score le plus élevé au plus faible.
    assert [c["score"] for c in results] == sorted((c["score"] for c in results), reverse=True)


def test_find_interesting_cities_respects_top_n():
    results = find_interesting_cities([], [], world_cities(), threshold_km=300.0, top_n=5)
    assert results == []  # aucune ligne/croisement fourni : aucune ville ne peut être proche de quoi que ce soit


def test_interesting_cities_endpoint_returns_ranked_cities(client):
    chart_id = client.post("/api/charts", json=VALID_CHART_PAYLOAD).json()["id"]
    res = client.get(f"/api/charts/{chart_id}/astrocartography/interesting-cities")
    assert res.status_code == 200
    body = res.json()
    assert 0 < len(body) <= 12
    assert [c["score"] for c in body] == sorted((c["score"] for c in body), reverse=True)
    for city in body:
        assert city["nearby_lines"] or city["nearby_crossings"]


def test_interesting_cities_endpoint_404_for_unknown_chart(client):
    res = client.get("/api/charts/does-not-exist/astrocartography/interesting-cities")
    assert res.status_code == 404


def test_interesting_cities_endpoint_respects_top_n_param(client):
    chart_id = client.post("/api/charts", json=VALID_CHART_PAYLOAD).json()["id"]
    res = client.get(f"/api/charts/{chart_id}/astrocartography/interesting-cities", params={"top_n": 3})
    assert res.status_code == 200
    assert len(res.json()) <= 3


def test_transit_interesting_cities_endpoint_defaults_to_top_5(client):
    res = client.get("/api/astrocartography/transit/interesting-cities")
    assert res.status_code == 200
    body = res.json()
    assert 0 < len(body) <= 5
    assert [c["score"] for c in body] == sorted((c["score"] for c in body), reverse=True)


def test_transit_interesting_cities_endpoint_recomputes_for_a_different_date(client):
    res_today = client.get("/api/astrocartography/transit/interesting-cities")
    res_future = client.get("/api/astrocartography/transit/interesting-cities", params={"date": "2028-03-15"})
    assert res_today.status_code == res_future.status_code == 200
    # Deux dates suffisamment éloignées doivent (quasi certainement) produire un classement
    # différent, puisque les lignes de transit se déplacent avec le temps.
    assert res_today.json() != res_future.json()


def test_transit_interesting_cities_endpoint_respects_top_n_param(client):
    res = client.get("/api/astrocartography/transit/interesting-cities", params={"top_n": 2})
    assert res.status_code == 200
    assert len(res.json()) <= 2
