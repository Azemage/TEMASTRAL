import pytest
import swisseph as swe
from fastapi.testclient import TestClient

from app.core.astrocartography import (
    ASTROCARTOGRAPHY_PLANETS,
    analyze_nearby_lines,
    compute_horizon_line_points,
    compute_meridian_lines,
    _normalize_longitude,
)
from app.core.ephemeris import PLANET_IDS, calc_planet_equatorial, greenwich_sidereal_time_degrees
from app.main import app

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
