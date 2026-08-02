import asyncio
from datetime import date

from app import schemas
from app.config import Settings
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
    # Filtré aux événements significatifs, pas les centaines d'événements bruts (Lune incluse).
    assert 0 < len(payload["upcoming_events"]) <= 20
    assert all("intensity" in e for e in payload["upcoming_events"])


def test_select_significant_events_prefers_high_intensity_and_falls_back_when_scarce():
    events = [{"intensity": i, "peak_orb": 0.1, "peak_date": f"2026-01-{i:02d}"} for i in (1, 1, 1, 2, 4)]
    selected = interpretation_service._select_significant_events(events, min_count=3, max_count=10)
    # Seuil 4 -> 1 seul événement (< min_count), on redescend jusqu'à un seuil qui en donne >= 3.
    assert len(selected) >= 3
    assert selected == sorted(selected, key=lambda e: e["peak_date"])


def test_select_significant_events_caps_at_max_count():
    events = [{"intensity": 4, "peak_orb": i * 0.01, "peak_date": f"2026-01-{(i % 28) + 1:02d}"} for i in range(50)]
    selected = interpretation_service._select_significant_events(events, min_count=5, max_count=10)
    assert len(selected) == 10


def test_zodiacal_releasing_reading_payload_defaults_to_fortune_and_spirit():
    chart = _make_chart()
    request = schemas.ReadingRequest(reading_type="zodiacal_releasing", as_of_date=date(2026, 8, 2))
    payload = interpretation_service._build_user_payload(chart, request)

    assert payload["as_of_date"] == "2026-08-02"
    assert set(payload["lots"].keys()) == {"Lot de Fortune", "Lot d'Esprit"}
    for lot_entry in payload["lots"].values():
        assert lot_entry["current_l1"] is not None
        assert lot_entry["current_l2"] is not None
        assert len(lot_entry["current_l1_l2_periods"]) > 0
        assert lot_entry["signification"]


def test_zodiacal_releasing_reading_payload_honors_selected_lots():
    chart = _make_chart()
    request = schemas.ReadingRequest(
        reading_type="zodiacal_releasing", zr_selected_lots=["Lot d'Amour", "Lot de Mariage", "Lot des Enfants"]
    )
    payload = interpretation_service._build_user_payload(chart, request)
    assert set(payload["lots"].keys()) == {"Lot d'Amour", "Lot de Mariage", "Lot des Enfants"}


def test_zodiacal_releasing_predictive_mode_returns_l1_periods_instead_of_l2_detail():
    chart = _make_chart()
    request = schemas.ReadingRequest(reading_type="zodiacal_releasing", zr_mode="predictive")
    payload = interpretation_service._build_user_payload(chart, request)
    for lot_entry in payload["lots"].values():
        assert "l1_periods" in lot_entry
        assert len(lot_entry["l1_periods"]) > 0
        assert "current_l1_l2_periods" not in lot_entry


def test_zodiacal_releasing_prompt_asks_for_compiled_chronology_with_multiple_lots():
    request = schemas.ReadingRequest(
        reading_type="zodiacal_releasing", zr_selected_lots=["Lot d'Amour", "Lot de Mariage"]
    )
    prompt = interpretation_service._build_system_prompt(request)
    assert "COMPILE-les en un seul récit" in prompt
    assert "convergence" in prompt


def test_zodiacal_releasing_prompt_goes_deep_for_a_single_lot():
    request = schemas.ReadingRequest(reading_type="zodiacal_releasing", zr_selected_lots=["Lot de Carrière"])
    prompt = interpretation_service._build_system_prompt(request)
    assert "lecture approfondie" in prompt
    assert "COMPILE-les en un seul récit" not in prompt
    assert "convergence" not in prompt


def test_zodiacal_releasing_predictive_prompt_asks_for_strong_years_and_concrete_scenarios():
    request = schemas.ReadingRequest(
        reading_type="zodiacal_releasing", zr_selected_lots=["Lot d'Argent (Richesse)", "Lot de Mariage"], zr_mode="predictive"
    )
    prompt = interpretation_service._build_system_prompt(request)
    assert "ANNÉES FORTES" in prompt
    assert "scénarios concrets" in prompt
    assert "SIGNE" in prompt and "ruling_planet" in prompt


def test_zodiacal_releasing_max_tokens_scale_with_lots_and_mode():
    few_current = schemas.ReadingRequest(reading_type="zodiacal_releasing")
    many_predictive = schemas.ReadingRequest(
        reading_type="zodiacal_releasing",
        zr_selected_lots=["Lot d'Amour", "Lot de Mariage", "Lot des Enfants", "Lot de Carrière"],
        zr_mode="predictive",
    )
    assert interpretation_service._zodiacal_releasing_max_tokens(
        many_predictive
    ) > interpretation_service._zodiacal_releasing_max_tokens(few_current)


def test_specialized_system_prompts_are_distinct_per_reading_type():
    prompts = {
        rtype: interpretation_service._build_system_prompt(schemas.ReadingRequest(reading_type=rtype))
        for rtype in ["global", "lots", "derived_houses", "timing", "zodiacal_releasing"]
    }
    assert len(set(prompts.values())) == 5  # les 5 prompts doivent différer
    assert "LOTS" in prompts["lots"]
    assert "MAISONS DÉRIVÉES" in prompts["derived_houses"]
    assert "DOUZE PROCHAINS MOIS" in prompts["timing"]
    assert "RÉPARTITION ZODIACALE" in prompts["zodiacal_releasing"]


# ---------------------------------------------------------------------------
# generate_reading : ne jamais renvoyer une lecture coupée en plein milieu d'une phrase.
# ---------------------------------------------------------------------------
class _FakeUsage:
    def __init__(self, input_tokens: int, output_tokens: int):
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens


class _FakeTextBlock:
    type = "text"

    def __init__(self, text: str):
        self.text = text


class _FakeResponse:
    def __init__(self, text: str, stop_reason: str):
        self.content = [_FakeTextBlock(text)]
        self.stop_reason = stop_reason
        self.usage = _FakeUsage(input_tokens=100, output_tokens=50)


class _FakeMessages:
    def __init__(self, responses: list[_FakeResponse]):
        self._responses = list(responses)
        self.calls: list[dict] = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        return self._responses.pop(0)


class _FakeAnthropicClient:
    def __init__(self, responses: list[_FakeResponse]):
        self.messages = _FakeMessages(responses)


def _settings_with_key() -> Settings:
    return Settings(anthropic_api_key="fake-key-for-tests")


def test_generate_reading_continues_when_cut_off_by_max_tokens(monkeypatch):
    chart = _make_chart()
    request = schemas.ReadingRequest(reading_type="global", focus_areas=["general"])

    fake_client = _FakeAnthropicClient(
        [
            _FakeResponse("Première partie de la lecture, coupée en pl", stop_reason="max_tokens"),
            _FakeResponse("eine phrase mais qui se termine correctement.", stop_reason="end_turn"),
        ]
    )
    monkeypatch.setattr(interpretation_service, "get_settings", _settings_with_key)
    monkeypatch.setattr(interpretation_service, "AsyncAnthropic", lambda api_key: fake_client)

    result = asyncio.run(interpretation_service.generate_reading(chart, request))

    assert result["reading_text"] == "Première partie de la lecture, coupée en pleine phrase mais qui se termine correctement."
    assert len(fake_client.messages.calls) == 2
    # Le texte partiel doit être repassé en tour "assistant" (préremplissage), sans nouveau
    # message "user" demandant de continuer.
    second_call_messages = fake_client.messages.calls[1]["messages"]
    assert second_call_messages[-1] == {"role": "assistant", "content": "Première partie de la lecture, coupée en pl"}
    assert result["tokens_used"] == 300  # (100+50) x 2 appels


def test_generate_reading_does_not_continue_when_response_completes_normally(monkeypatch):
    chart = _make_chart()
    request = schemas.ReadingRequest(reading_type="global", focus_areas=["general"])

    fake_client = _FakeAnthropicClient([_FakeResponse("Lecture complète en un seul appel.", stop_reason="end_turn")])
    monkeypatch.setattr(interpretation_service, "get_settings", _settings_with_key)
    monkeypatch.setattr(interpretation_service, "AsyncAnthropic", lambda api_key: fake_client)

    result = asyncio.run(interpretation_service.generate_reading(chart, request))

    assert result["reading_text"] == "Lecture complète en un seul appel."
    assert len(fake_client.messages.calls) == 1


def test_generate_reading_stops_after_max_continuation_rounds(monkeypatch):
    chart = _make_chart()
    request = schemas.ReadingRequest(reading_type="global", focus_areas=["general"])

    # Toujours tronqué : vérifie qu'on ne boucle pas indéfiniment.
    responses = [_FakeResponse(f"partie {i} ", stop_reason="max_tokens") for i in range(10)]
    fake_client = _FakeAnthropicClient(responses)
    monkeypatch.setattr(interpretation_service, "get_settings", _settings_with_key)
    monkeypatch.setattr(interpretation_service, "AsyncAnthropic", lambda api_key: fake_client)

    result = asyncio.run(interpretation_service.generate_reading(chart, request))

    assert len(fake_client.messages.calls) == interpretation_service.MAX_CONTINUATION_ROUNDS + 1
    assert result["reading_text"] == "".join(f"partie {i} " for i in range(interpretation_service.MAX_CONTINUATION_ROUNDS + 1))


def test_basic_reading_types_include_focus_zone_section():
    request = schemas.ReadingRequest(reading_type="love", focus_areas=["love"])
    prompt = interpretation_service._build_system_prompt(request)
    assert "ZONES À COUVRIR" in prompt


def test_specialized_reading_types_omit_focus_zone_section():
    request = schemas.ReadingRequest(reading_type="lots")
    prompt = interpretation_service._build_system_prompt(request)
    assert "ZONES À COUVRIR" not in prompt
