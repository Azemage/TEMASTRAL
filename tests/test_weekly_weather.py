from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.core.root_finding import bisect_root, scan_zero_crossings
from app.core.weekly_weather import (
    FAST_PLANETS,
    GENERATIONAL_PLANETS,
    _house_score,
    compute_generic_weekly_by_sign,
    compute_weekly_collective,
)
from app.core.weekly_weather_domains import compute_weekly_domain_scores
from app.database import SessionLocal
from app.main import app
from app.models import GlobalWeeklyWeatherCache
from app.services import interpretation_service
from app.services.weekly_weather_service import compute_domain_scores_for_chart, get_or_compute_weekly_weather


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


# ---------------------------------------------------------------------------
# Recherche de racines (extraite de witchy_calendar.py, réutilisée ici)
# ---------------------------------------------------------------------------
def test_bisect_root_finds_zero_crossing():
    assert bisect_root(lambda x: x - 5, 0, 10) == pytest.approx(5, abs=1e-6)


def test_scan_zero_crossings_finds_all_roots_in_range():
    # Racines à 2.3 et 6.3 (volontairement pas sur un pas entier, comme en pratique pour une
    # fonction astronomique réelle) sur [0, 8], échantillonné au pas de 1.
    def f(x):
        return (x - 2.3) if x < 4.3 else (6.3 - x)

    roots = scan_zero_crossings(f, 0, 8, step=1)
    assert len(roots) == 2
    assert roots[0] == pytest.approx(2.3, abs=1e-6)
    assert roots[1] == pytest.approx(6.3, abs=1e-6)


# ---------------------------------------------------------------------------
# Moteur de calcul (couche collective)
# ---------------------------------------------------------------------------
def test_compute_weekly_collective_covers_seven_days():
    data = compute_weekly_collective(date(2027, 2, 3))
    assert data["period_start"] == "2027-02-03"
    assert data["period_end"] == "2027-02-09"
    assert len(data["moon_path"]) == 7
    assert data["moon_path"][0]["date"] == "2027-02-03"
    assert data["moon_path"][-1]["date"] == "2027-02-09"


def test_compute_weekly_collective_is_deterministic():
    a = compute_weekly_collective(date(2027, 2, 3))
    b = compute_weekly_collective(date(2027, 2, 3))
    assert a == b


def test_compute_weekly_collective_output_is_json_serializable():
    import json

    json.dumps(compute_weekly_collective(date(2027, 2, 3)))


def test_compute_weekly_collective_detects_known_moon_and_venus_ingresses():
    """Semaine de référence externe (calcul Swiss Ephemeris) : la Lune entre en Verseau le 5
    février 2027 puis en Poissons le 8, et Vénus entre en Capricorne le 4 — vérifie que la
    détection jour par jour fonctionne, pas seulement qu'elle ne lève pas d'exception."""
    data = compute_weekly_collective(date(2027, 2, 3))
    moon_ingress_dates = {(i["date"], i["from_sign"], i["to_sign"]) for i in data["moon_ingresses"]}
    assert ("2027-02-05", "Capricorn", "Aquarius") in moon_ingress_dates
    assert ("2027-02-08", "Aquarius", "Pisces") in moon_ingress_dates

    venus = next(p for p in data["fast_planets"] if p["name"] == "Venus")
    assert venus["ingress"] == {"date": "2027-02-04", "from_sign": "Sagittarius", "to_sign": "Capricorn"}


def test_compute_weekly_collective_reuses_witchy_calendar_events_in_range():
    """La Nouvelle Lune / éclipse solaire du 6 février 2027 (déjà couverte par
    test_known_2027_solar_eclipse_is_detected dans test_witchy_calendar.py) doit apparaître
    telle quelle dans la semaine, sans recalcul indépendant."""
    data = compute_weekly_collective(date(2027, 2, 3))
    event_types = {e["event_type"] for e in data["witchy_events"]}
    assert "eclipse_solaire" in event_types
    assert "nouvelle_lune" in event_types
    for event in data["witchy_events"]:
        assert "2027-02-03" <= event["event_date"] <= "2027-02-09"


def test_compute_weekly_collective_reuses_station_events_filtered_to_fast_planets():
    data = compute_weekly_collective(date(2027, 2, 3))
    assert all(s["planet"] in ("Mercury", "Venus", "Mars") for s in data["stations"])
    mercury_station = next(s for s in data["stations"] if s["planet"] == "Mercury")
    assert mercury_station["event_date"] == "2027-02-09"
    assert mercury_station["direction"] == "retrograde"
    assert mercury_station["score"] >= 1  # score du catalogue witchy réutilisé tel quel


def test_compute_weekly_collective_transit_transit_aspects_are_exact_and_scored():
    data = compute_weekly_collective(date(2027, 2, 3))
    assert len(data["transit_transit_aspects"]) > 0
    for aspect in data["transit_transit_aspects"]:
        assert aspect["planet_a"] in ("Moon", "Mercury", "Venus", "Mars")
        assert aspect["planet_b"] in ("Moon", "Mercury", "Venus", "Mars")
        assert aspect["aspect_type"] in ("conjunction", "sextile", "square", "trine", "opposition")
        assert "2027-02-03" <= aspect["date"] <= "2027-02-09"
        assert aspect["score"] >= 1


def test_compute_weekly_collective_generational_aspects_are_exact_and_scored():
    """Technique 'Aspects planète rapide vers planète lente/générationnelle' (voir
    echelles_temporelles_lecture.json, mode_semaine) : Mercure/Vénus/Mars en aspect majeur EXACT
    cette semaine avec Jupiter à Pluton. Un cran au-dessus du même aspect entre deux planètes
    rapides (voir _ASPECT_TYPE_SCORE_GENERATIONAL)."""
    data = compute_weekly_collective(date(2027, 2, 3))
    assert len(data["generational_aspects"]) > 0
    for aspect in data["generational_aspects"]:
        assert aspect["planet_a"] in FAST_PLANETS
        assert aspect["planet_b"] in GENERATIONAL_PLANETS
        assert aspect["aspect_type"] in ("conjunction", "sextile", "square", "trine", "opposition")
        assert "2027-02-03" <= aspect["date"] <= "2027-02-09"
        assert aspect["score"] >= 3  # noté un cran au-dessus des aspects rapide-rapide (score >= 2)


def test_compute_weekly_collective_generational_aspects_excluded_from_transit_transit_aspects():
    """Les deux listes restent distinctes : la Lune n'apparaît jamais dans generational_aspects,
    et aucune planète générationnelle n'apparaît dans transit_transit_aspects."""
    data = compute_weekly_collective(date(2027, 2, 3))
    for aspect in data["generational_aspects"]:
        assert aspect["planet_a"] != "Moon"
    for aspect in data["transit_transit_aspects"]:
        assert aspect["planet_a"] not in GENERATIONAL_PLANETS
        assert aspect["planet_b"] not in GENERATIONAL_PLANETS


def test_compute_weekly_collective_highlights_include_generational_aspect_kind():
    data = compute_weekly_collective(date(2027, 2, 3))
    generational_highlights = [h for h in data["highlights"] if h["kind"] == "aspect_generational"]
    assert len(generational_highlights) == len(data["generational_aspects"])


def test_compute_weekly_collective_highlights_sorted_by_score_descending():
    data = compute_weekly_collective(date(2027, 2, 3))
    scores = [h["score"] for h in data["highlights"]]
    assert scores == sorted(scores, reverse=True)


def test_compute_weekly_collective_main_event_is_highest_scored_highlight_with_a_sign():
    data = compute_weekly_collective(date(2027, 2, 3))
    best_with_sign = next(h for h in data["highlights"] if h.get("sign"))
    assert data["main_event"]["sign"] == best_with_sign["sign"]
    assert data["main_event"]["kind"] == best_with_sign["kind"]


def test_compute_weekly_collective_handles_year_boundary_week():
    """Une semaine à cheval sur deux années civiles ne doit pas planter (compute_witchy_calendar
    est appelé pour les deux années concernées)."""
    data = compute_weekly_collective(date(2027, 12, 29))
    assert data["period_start"] == "2027-12-29"
    assert data["period_end"] == "2028-01-04"


# ---------------------------------------------------------------------------
# Moteur de calcul (couche 3 : générique par signe)
# ---------------------------------------------------------------------------
def test_compute_generic_weekly_by_sign_matches_documented_example():
    """Exemple du document source : pour le Bélier comme signe cible (Ascendant générique), le
    Cancer occupe la maison 4 générique — ici l'événement (`main_event_sign`) est en Cancer, et
    on lit la ligne du Bélier."""
    by_sign = compute_generic_weekly_by_sign("Cancer")
    aries = next(row for row in by_sign if row["sign"] == "Aries")
    assert aries["generic_house"] == 4
    assert aries["house_keyword"] == "foyer"


def test_compute_generic_weekly_by_sign_marks_main_event_sign_as_house_one():
    by_sign = compute_generic_weekly_by_sign("Scorpio")
    scorpio = next(row for row in by_sign if row["sign"] == "Scorpio")
    assert scorpio["generic_house"] == 1
    assert scorpio["house_keyword"] == "identité"
    assert scorpio["is_main_event_sign"] is True
    assert sum(row["is_main_event_sign"] for row in by_sign) == 1


def test_compute_generic_weekly_by_sign_covers_all_twelve_signs_exactly_once_per_house():
    by_sign = compute_generic_weekly_by_sign("Leo")
    assert len(by_sign) == 12
    assert sorted(row["generic_house"] for row in by_sign) == list(range(1, 13))


def test_house_score_reuses_aspect_nature_and_is_within_1_to_5():
    # Maisons 5/9 (trigone, harmonieux) doivent être notées au-dessus des maisons 6/8
    # (quinconce, mineur inconfortable) — le même vocabulaire "nature" que aspects.json.
    assert _house_score(5) == 5
    assert _house_score(9) == 5
    assert _house_score(6) == 2
    assert _house_score(8) == 2
    assert _house_score(1) == 4  # conjonction : énergie forte mais neutre ("variable")
    for house in range(1, 13):
        assert 1 <= _house_score(house) <= 5


def test_compute_generic_weekly_by_sign_scores_differentiate_signs():
    """La note doit varier d'un signe à l'autre (pas une valeur plate) pour permettre de
    comparer quel signe s'en sort le mieux ou le moins bien cette semaine-là."""
    by_sign = compute_generic_weekly_by_sign("Scorpio")
    scores = {row["sign"]: row["score"] for row in by_sign}
    assert len(set(scores.values())) > 1
    assert scores["Scorpio"] == 4  # maison 1 générique, is_main_event_sign
    assert all(1 <= s <= 5 for s in scores.values())


# ---------------------------------------------------------------------------
# Notation par domaine de vie (voir app/core/weekly_weather_domains.py et
# app/reference_data/weekly_domain_scoring.json)
# ---------------------------------------------------------------------------
def _personal_event(transiting_planet, natal_point, aspect_type, aspect_type_fr, peak_date):
    return {
        "transiting_planet": transiting_planet, "natal_point": natal_point,
        "type": aspect_type, "type_fr": aspect_type_fr,
        "peak_date": peak_date, "peak_orb": 0.3,
        "window_start": "2027-02-01", "window_end": "2027-02-12",
        "favorability": "neutre", "favorability_description": "", "intensity": 3,
    }


def test_compute_weekly_domain_scores_benefic_trine_applying_is_favorable():
    start = date(2027, 2, 3)
    # Vénus trigone Vénus natale (bénéfique, +2), pic après le début de semaine => applicatif (x1.3).
    events = [_personal_event("Venus", "Venus", "trine", "trigone", "2027-02-05")]
    scores = compute_weekly_domain_scores({"Venus": 5}, events, [], start)
    assert scores["amour"]["note"] == 4
    assert scores["amour"]["label"] == "semaine favorable"
    assert scores["amour"]["top_positive_signal"] == "Venus transit trigone Venus natal"
    assert scores["amour"]["top_negative_signal"] is None
    # Vénus n'appartient pas aux planètes de référence de santé, ni sa maison (5) à houses_ref
    # de santé ([1, 6]) : le domaine santé n'est pas concerné, score neutre par défaut.
    assert scores["sante"]["note"] == 3
    assert scores["sante"]["top_positive_signal"] is None


def test_compute_weekly_domain_scores_demanding_square_is_negative_signal():
    start = date(2027, 2, 3)
    # Mars carré Saturne natale (exigeante, -2), pic avant le début de semaine => séparatif (x0.7).
    events = [_personal_event("Mars", "Saturn", "square", "carré", "2027-02-01")]
    scores = compute_weekly_domain_scores({"Saturn": 10}, events, [], start)
    for area in ("sante", "travail_quotidien"):  # Mars ET Saturne y figurent tous les deux
        assert scores[area]["top_negative_signal"] == "Mars transit carré Saturn natal"
        assert scores[area]["note"] < 4


def test_compute_weekly_domain_scores_matches_by_natal_house_even_without_planet_ref():
    """Le Soleil n'est PAS dans planets_ref de 'amour', mais s'il occupe la maison 7 (dans
    houses_ref de 'amour'), un transit qui le touche doit quand même colorer ce domaine."""
    start = date(2027, 2, 3)
    events = [_personal_event("Jupiter", "Sun", "sextile", "sextile", "2027-02-05")]
    scores = compute_weekly_domain_scores({"Sun": 7}, events, [], start)
    assert scores["amour"]["top_positive_signal"] is not None
    assert scores["argent"]["top_positive_signal"] is None  # maison 7 hors houses_ref de argent


def test_compute_weekly_domain_scores_collective_generational_aspect_is_weighted_lighter():
    """Le même aspect (trigone Vénus bénéfique) pèse moitié moins en composante collective
    (generational_aspects, x0.5) qu'en composante personnelle applicative (x1.3)."""
    start = date(2027, 2, 3)
    personal = [_personal_event("Venus", "Venus", "trine", "trigone", "2027-02-05")]
    collective = [{"date": "2027-02-05", "planet_a": "Venus", "planet_b": "Jupiter", "aspect_type": "trine", "aspect_type_fr": "trigone", "score": 3}]

    personal_scores = compute_weekly_domain_scores({"Venus": 5}, personal, [], start)
    collective_scores = compute_weekly_domain_scores({"Venus": 5}, [], collective, start)

    assert collective_scores["amour"]["note"] <= personal_scores["amour"]["note"]
    assert collective_scores["amour"]["top_positive_signal"] is not None


def test_compute_weekly_domain_scores_unrecognized_aspect_type_is_ignored_not_crashed():
    start = date(2027, 2, 3)
    events = [_personal_event("Venus", "Venus", "quintile", "quintile", "2027-02-05")]  # aspect mineur non couvert par le barème
    scores = compute_weekly_domain_scores({"Venus": 5}, events, [], start)
    assert scores["amour"]["note"] == 3  # aucun signal retenu => note neutre par défaut
    assert scores["amour"]["top_positive_signal"] is None


def test_compute_weekly_domain_scores_covers_all_four_life_areas():
    start = date(2027, 2, 3)
    scores = compute_weekly_domain_scores({}, [], [], start)
    assert set(scores.keys()) == {"amour", "argent", "sante", "travail_quotidien"}
    for area in scores.values():
        assert 1 <= area["note"] <= 5
        assert isinstance(area["label"], str) and area["label"]


def test_compute_weekly_domain_scores_score_boundaries_have_no_gap():
    """La pondération applicatif/séparatif (x1.3/x0.7) produit des sommes non entières : le
    barème doit rester continu (aucun intervalle non couvert) sur toute une plage réaliste."""
    from app.core.reference_data import weekly_domain_scoring
    from app.core.weekly_weather_domains import _note_for_score

    final_scale = weekly_domain_scoring()["final_scale"]
    for tenth in range(-100, 101):
        note, label = _note_for_score(tenth / 10, final_scale)
        assert 1 <= note <= 5
        assert label


def test_compute_weekly_domain_scores_is_json_serializable():
    import json

    start = date(2027, 2, 3)
    events = [_personal_event("Venus", "Venus", "trine", "trigone", "2027-02-05")]
    json.dumps(compute_weekly_domain_scores({"Venus": 5}, events, [], start))


# ---------------------------------------------------------------------------
# Service (cache)
# ---------------------------------------------------------------------------
def test_get_or_compute_weekly_weather_caches_across_calls(client):
    db = SessionLocal()
    try:
        target_date = date(2031, 3, 2)
        first = get_or_compute_weekly_weather(db, target_date)
        count_after_first = db.query(GlobalWeeklyWeatherCache).filter_by(period_start=target_date).count()
        second = get_or_compute_weekly_weather(db, target_date)
        count_after_second = db.query(GlobalWeeklyWeatherCache).filter_by(period_start=target_date).count()
        assert first == second
        assert count_after_first == count_after_second == 1
    finally:
        db.close()


def test_get_or_compute_weekly_weather_handles_concurrent_cache_miss(client):
    db = SessionLocal()
    other_db = SessionLocal()
    try:
        target_date = date(2031, 4, 6)
        original_commit = db.commit

        def commit_after_concurrent_winner():
            get_or_compute_weekly_weather(other_db, target_date)
            return original_commit()

        db.commit = commit_after_concurrent_winner
        result = get_or_compute_weekly_weather(db, target_date)
        assert result["period_start"] == target_date.isoformat()
    finally:
        db.close()
        other_db.close()


def test_compute_domain_scores_for_chart_returns_all_areas_and_reuses_cached_collective():
    from tests.test_interpretation_service import _make_chart

    db = SessionLocal()
    try:
        chart = _make_chart()
        target_date = date(2027, 2, 3)
        # Réutilise le cache collectif déjà rempli par les tests ci-dessus pour cette même
        # semaine, plutôt que de recalculer : vérifie juste qu'aucune exception n'est levée et
        # que la ligne de cache n'est pas dupliquée.
        get_or_compute_weekly_weather(db, target_date)
        count_before = db.query(GlobalWeeklyWeatherCache).filter_by(period_start=target_date).count()

        scores = compute_domain_scores_for_chart(db, chart, target_date)

        count_after = db.query(GlobalWeeklyWeatherCache).filter_by(period_start=target_date).count()
        assert count_before == count_after == 1
        assert set(scores.keys()) == {"amour", "argent", "sante", "travail_quotidien"}
        for area in scores.values():
            assert 1 <= area["note"] <= 5
    finally:
        db.close()


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------
def test_weekly_weather_endpoint_defaults_to_today(client):
    res = client.get("/api/weekly-weather")
    assert res.status_code == 200
    body = res.json()
    assert body["period_start"] == date.today().isoformat()


def test_weekly_weather_endpoint_accepts_explicit_start_date(client):
    res = client.get("/api/weekly-weather", params={"start_date": "2027-02-03"})
    assert res.status_code == 200
    body = res.json()
    assert body["period_start"] == "2027-02-03"
    assert body["period_end"] == "2027-02-09"
    assert len(body["moon_path"]) == 7


def test_weekly_weather_endpoint_is_cached_between_requests(client):
    res1 = client.get("/api/weekly-weather", params={"start_date": "2033-06-01"})
    res2 = client.get("/api/weekly-weather", params={"start_date": "2033-06-01"})
    assert res1.json() == res2.json()


def test_weekly_weather_by_sign_endpoint_returns_twelve_signs_one_flagged(client):
    res = client.get("/api/weekly-weather/by-sign", params={"start_date": "2027-02-03"})
    assert res.status_code == 200
    body = res.json()
    assert len(body["by_sign"]) == 12
    flagged = [row for row in body["by_sign"] if row["is_main_event_sign"]]
    assert len(flagged) == 1
    assert flagged[0]["sign"] == body["main_event_sign"]


def test_weekly_weather_domain_scores_endpoint_returns_four_areas(client):
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

    res = client.get(f"/api/charts/{chart_id}/weekly-weather/domain-scores", params={"start_date": "2027-02-03"})
    assert res.status_code == 200
    body = res.json()
    assert body["period_start"] == "2027-02-03"
    assert body["period_end"] == "2027-02-09"
    assert set(body["scores"].keys()) == {"amour", "argent", "sante", "travail_quotidien"}
    for area in body["scores"].values():
        assert 1 <= area["note"] <= 5
        assert area["label"]


def test_weekly_weather_domain_scores_endpoint_rejects_unowned_chart(client):
    res = client.get("/api/charts/does-not-exist/weekly-weather/domain-scores")
    assert res.status_code == 404


# ---------------------------------------------------------------------------
# Lecture LLM
# ---------------------------------------------------------------------------
def test_weekly_weather_reading_payload_returns_503_without_api_key(client):
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
        json={"reading_type": "weekly_weather", "weekly_weather_start_date": "2027-02-03"},
    )
    assert res.status_code == 503

    res_by_sign = client.post(
        f"/api/charts/{chart_id}/readings",
        json={"reading_type": "weekly_weather_by_sign", "weekly_weather_start_date": "2027-02-03"},
    )
    assert res_by_sign.status_code == 503


def test_weekly_weather_prompt_is_distinct_and_explains_two_layers():
    from app import schemas

    prompt = interpretation_service._build_system_prompt(schemas.ReadingRequest(reading_type="weekly_weather"))
    other_prompt = interpretation_service._build_system_prompt(schemas.ReadingRequest(reading_type="witchy_calendar"))
    assert prompt != other_prompt
    assert "collective" in prompt
    assert "personal_highlights" in prompt
    assert "generational_aspects" in prompt
    assert "domain_scores" in prompt


def test_weekly_weather_payload_includes_domain_scores_for_all_four_areas():
    from app import schemas
    from tests.test_interpretation_service import _make_chart

    chart = _make_chart()
    request = schemas.ReadingRequest(reading_type="weekly_weather", weekly_weather_start_date=date(2027, 2, 3))
    payload = interpretation_service._build_user_payload(chart, request)
    assert set(payload["domain_scores"].keys()) == {"amour", "argent", "sante", "travail_quotidien"}
    assert "generational_aspects" in payload["collective"]


def test_weekly_weather_by_sign_prompt_is_distinct_and_forbids_natal_identity():
    from app import schemas

    prompt = interpretation_service._build_system_prompt(schemas.ReadingRequest(reading_type="weekly_weather_by_sign"))
    other_prompt = interpretation_service._build_system_prompt(schemas.ReadingRequest(reading_type="weekly_weather"))
    assert prompt != other_prompt
    assert "by_sign" in prompt
    assert "generic_house" in prompt


def test_weekly_weather_by_sign_payload_has_no_identity_block():
    from app import schemas
    from tests.test_interpretation_service import _make_chart

    chart = _make_chart()
    request = schemas.ReadingRequest(reading_type="weekly_weather_by_sign", weekly_weather_start_date=date(2027, 2, 3))
    payload = interpretation_service._build_user_payload(chart, request)
    assert "identity" not in payload
    assert len(payload["by_sign"]) == 12
