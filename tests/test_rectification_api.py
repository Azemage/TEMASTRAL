import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_ascendant_rectification_traits_endpoint(client):
    res = client.get("/api/reference/ascendant-rectification-traits")
    assert res.status_code == 200
    data = res.json()
    assert "categories" in data
    assert len(data["categories"]) == 4
    for category in data["categories"]:
        assert len(category["options"]) == 12


def test_rectification_scan_endpoint_returns_ranked_candidates(client):
    payload = {
        "birth_date": "1990-05-15",
        "timezone": "Europe/Paris",
        "latitude": 45.764,
        "longitude": 4.8357,
        "window_start": "08:00:00",
        "window_end": "12:00:00",
        "step_minutes": 20,
        "life_events": [
            {"label": "Mariage", "date": "2018-06-10", "significance": "major"},
            {"label": "Déménagement", "date": "2015-03-01", "significance": "moderate"},
        ],
    }
    res = client.post("/api/rectification/scan", json=payload)
    assert res.status_code == 200
    body = res.json()
    assert "warning" in body and body["warning"]
    assert body["candidates"]
    scores = [c["total_score"] for c in body["candidates"]]
    assert scores == sorted(scores, reverse=True)


def test_rectification_scan_endpoint_filters_by_candidate_signs(client):
    payload = {
        "birth_date": "1990-05-15",
        "timezone": "Europe/Paris",
        "latitude": 45.764,
        "longitude": 4.8357,
        "window_start": "00:00:00",
        "window_end": "23:00:00",
        "step_minutes": 30,
        "candidate_signs": ["Leo"],
        "life_events": [{"label": "Test", "date": "2020-01-01"}],
    }
    res = client.post("/api/rectification/scan", json=payload)
    assert res.status_code == 200
    body = res.json()
    assert all(c["ascendant_sign"] == "Leo" for c in body["candidates"])
