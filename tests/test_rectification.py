from datetime import date

from app.core.rectification import LifeEvent, scan_candidate_times

BIRTH_KWARGS = dict(
    birth_date=date(1990, 5, 15),
    timezone="Europe/Paris",
    latitude=45.7640,
    longitude=4.8357,
)


def test_scan_returns_ranked_candidates_with_valid_structure():
    events = [
        LifeEvent(label="Mariage", event_date=date(2018, 6, 10), significance="major"),
        LifeEvent(label="Déménagement", event_date=date(2015, 3, 1), significance="moderate"),
    ]
    result = scan_candidate_times(
        **BIRTH_KWARGS, life_events=events, window_start="06:00:00", window_end="12:00:00", step_minutes=15
    )
    assert "warning" in result and result["warning"]
    assert result["candidates"]
    # Classé par score décroissant.
    scores = [c["total_score"] for c in result["candidates"]]
    assert scores == sorted(scores, reverse=True)
    for c in result["candidates"]:
        assert c["ascendant_sign"]
        assert 0 <= c["ascendant_degree"] < 30
        assert all(m["method"] in {"transit", "solar_arc", "progressed_moon"} for m in c["matches"])


def test_scan_respects_time_window():
    events = [LifeEvent(label="Test", event_date=date(2020, 1, 1))]
    result = scan_candidate_times(
        **BIRTH_KWARGS, life_events=events, window_start="08:00:00", window_end="09:00:00", step_minutes=10
    )
    times = [c["time"] for c in result["candidates"]]
    assert all("08:" <= t[:3] or t == "09:00:00" for t in times)


def test_scan_filters_by_candidate_signs():
    events = [LifeEvent(label="Test", event_date=date(2020, 1, 1))]
    result = scan_candidate_times(
        **BIRTH_KWARGS,
        life_events=events,
        window_start="00:00:00",
        window_end="23:00:00",
        step_minutes=30,
        candidate_signs=["Leo"],
        top_n=50,
    )
    assert all(c["ascendant_sign"] == "Leo" for c in result["candidates"])
    assert all(entry["sign"] == "Leo" for entry in result["by_sign_summary"])


def test_scan_with_no_life_events_returns_zero_scores():
    result = scan_candidate_times(
        **BIRTH_KWARGS, life_events=[], window_start="10:00:00", window_end="10:30:00", step_minutes=10
    )
    assert all(c["total_score"] == 0 for c in result["candidates"])
    assert all(c["matches"] == [] for c in result["candidates"])


def test_by_sign_summary_covers_full_window_even_when_top_n_is_small():
    events = [LifeEvent(label="Test", event_date=date(2020, 1, 1))]
    result = scan_candidate_times(
        **BIRTH_KWARGS,
        life_events=events,
        window_start="00:00:00",
        window_end="23:00:00",
        step_minutes=60,
        top_n=2,
    )
    assert len(result["candidates"]) == 2
    assert len(result["by_sign_summary"]) > 2
