from collections import Counter

import pytest
import swisseph as swe
from fastapi.testclient import TestClient

from app.core.day_chart import compute_day_chart
from app.core.witchy_calendar import (
    SLOW_PLANET_PAIRS,
    STATION_PLANETS,
    SUPER_MOON_DISTANCE_KM_THRESHOLD,
    _score_from_raw,
    compute_contextual_signals,
    compute_eclipse_events,
    compute_eclipse_local_visibility,
    compute_grand_conjunction_events,
    compute_hemisphere,
    compute_ingress_events,
    compute_location_context,
    compute_lunation_events,
    compute_station_events,
    compute_witchy_calendar,
    enrich_events_with_contextual_signals,
)
from app.core.witchy_calendar_personalization import (
    DURATION_EVENT_TYPES,
    PUNCTUAL_EVENT_TYPES,
    _mechanism_1_aspect_natal,
    _mechanism_2_maison_natale,
    personalize_day_chart,
    personalize_witchy_events,
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
    assert _score_from_raw(0) == 1
    assert _score_from_raw(4) == 1
    assert _score_from_raw(5) == 2
    assert _score_from_raw(6) == 2
    assert _score_from_raw(7) == 3
    assert _score_from_raw(8) == 3
    assert _score_from_raw(9) == 4
    assert _score_from_raw(10) == 5
    assert _score_from_raw(15) == 5


def test_score_from_raw_floor_is_reachable_by_the_most_common_event():
    """Une station de Mercure (poids_base 4, l'événement le plus fréquent du catalogue, sans
    modificateur) doit atteindre le vrai plancher 1/5 — pas être artificiellement remontée à 2
    (voir app/reference_data/witchy_calendar_events.json, note_qualitative)."""
    mercury_station_score_brut = 4
    assert _score_from_raw(mercury_station_score_brut) == 1


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


def test_witchy_calendar_prompt_explains_personalization_blocks():
    from app import schemas

    prompt = interpretation_service._build_system_prompt(schemas.ReadingRequest(reading_type="witchy_calendar"))
    assert "impact_personnel" in prompt
    assert "theme_confirme_amplifie" in prompt


# ---------------------------------------------------------------------------
# V2 : grandes conjonctions
# ---------------------------------------------------------------------------
def test_known_2020_jupiter_saturn_great_conjunction_is_detected():
    """Grande conjonction Jupiter-Saturne du 21 décembre 2020 (référence externe connue, la
    plus médiatisée de ce type) — vérifie que la détection dynamique par paire de planètes
    lentes fonctionne correctement, pas seulement qu'elle ne lève pas d'exception."""
    start_jd = swe.julday(2020, 1, 1, 0)
    end_jd = swe.julday(2021, 1, 1, 0)
    events = compute_grand_conjunction_events(start_jd, end_jd)
    jupiter_saturn_conjunctions = [
        e
        for e in events
        if {e["planet"], e["planet_b"]} == {"Jupiter", "Saturn"} and e["aspect_type"] == "conjunction"
    ]
    assert any(e["event_date"] == "2020-12-21" for e in jupiter_saturn_conjunctions)


def test_grand_conjunction_events_cover_distinct_slow_planet_pairs():
    start_jd = swe.julday(2020, 1, 1, 0)
    end_jd = swe.julday(2021, 1, 1, 0)
    events = compute_grand_conjunction_events(start_jd, end_jd)
    assert len(events) > 0
    for event in events:
        assert (event["planet"], event["planet_b"]) in SLOW_PLANET_PAIRS
        assert event["aspect_type"] in ("conjunction", "square", "opposition")
        assert event["planet"] != event["planet_b"]


def test_grand_conjunction_events_use_catalog_weight():
    start_jd = swe.julday(2020, 1, 1, 0)
    end_jd = swe.julday(2021, 1, 1, 0)
    events = compute_grand_conjunction_events(start_jd, end_jd)
    for event in events:
        assert event["score_brut"] == 9  # poids_base du catalogue, voir witchy_calendar_events.json
        assert event["score"] == _score_from_raw(9)


def test_compute_witchy_calendar_includes_grand_conjunctions_for_2020():
    events = compute_witchy_calendar(2020)
    assert any(e["event_type"] == "grande_conjonction" for e in events)


# ---------------------------------------------------------------------------
# V2 : personnalisation par croisement avec le thème natal
# ---------------------------------------------------------------------------
def _synthetic_chart_data():
    from app.core.zodiac import SIGNS

    return {
        "planets": [
            {"name": "Sun", "absolute_longitude": 4.0, "sign": "Aries", "house": 1},
            {"name": "Moon", "absolute_longitude": 200.0, "sign": "Libra", "house": 7},
            {"name": "Mercury", "absolute_longitude": 10.0, "sign": "Aries", "house": 1},
            {"name": "Venus", "absolute_longitude": 40.0, "sign": "Taurus", "house": 2},
            {"name": "Mars", "absolute_longitude": 70.0, "sign": "Gemini", "house": 3},
            {"name": "Jupiter", "absolute_longitude": 100.0, "sign": "Cancer", "house": 4},
            {"name": "Saturn", "absolute_longitude": 5.1, "sign": "Aries", "house": 1},
            {"name": "Uranus", "absolute_longitude": 160.0, "sign": "Virgo", "house": 6},
            {"name": "Neptune", "absolute_longitude": 190.0, "sign": "Libra", "house": 7},
            {"name": "Pluto", "absolute_longitude": 220.0, "sign": "Scorpio", "house": 8},
        ],
        "angles": {
            "ascendant": {"absolute_longitude": 0.0, "sign": "Aries"},
            "midheaven": {"absolute_longitude": 270.0, "sign": "Capricorn"},
        },
        "houses": [{"number": i + 1, "sign": SIGNS[i], "absolute_longitude": i * 30.0} for i in range(12)],
        "dispositors_traditional": {"convergence": {"dominant_dispositor": "Saturn", "level": "forte"}},
        "dispositors_modern": {"convergence": {"dominant_dispositor": None, "level": "aucune"}},
    }


def test_mechanism_1_prioritizes_luminary_over_tighter_slow_planet_aspect():
    chart_data = _synthetic_chart_data()
    # Événement à 5.2° : Soleil (4.0°, écart 1.2°) ET Saturne (5.1°, écart 0.1°, bien plus
    # serré) sont tous deux en orbe de conjonction (2°) — le Soleil doit néanmoins l'emporter
    # (luminaire prioritaire, voir priorite_cibles du document source).
    match = _mechanism_1_aspect_natal(5.2, chart_data)
    assert match is not None
    assert match["target"] == "Sun"
    assert match["aspect_type"] == "conjunction"


def test_mechanism_1_returns_none_when_nothing_in_orb():
    chart_data = _synthetic_chart_data()
    assert _mechanism_1_aspect_natal(135.0, chart_data) is None  # loin de tous les points testés


def test_mechanism_2_returns_house_and_its_ruler():
    chart_data = _synthetic_chart_data()
    house_number, ruler = _mechanism_2_maison_natale(15.0, chart_data)  # tombe en maison 1 (0-30°, Bélier)
    assert house_number == 1
    assert ruler == "Mars"  # maître traditionnel du Bélier


def test_personalize_witchy_events_flags_theme_confirme_amplification():
    chart_data = _synthetic_chart_data()  # Saturne = dispositeur final dominant (convergence forte)
    events = [
        {
            "event_date": "2027-01-01",
            "event_type": "nouvelle_lune",
            "planet": "Moon",
            "sign": "Aries",
            "score_brut": 5,
            "score": 3,
            "event_longitude": 5.15,  # très serré sur Saturne (5.1°), loin du Soleil/Lune/ASC
        }
    ]
    # Neutralise les autres cibles proches pour isoler Saturne comme seule correspondance.
    chart_data["planets"][0]["absolute_longitude"] = 60.0  # Sun loin
    chart_data["angles"]["ascendant"]["absolute_longitude"] = 200.0  # ASC loin

    result = personalize_witchy_events(events, chart_data)
    impact = result[0]["impact_personnel"]
    assert impact["detecte"] is True
    assert impact["mecanisme"] == "aspect_natal"
    assert impact["cible_touchee"] == "Saturn"
    assert impact["theme_confirme_amplifie"] is True  # Saturne est dispositeur dominant (forte)


def test_personalize_witchy_events_no_detection_returns_empty_block():
    chart_data = _synthetic_chart_data()
    events = [
        {
            "event_date": "2027-01-01",
            "event_type": "nouvelle_lune",
            "planet": "Moon",
            "sign": "Libra",
            "score_brut": 5,
            "score": 3,
            "event_longitude": 135.0,  # loin de tout point natal testé
        }
    ]
    impact = personalize_witchy_events(events, chart_data)[0]["impact_personnel"]
    assert impact == {
        "detecte": False,
        "mecanisme": None,
        "cible_touchee": None,
        "orbe_ou_maison": None,
        "theme_confirme_amplifie": False,
    }


def test_personalize_witchy_events_uses_mechanism_2_for_duration_events_only():
    chart_data = _synthetic_chart_data()
    events = [
        {
            "event_date": "2027-01-01",
            "event_type": "ingres",
            "planet": "Jupiter",
            "sign": "Aries",
            "score_brut": 8,
            "score": 4,
            "event_longitude": 15.0,
        },
        {
            "event_date": "2027-01-02",
            "event_type": "station_retrograde",
            "planet": "Mercury",
            "sign": "Aries",
            "score_brut": 4,
            "score": 2,
            "event_longitude": 4.2,  # serré sur le Soleil natal (4.0°) -> mécanisme 1 attendu
        },
    ]
    result = personalize_witchy_events(events, chart_data)
    assert result[0]["impact_personnel"]["mecanisme"] == "maison_natale"
    assert result[1]["impact_personnel"]["mecanisme"] == "aspect_natal"


def test_punctual_and_duration_event_type_sets_partition_known_event_types():
    known_types = {
        "nouvelle_lune", "pleine_lune", "eclipse_solaire", "eclipse_lunaire",
        "station_retrograde", "station_directe", "ingres", "grande_conjonction",
    }
    assert PUNCTUAL_EVENT_TYPES | DURATION_EVENT_TYPES == known_types
    assert PUNCTUAL_EVENT_TYPES.isdisjoint(DURATION_EVENT_TYPES)


def test_personalize_witchy_events_output_is_json_serializable():
    import json

    chart_data = _synthetic_chart_data()
    events = compute_witchy_calendar(2027)
    personalized = personalize_witchy_events(events, chart_data)
    json.dumps(personalized)
    assert len(personalized) == len(events)


# ---------------------------------------------------------------------------
# V3 : carte du jour (mode_detail_journee)
# ---------------------------------------------------------------------------
def test_compute_day_chart_has_no_houses_or_ascendant():
    """Une carte du jour n'a ni Ascendant ni maisons (aucun lieu associé à une date seule) —
    voir modes_de_lecture.mode_detail_journee.reutilisation_moteur du document source."""
    day_chart = compute_day_chart("2027-01-22")
    assert "houses" not in day_chart
    assert "angles" not in day_chart
    assert set(p["name"] for p in day_chart["planets"]) == {
        "Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto",
    }


def test_compute_day_chart_computes_all_planet_aspects():
    day_chart = compute_day_chart("2027-01-22")
    assert len(day_chart["aspects"]) > 0
    for aspect in day_chart["aspects"]:
        assert {"planet1", "planet2", "type", "orb"} <= aspect.keys()


def test_compute_day_chart_is_deterministic():
    assert compute_day_chart("2027-01-22") == compute_day_chart("2027-01-22")


def test_compute_day_chart_themes_confirmes_only_keeps_planets_with_a_reason():
    day_chart = compute_day_chart("2027-01-22")
    for planet, data in day_chart["themes_confirmes_du_jour"].items():
        assert data["present"] is True
        assert len(data["reasons"]) > 0


def test_personalize_day_chart_detects_tight_aspect_to_natal_point():
    from app.core.zodiac import SIGNS

    day_chart = compute_day_chart("2027-01-22")
    # Le Soleil du jour (voir fixture) doit tomber quelque part sur le zodiaque ; on construit un
    # point natal en conjonction serrée avec lui pour vérifier la détection (mécanisme 1 réutilisé
    # tel quel, ici appliqué à chaque planète de la carte du jour plutôt qu'à un seul événement).
    sun_lon = next(p["absolute_longitude"] for p in day_chart["planets"] if p["name"] == "Sun")
    chart_data = {
        "planets": [{"name": "Moon", "absolute_longitude": sun_lon, "sign": "Libra", "house": 7}],  # Lune natale collée au Soleil du jour
        "angles": {
            "ascendant": {"absolute_longitude": (sun_lon + 100) % 360, "sign": SIGNS[0]},
            "midheaven": {"absolute_longitude": (sun_lon + 190) % 360, "sign": SIGNS[9]},
        },
        "dispositors_traditional": {"convergence": {"dominant_dispositor": None, "level": "aucune"}},
        "dispositors_modern": {"convergence": {"dominant_dispositor": None, "level": "aucune"}},
    }
    resonances = personalize_day_chart(day_chart, chart_data)
    assert any(r["planete_du_jour"] == "Sun" and r["cible_natale_touchee"] == "Moon" for r in resonances)


def test_personalize_day_chart_output_is_json_serializable():
    import json

    day_chart = compute_day_chart("2027-01-22")
    chart_data = _synthetic_chart_data()
    resonances = personalize_day_chart(day_chart, chart_data)
    json.dumps(resonances)


# ---------------------------------------------------------------------------
# V3 : location_context (visibilité locale des éclipses)
# ---------------------------------------------------------------------------
def test_compute_hemisphere():
    assert compute_hemisphere(45.0) == "nord"
    assert compute_hemisphere(-33.87) == "sud"
    assert compute_hemisphere(0.0) == "nord"


def test_compute_eclipse_local_visibility_matches_known_2024_total_solar_eclipse():
    """Éclipse solaire totale du 8 avril 2024 (référence externe connue) : visible depuis le
    Texas (dans la bande de totalité), pas visible depuis Paris (nuit/hémisphère opposé)."""
    import swisseph as swe

    start_jd = swe.julday(2024, 1, 1, 0)
    end_jd = swe.julday(2025, 1, 1, 0)
    eclipses = compute_eclipse_events(start_jd, end_jd)
    eclipse = next(e for e in eclipses if e["event_date"] == "2024-04-08")

    assert compute_eclipse_local_visibility(eclipse, 29.42, -98.49) is True  # San Antonio, TX
    assert compute_eclipse_local_visibility(eclipse, 48.8566, 2.3522) is False  # Paris


def test_compute_eclipse_local_visibility_returns_none_for_non_eclipse_event():
    event = {"event_type": "nouvelle_lune", "event_date": "2027-01-07"}
    assert compute_eclipse_local_visibility(event, 45.0, 5.0) is None


def test_compute_location_context_only_applies_to_eclipses():
    eclipse_event = {"event_type": "eclipse_solaire", "event_date": "2027-02-06"}
    other_event = {"event_type": "nouvelle_lune", "event_date": "2027-01-07"}
    assert compute_location_context(eclipse_event, 45.0, 5.0) is not None
    assert compute_location_context(other_event, 45.0, 5.0) is None


# ---------------------------------------------------------------------------
# V3 : enrichissement contextuel mode aperçu
# ---------------------------------------------------------------------------
def test_compute_contextual_signals_excludes_aspect_between_main_actors():
    event = {"event_type": "eclipse_solaire", "planet": "Sun"}
    day_aspects = [
        {"planet1": "Sun", "planet2": "Moon", "type": "conjunction", "orb": 0.1},  # l'éclipse elle-même, exclue
        {"planet1": "Mars", "planet2": "Uranus", "type": "square", "orb": 0.5},  # n'implique aucun acteur, exclue
        {"planet1": "Sun", "planet2": "Mars", "type": "square", "orb": 0.3},  # signal valable (implique le Soleil)
    ]
    signals = compute_contextual_signals(event, day_aspects)
    assert len(signals) == 1
    assert {signals[0]["planet1"], signals[0]["planet2"]} == {"Sun", "Mars"}


def test_compute_contextual_signals_filters_by_orb_and_major_type_and_caps_at_two():
    event = {"event_type": "station_retrograde", "planet": "Mercury"}
    day_aspects = [
        {"planet1": "Mercury", "planet2": "Venus", "type": "sextile", "orb": 1.9},  # dans l'orbe
        {"planet1": "Mercury", "planet2": "Mars", "type": "square", "orb": 2.5},  # hors orbe (>= 2°)
        {"planet1": "Mercury", "planet2": "Jupiter", "type": "quincunx", "orb": 0.5},  # aspect mineur, exclu
        {"planet1": "Mercury", "planet2": "Saturn", "type": "trine", "orb": 0.2},
        {"planet1": "Mercury", "planet2": "Uranus", "type": "conjunction", "orb": 0.1},
        {"planet1": "Venus", "planet2": "Mars", "type": "sextile", "orb": 0.1},  # n'implique pas Mercure
    ]
    signals = compute_contextual_signals(event, day_aspects)
    assert len(signals) == 2  # plafonné, jamais une liste exhaustive
    assert [s["orb"] for s in signals] == sorted(s["orb"] for s in signals)  # les plus serrés d'abord
    assert all("Mercury" in (s["planet1"], s["planet2"]) for s in signals)


def test_compute_contextual_signals_returns_empty_for_unknown_event_type():
    assert compute_contextual_signals({"event_type": "inconnu"}, [{"planet1": "A", "planet2": "B", "type": "trine", "orb": 0.1}]) == []


def test_enrich_events_with_contextual_signals_adds_field_to_every_event():
    events = compute_witchy_calendar(2027)[:10]
    enriched = enrich_events_with_contextual_signals(events)
    assert len(enriched) == len(events)
    for event in enriched:
        assert "contextual_signals" in event
        assert len(event["contextual_signals"]) <= 2


def test_enrich_events_with_contextual_signals_output_is_json_serializable():
    import json

    events = compute_witchy_calendar(2027)[:10]
    json.dumps(enrich_events_with_contextual_signals(events))


# ---------------------------------------------------------------------------
# V3 : lecture LLM mode détail journée
# ---------------------------------------------------------------------------
def test_witchy_day_detail_prompt_is_distinct_and_mentions_day_chart():
    from app import schemas

    prompt = interpretation_service._build_system_prompt(
        schemas.ReadingRequest(reading_type="witchy_day_detail")
    )
    other_prompt = interpretation_service._build_system_prompt(schemas.ReadingRequest(reading_type="witchy_calendar"))
    assert prompt != other_prompt
    assert "day_chart" in prompt
    assert "themes_confirmes_du_jour" in prompt
    assert "maisons" in prompt  # précise l'absence de maisons/Ascendant pour une carte du jour


def test_witchy_day_detail_reading_payload_returns_503_without_api_key(client):
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
    res = client.post(
        f"/api/charts/{chart_id}/readings",
        json={"reading_type": "witchy_day_detail", "witchy_day_detail_date": "2027-01-22"},
    )
    assert res.status_code == 503
