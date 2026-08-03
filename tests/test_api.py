import pytest
from fastapi.testclient import TestClient

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

OTHER_CHART_PAYLOAD = {
    "birth_data": {
        "date": "1988-11-02",
        "time": "08:15:00",
        "time_known": True,
        "timezone": "Europe/Paris",
        "location": {"city": "Paris", "country": "France", "latitude": 48.8566, "longitude": 2.3522},
    }
}


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_create_and_fetch_chart(client):
    create_res = client.post("/api/charts", json=VALID_CHART_PAYLOAD)
    assert create_res.status_code == 201
    chart = create_res.json()
    assert chart["computed_chart_data"]["planets"]

    get_res = client.get(f"/api/charts/{chart['id']}")
    assert get_res.status_code == 200
    assert get_res.json()["id"] == chart["id"]


def test_list_charts_scoped_to_session(client):
    create_res = client.post("/api/charts", json=VALID_CHART_PAYLOAD)
    list_res = client.get("/api/charts")
    assert list_res.status_code == 200
    assert len(list_res.json()) == 1


def test_chart_not_accessible_from_another_session(client):
    create_res = client.post("/api/charts", json=VALID_CHART_PAYLOAD)
    chart_id = create_res.json()["id"]

    # Un tout nouveau client (donc sans le cookie de session émis ci-dessus) simule un autre visiteur.
    with TestClient(app) as other_client:
        other_session_res = other_client.get(f"/api/charts/{chart_id}")
    assert other_session_res.status_code == 403


def test_get_unknown_chart_returns_404(client):
    create_res = client.post("/api/charts", json=VALID_CHART_PAYLOAD)
    res = client.get("/api/charts/does-not-exist")
    assert res.status_code == 404


def test_reading_without_api_key_returns_503(client, monkeypatch):
    monkeypatch.setattr("app.services.interpretation_service.get_settings", lambda: _settings_without_key())
    create_res = client.post("/api/charts", json=VALID_CHART_PAYLOAD)
    chart_id = create_res.json()["id"]

    res = client.post(
        f"/api/charts/{chart_id}/readings",
        json={"reading_type": "global", "focus_areas": ["general"]},
    )
    assert res.status_code == 503


def test_reference_config_endpoint(client):
    res = client.get("/api/reference/config")
    assert res.status_code == 200
    assert "house_systems" in res.json()


def test_reference_timezones_endpoint(client):
    res = client.get("/api/reference/timezones")
    assert res.status_code == 200
    zones = res.json()
    assert "Europe/Paris" in zones
    assert zones == sorted(zones)
    # Alias historiques exclus au profit des identifiants canoniques 'Continent/Ville'.
    assert not any(z.startswith(("Etc/", "US/", "SystemV/")) for z in zones)


def test_reference_derived_house_relations_endpoint(client):
    res = client.get("/api/reference/derived-house-relations")
    assert res.status_code == 200
    data = res.json()
    assert {r["key"] for r in data["first_order"]} >= {"partner", "mother", "father", "business_partner"}
    assert {r["key"] for r in data["second_order"]} >= {"belle_famille", "grand_mere_maternelle"}


def test_reference_axes_thematiques_lots_endpoint(client):
    res = client.get("/api/reference/axes-thematiques-lots")
    assert res.status_code == 200
    data = res.json()
    assert data["liste_finale_validee"]["total"] == 17
    codes = {axis["code"] for axis in data["axes_thematiques"]["axes"]}
    assert codes == {
        "famille_racines", "corps_circonstances", "amour_relations",
        "vocation_reussite", "epreuves_resilience", "ouverture_reseau", "vue_complete",
    }


def test_chart_includes_lots_and_derived_houses(client):
    res = client.post("/api/charts", json=VALID_CHART_PAYLOAD)
    data = res.json()["computed_chart_data"]
    assert len(data["lots"]) == 17
    assert len(data["derived_houses"]) == 12
    lots_by_name = {lot["name"]: lot for lot in data["lots"]}
    assert lots_by_name["Fortune"]["certainty"]
    assert lots_by_name["Fortune"]["construction_logic"] is None
    assert lots_by_name["Amis"]["construction_logic"]
    assert lots_by_name["Amis"]["certainty"] is None


def test_timing_endpoint_returns_transits_and_profection(client):
    create_res = client.post("/api/charts", json=VALID_CHART_PAYLOAD)
    chart_id = create_res.json()["id"]

    res = client.get(f"/api/charts/{chart_id}/timing")
    assert res.status_code == 200
    body = res.json()
    assert len(body["transiting_planets"]) == 10  # toutes les planètes classiques, Lune/Mercure/Vénus/Soleil/Mars compris
    assert all("intensity" in a for a in body["aspects"])
    assert "profection" in body
    assert body["profection"]["profected_house"] in range(1, 13)


def test_timing_endpoint_accepts_explicit_date(client):
    create_res = client.post("/api/charts", json=VALID_CHART_PAYLOAD)
    chart_id = create_res.json()["id"]

    res = client.get(f"/api/charts/{chart_id}/timing", params={"date": "2000-01-01"})
    assert res.status_code == 200
    assert res.json()["date"] == "2000-01-01"


def test_timing_endpoint_404_for_unknown_chart(client):
    res = client.get("/api/charts/does-not-exist/timing")
    assert res.status_code == 404


def test_timing_forecast_endpoint_returns_events(client):
    create_res = client.post("/api/charts", json=VALID_CHART_PAYLOAD)
    chart_id = create_res.json()["id"]

    res = client.get(f"/api/charts/{chart_id}/timing/forecast", params={"date": "2026-08-02", "months": 12})
    assert res.status_code == 200
    body = res.json()
    assert body["start_date"] == "2026-08-02"
    assert len(body["events"]) > 0
    assert body["events"] == sorted(body["events"], key=lambda e: e["peak_date"])


def test_zodiacal_releasing_endpoint_returns_current_phases_for_all_lots(client):
    create_res = client.post("/api/charts", json=VALID_CHART_PAYLOAD)
    chart_id = create_res.json()["id"]

    res = client.get(f"/api/charts/{chart_id}/zodiacal-releasing", params={"date": "2026-08-02"})
    assert res.status_code == 200
    body = res.json()
    assert body["as_of_date"] == "2026-08-02"
    assert len(body["lots"]) == 17  # les 17 lots de la bibliothèque, pas seulement Fortune/Esprit
    assert "Fortune" in body["lots"]
    assert "Esprit" in body["lots"]
    for lot_result in body["lots"].values():
        assert lot_result["current_l1"] is not None
        assert lot_result["current_l2"] is not None
        assert lot_result["current_l1"]["start_date"] <= "2026-08-02" < lot_result["current_l1"]["end_date"]
        assert len(lot_result["current_l1_l2_periods"]) > 0


def test_zodiacal_releasing_endpoint_accepts_lookahead_years(client):
    create_res = client.post("/api/charts", json=VALID_CHART_PAYLOAD)
    chart_id = create_res.json()["id"]

    res = client.get(
        f"/api/charts/{chart_id}/zodiacal-releasing", params={"date": "2026-08-02", "lookahead_years": 10}
    )
    assert res.status_code == 200
    fortune_l1_periods = res.json()["lots"]["Fortune"]["l1_periods"]
    assert fortune_l1_periods[-1]["end_date"] >= "2036-07-02"


def test_zodiacal_releasing_endpoint_404_for_unknown_chart(client):
    res = client.get("/api/charts/does-not-exist/zodiacal-releasing")
    assert res.status_code == 404


def test_compatibility_endpoint_returns_synastry_data(client):
    chart_a_id = client.post("/api/charts", json=VALID_CHART_PAYLOAD).json()["id"]
    chart_b_id = client.post("/api/charts", json=OTHER_CHART_PAYLOAD).json()["id"]

    res = client.get(
        f"/api/charts/{chart_a_id}/compatibility", params={"chart_b_id": chart_b_id, "mode": "romantic"}
    )
    assert res.status_code == 200
    body = res.json()
    assert body["relationship_mode"] == "romantic"
    assert body["chart_a_id"] == chart_a_id
    assert body["chart_b_id"] == chart_b_id
    assert len(body["inter_aspects"]) > 0
    assert len(body["house_overlay"]["a_planets_in_b_houses"]) == 12  # 10 classiques + nœuds N/S par défaut
    assert "Sun" in body["composite_chart"]["points"]


def test_compatibility_endpoint_rejects_invalid_mode(client):
    chart_a_id = client.post("/api/charts", json=VALID_CHART_PAYLOAD).json()["id"]
    chart_b_id = client.post("/api/charts", json=OTHER_CHART_PAYLOAD).json()["id"]

    res = client.get(
        f"/api/charts/{chart_a_id}/compatibility", params={"chart_b_id": chart_b_id, "mode": "person_company"}
    )
    assert res.status_code == 422


def test_compatibility_endpoint_rejects_same_chart_twice(client):
    chart_a_id = client.post("/api/charts", json=VALID_CHART_PAYLOAD).json()["id"]

    res = client.get(
        f"/api/charts/{chart_a_id}/compatibility", params={"chart_b_id": chart_a_id, "mode": "romantic"}
    )
    assert res.status_code == 422


def test_compatibility_endpoint_404_when_chart_b_unknown(client):
    chart_a_id = client.post("/api/charts", json=VALID_CHART_PAYLOAD).json()["id"]

    res = client.get(
        f"/api/charts/{chart_a_id}/compatibility", params={"chart_b_id": "does-not-exist", "mode": "romantic"}
    )
    assert res.status_code == 404


def test_compatibility_reading_requires_chart_b_id(client):
    chart_a_id = client.post("/api/charts", json=VALID_CHART_PAYLOAD).json()["id"]

    res = client.post(
        f"/api/charts/{chart_a_id}/readings",
        json={"reading_type": "compatibility", "relationship_mode": "romantic"},
    )
    assert res.status_code == 422


def test_compatibility_reading_checks_ownership_of_chart_b(client):
    chart_a_id = client.post("/api/charts", json=VALID_CHART_PAYLOAD).json()["id"]

    with TestClient(app) as other_client:
        other_chart_id = other_client.post("/api/charts", json=OTHER_CHART_PAYLOAD).json()["id"]

    res = client.post(
        f"/api/charts/{chart_a_id}/readings",
        json={"reading_type": "compatibility", "relationship_mode": "romantic", "chart_b_id": other_chart_id},
    )
    assert res.status_code == 403


def test_compatibility_endpoint_403_when_chart_b_belongs_to_another_session(client):
    chart_a_id = client.post("/api/charts", json=VALID_CHART_PAYLOAD).json()["id"]

    with TestClient(app) as other_client:
        other_chart_id = other_client.post("/api/charts", json=OTHER_CHART_PAYLOAD).json()["id"]

    res = client.get(
        f"/api/charts/{chart_a_id}/compatibility", params={"chart_b_id": other_chart_id, "mode": "romantic"}
    )
    assert res.status_code == 403


def _settings_without_key():
    from app.config import Settings

    return Settings(anthropic_api_key="")
