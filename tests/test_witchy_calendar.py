from collections import Counter

import pytest
import swisseph as swe
from fastapi.testclient import TestClient

from app.core.witchy_calendar import (
    STATION_PLANETS,
    SUPER_MOON_DISTANCE_KM_THRESHOLD,
    _score_from_raw,
    compute_eclipse_events,
    compute_ingress_events,
    compute_lunation_events,
    compute_station_events,
    compute_witchy_calendar,
)
from app.database import SessionLocal
from app.main import app
from app.models import GlobalWitchyCalendarCache
from app.services import interpretation_service
from app.services.witchy_calendar_service import get_or_compute_witchy_calendar


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


# ---------------------------------------------------------------------------
# Moteur de calcul
# ---------------------------------------------------------------------------
def test_score_from_raw_matches_conversion_table():
    assert _score_from_raw(0) == 2
    assert _score_from_raw(4) == 2
    assert _score_from_raw(5) == 3
    assert _score_from_raw(7) == 3
    assert _score_from_raw(8) == 4
    assert _score_from_raw(9) == 4
    assert _score_from_raw(10) == 5
    assert _score_from_raw(15) == 5


def test_lunation_events_alternate_new_and_full_moon():
    start_jd = swe.julday(2027, 1, 1, 0)
    end_jd = swe.julday(2028, 1, 1, 0)
    events = compute_lunation_events(start_jd, end_jd)
    new_moons = sorted(e["event_date"] for e in events if e["event_type"] == "nouvelle_lune")
    full_moons = sorted(e["event_date"] for e in events if e["event_type"] == "pleine_lune")
    # Environ 12-13 de chaque sur une année (mois synodique ~29.53 jours).
    assert 12 <= len(new_moons) <= 13
    assert 12 <= len(full_moons) <= 13
    # Aucune date ne doit apparaître dans les deux listes (bug historique : voir le fix du
    # rebouclage de la fonction de recherche de racine, qui confondait la discontinuité de
    # l'offset centré avec un vrai passage par zéro).
    assert set(new_moons).isdisjoint(set(full_moons))


def test_lunation_events_detects_super_moon_below_threshold():
    start_jd = swe.julday(2027, 1, 1, 0)
    end_jd = swe.julday(2028, 1, 1, 0)
    events = compute_lunation_events(start_jd, end_jd)
    for event in events:
        assert event["super_moon"] == (event["moon_distance_km"] <= SUPER_MOON_DISTANCE_KM_THRESHOLD)
    assert any(e["super_moon"] for e in events)  # au moins une super lune dans l'année testée


def test_eclipse_events_align_exactly_with_a_lunation_date():
    """Une éclipse ne peut astronomiquement se produire qu'à une syzygie exacte (Nouvelle Lune
    pour une éclipse solaire, Pleine Lune pour une éclipse lunaire) — vérifie que le calcul de
    date d'éclipse et le calcul de lunaison, pourtant indépendants, tombent bien sur le même
    jour."""
    start_jd = swe.julday(2027, 1, 1, 0)
    end_jd = swe.julday(2028, 1, 1, 0)
    eclipses = compute_eclipse_events(start_jd, end_jd)
    lunations = compute_lunation_events(start_jd, end_jd)
    lunation_dates = {e["event_date"] for e in lunations}
    assert len(eclipses) > 0
    for eclipse in eclipses:
        assert eclipse["event_date"] in lunation_dates


def test_known_2027_solar_eclipse_is_detected():
    """Éclipse solaire annulaire connue du 6 février 2027 (référence externe, indépendante de
    ce code) — vérifie que le calcul par swe.sol_eclipse_when_glob est bien branché et exploité
    correctement (mois/jour), pas seulement qu'il ne lève pas d'exception."""
    start_jd = swe.julday(2027, 1, 1, 0)
    end_jd = swe.julday(2028, 1, 1, 0)
    eclipses = compute_eclipse_events(start_jd, end_jd)
    solar = [e for e in eclipses if e["event_type"] == "eclipse_solaire"]
    assert any(e["event_date"] == "2027-02-06" for e in solar)


def test_station_events_cover_all_station_planets_over_two_years():
    start_jd = swe.julday(2026, 1, 1, 0)
    end_jd = swe.julday(2028, 1, 1, 0)
    events = compute_station_events(start_jd, end_jd)
    planets_seen = {e["planet"] for e in events}
    # Sur 2 ans, toutes les planètes de la liste doivent avoir au moins une station (même
    # Vénus/Mars, les plus rares avec des périodes synodiques de ~1,6 et ~2 ans).
    assert planets_seen == set(STATION_PLANETS)
    for event in events:
        assert event["event_type"] in ("station_retrograde", "station_directe")
        assert event["direction"] in ("retrograde", "direct")


def test_ingress_events_have_distinct_from_and_to_signs():
    start_jd = swe.julday(2020, 1, 1, 0)
    end_jd = swe.julday(2030, 1, 1, 0)  # large fenêtre pour capter des ingrès même de Pluton
    events = compute_ingress_events(start_jd, end_jd)
    assert len(events) > 0
    for event in events:
        assert event["from_sign"] != event["sign"]
        assert event["event_type"] == "ingres"


def test_compute_witchy_calendar_is_sorted_and_json_shape_consistent():
    events = compute_witchy_calendar(2027)
    assert len(events) > 30  # ordre de grandeur attendu (~45-55/an)
    dates = [e["event_date"] for e in events]
    assert dates == sorted(dates)
    for event in events:
        assert 1 <= event["score"] <= 5
        assert isinstance(event["score_brut"], (int, float))


def test_compute_witchy_calendar_is_deterministic():
    assert compute_witchy_calendar(2027) == compute_witchy_calendar(2027)


# ---------------------------------------------------------------------------
# Service (cache)
# ---------------------------------------------------------------------------
def test_get_or_compute_witchy_calendar_caches_across_calls(client):
    db = SessionLocal()
    try:
        first = get_or_compute_witchy_calendar(db, 2031)
        count_after_first = db.query(GlobalWitchyCalendarCache).filter_by(year=2031).count()
        second = get_or_compute_witchy_calendar(db, 2031)
        count_after_second = db.query(GlobalWitchyCalendarCache).filter_by(year=2031).count()
        assert first == second
        assert count_after_first == count_after_second == 1
    finally:
        db.close()


def test_get_or_compute_witchy_calendar_handles_concurrent_cache_miss(client):
    """Même correction que pour les lignes d'astrocartography_service : deux requêtes
    concurrentes sur une année pas encore en cache ne doivent pas se solder par une 500
    (IntegrityError sur la contrainte UNIQUE year)."""
    db = SessionLocal()
    other_db = SessionLocal()
    try:
        original_commit = db.commit

        def commit_after_concurrent_winner():
            get_or_compute_witchy_calendar(other_db, 2032)
            return original_commit()

        db.commit = commit_after_concurrent_winner
        result = get_or_compute_witchy_calendar(db, 2032)
        assert len(result) > 0
    finally:
        db.close()
        other_db.close()


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------
def test_witchy_calendar_endpoint_defaults_to_current_year(client):
    import datetime

    res = client.get("/api/witchy-calendar")
    assert res.status_code == 200
    body = res.json()
    assert body["year"] == datetime.date.today().year
    assert len(body["events"]) > 0


def test_witchy_calendar_endpoint_accepts_explicit_year(client):
    res = client.get("/api/witchy-calendar", params={"year": 2027})
    assert res.status_code == 200
    body = res.json()
    assert body["year"] == 2027
    event_types = {e["event_type"] for e in body["events"]}
    assert "nouvelle_lune" in event_types
    assert "eclipse_solaire" in event_types


def test_witchy_calendar_endpoint_rejects_year_out_of_range(client):
    res = client.get("/api/witchy-calendar", params={"year": 1800})
    assert res.status_code == 422


def test_witchy_calendar_endpoint_is_cached_between_requests(client):
    res1 = client.get("/api/witchy-calendar", params={"year": 2033})
    res2 = client.get("/api/witchy-calendar", params={"year": 2033})
    assert res1.json() == res2.json()


# ---------------------------------------------------------------------------
# Lecture LLM
# ---------------------------------------------------------------------------
def test_witchy_calendar_reading_payload_defaults_focus_to_current_year(client):
    chart_id = client.post(
        "/api/charts",
        json={
            "birth_data": {
                "date": "1990-05-15",
                "time": "14:32:00",
                "time_known": True,
                "timezone": "Europe/Paris",
                "location": {"city": "Lyon", "country": "France", "latitude": 45.764, "longitude": 4.8357},
            }
        },
    ).json()["id"]
    res = client.post(f"/api/charts/{chart_id}/readings", json={"reading_type": "witchy_calendar"})
    # Pas de clé API configurée dans les tests : 503 (RuntimeError) attendu, pas une erreur de
    # construction du payload en amont (422/500).
    assert res.status_code == 503


def test_witchy_calendar_prompt_is_distinct_and_explains_scannable_format():
    from app import schemas

    prompt = interpretation_service._build_system_prompt(schemas.ReadingRequest(reading_type="witchy_calendar"))
    other_prompt = interpretation_service._build_system_prompt(schemas.ReadingRequest(reading_type="astrocartography"))
    assert prompt != other_prompt
    assert "CALENDRIER" in prompt
    assert "events" in prompt
