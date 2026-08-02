from datetime import date

from app import schemas
from app.core.chart_calculator import calculate_natal_chart
from app.services import interpretation_service


class _FakeChart:
    subject_name = "Test"
    relationship_to_user = "self"
    birth_date = date(1990, 5, 15)
    birth_time_known = True
    birth_city = "Lyon"
    birth_country = "France"
    house_system = "placidus"
    zodiac_type = "tropical"
    rulership_system = "both"

    def __init__(self, computed_chart_data):
        self.computed_chart_data = computed_chart_data


def _make_chart():
    data = calculate_natal_chart(
        birth_date="1990-05-15",
        birth_time="14:32:00",
        time_known=True,
        timezone="Europe/Paris",
        latitude=45.7640,
        longitude=4.8357,
    )
    return _FakeChart(data)


def test_global_reading_payload_excludes_lots_and_derived_houses():
    chart = _make_chart()
    request = schemas.ReadingRequest(reading_type="global")
    payload = interpretation_service._build_user_payload(chart, request)

    assert "lots" not in payload["chart_data"]
    assert "derived_houses" not in payload["chart_data"]
    assert "planets" in payload["chart_data"]  # les données de base restent présentes


def test_lots_reading_payload_contains_only_lots_and_identity():
    chart = _make_chart()
    request = schemas.ReadingRequest(reading_type="lots")
    payload = interpretation_service._build_user_payload(chart, request)

    assert "chart_data" not in payload
    assert len(payload["lots"]) == 14
    assert set(payload["identity"].keys()) == {"sun", "moon", "ascendant", "is_day_chart"}


def test_derived_houses_reading_payload_uses_requested_reference_house():
    chart = _make_chart()
    request = schemas.ReadingRequest(reading_type="derived_houses", reference_house=4)
    payload = interpretation_service._build_user_payload(chart, request)

    assert payload["reference_house"] == 4
    assert payload["derived_house_mapping"]["reference_house"] == 4


def test_derived_houses_reading_defaults_to_house_7():
    chart = _make_chart()
    request = schemas.ReadingRequest(reading_type="derived_houses")
    payload = interpretation_service._build_user_payload(chart, request)
    assert payload["reference_house"] == 7


def test_timing_reading_payload_includes_profection_transits_and_forecast():
    chart = _make_chart()
    request = schemas.ReadingRequest(reading_type="timing", as_of_date=date(2026, 8, 2))
    payload = interpretation_service._build_user_payload(chart, request)

    assert payload["profection"]["as_of_date"] == "2026-08-02"
    assert "aspects" in payload["current_transits"]
    assert isinstance(payload["upcoming_events"], list)


def test_specialized_system_prompts_are_distinct_per_reading_type():
    prompts = {
        rtype: interpretation_service._build_system_prompt(schemas.ReadingRequest(reading_type=rtype))
        for rtype in ["global", "lots", "derived_houses", "timing"]
    }
    assert len(set(prompts.values())) == 4  # les 4 prompts doivent différer
    assert "LOTS" in prompts["lots"]
    assert "MAISONS DÉRIVÉES" in prompts["derived_houses"]
    assert "TIMING" in prompts["timing"]


def test_basic_reading_types_include_focus_zone_section():
    request = schemas.ReadingRequest(reading_type="love", focus_areas=["love"])
    prompt = interpretation_service._build_system_prompt(request)
    assert "ZONES À COUVRIR" in prompt


def test_specialized_reading_types_omit_focus_zone_section():
    request = schemas.ReadingRequest(reading_type="lots")
    prompt = interpretation_service._build_system_prompt(request)
    assert "ZONES À COUVRIR" not in prompt
