import asyncio
import json
from datetime import date, time

from app import schemas
from app.config import Settings
from app.core.chart_calculator import calculate_natal_chart
from app.services import interpretation_service


class _FakeChart:
    relationship_to_user = "self"
    birth_time_known = True
    birth_time = time(14, 32, 0)
    birth_timezone = "Europe/Paris"
    birth_country = "France"
    house_system = "placidus"
    zodiac_type = "tropical"
    rulership_system = "both"

    def __init__(
        self,
        computed_chart_data,
        subject_name="Test",
        birth_date=date(1990, 5, 15),
        birth_city="Lyon",
        id="fake-id",
        birth_latitude=45.7640,
        birth_longitude=4.8357,
    ):
        self.computed_chart_data = computed_chart_data
        self.subject_name = subject_name
        self.birth_date = birth_date
        self.birth_city = birth_city
        self.id = id
        self.birth_latitude = birth_latitude
        self.birth_longitude = birth_longitude


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


def _make_chart_b():
    data = calculate_natal_chart(
        birth_date="1988-11-02",
        birth_time="08:15:00",
        time_known=True,
        timezone="Europe/Paris",
        latitude=48.8566,
        longitude=2.3522,
    )
    return _FakeChart(
        data,
        subject_name="Partenaire",
        birth_date=date(1988, 11, 2),
        birth_city="Paris",
        id="fake-id-b",
        birth_latitude=48.8566,
        birth_longitude=2.3522,
    )


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
    assert len(payload["lots"]) == 17
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


def test_derived_houses_reading_resolves_relation_key_first_order():
    chart = _make_chart()
    request = schemas.ReadingRequest(reading_type="derived_houses", relation_key="mother")
    payload = interpretation_service._build_user_payload(chart, request)
    assert payload["reference_house"] == 4
    assert payload["relation"]["key"] == "mother"
    assert "derivation_path" not in payload["relation"]


def test_derived_houses_reading_resolves_relation_key_second_order():
    chart = _make_chart()
    request = schemas.ReadingRequest(reading_type="derived_houses", relation_key="belle_famille")
    payload = interpretation_service._build_user_payload(chart, request)
    assert payload["reference_house"] == 10  # derive(7, 4)
    assert payload["relation"]["derivation_path"]


def test_derived_houses_prompt_block_is_relation_aware():
    request = schemas.ReadingRequest(reading_type="derived_houses", relation_key="business_partner")
    block = interpretation_service._derived_houses_prompt_block(request)
    assert "Associé d'affaires" in block
    assert "Saturne, Mercure" in block


def test_timing_reading_payload_includes_profection_transits_and_forecast():
    chart = _make_chart()
    request = schemas.ReadingRequest(reading_type="timing", as_of_date=date(2026, 8, 2))
    payload = interpretation_service._build_user_payload(chart, request)

    assert payload["horizon"] == "year"  # défaut
    assert payload["profection"]["as_of_date"] == "2026-08-02"
    assert "aspects" in payload["current_transits"]
    assert isinstance(payload["upcoming_events"], list)
    # Filtré aux événements significatifs, pas les centaines d'événements bruts (Lune incluse).
    assert 0 < len(payload["upcoming_events"]) <= 20
    assert all("intensity" in e for e in payload["upcoming_events"])


def test_timing_reading_payload_honors_horizon():
    chart = _make_chart()
    for horizon in ("week", "month", "year"):
        request = schemas.ReadingRequest(reading_type="timing", as_of_date=date(2026, 8, 2), timing_horizon=horizon)
        payload = interpretation_service._build_user_payload(chart, request)
        assert payload["horizon"] == horizon
        for event in payload["upcoming_events"]:
            assert event["window_start"] <= "2027-08-02"
            assert event["window_end"] >= "2026-08-02"


def test_select_events_for_horizon_week_keeps_low_intensity_events():
    events = [
        {"intensity": 1, "peak_orb": 0.1, "peak_date": "2026-08-04", "window_start": "2026-08-03", "window_end": "2026-08-05"},
        {"intensity": 4, "peak_orb": 0.1, "peak_date": "2026-09-15", "window_start": "2026-09-14", "window_end": "2026-09-16"},
    ]
    selected = interpretation_service._select_events_for_horizon(events, "week", date(2026, 8, 2))
    assert len(selected) == 1
    assert selected[0]["intensity"] == 1  # l'événement mineur mais dans la fenêtre est gardé


def test_select_events_for_horizon_year_filters_to_significant_events():
    events = [
        {"intensity": 1, "peak_orb": 0.1, "peak_date": "2026-08-04", "window_start": "2026-08-03", "window_end": "2026-08-05"},
        {"intensity": 4, "peak_orb": 0.1, "peak_date": "2026-09-15", "window_start": "2026-09-14", "window_end": "2026-09-16"},
        {"intensity": 4, "peak_orb": 0.1, "peak_date": "2026-10-15", "window_start": "2026-10-14", "window_end": "2026-10-16"},
        {"intensity": 4, "peak_orb": 0.1, "peak_date": "2026-11-15", "window_start": "2026-11-14", "window_end": "2026-11-16"},
        {"intensity": 4, "peak_orb": 0.1, "peak_date": "2026-12-15", "window_start": "2026-12-14", "window_end": "2026-12-16"},
        {"intensity": 4, "peak_orb": 0.1, "peak_date": "2027-01-15", "window_start": "2027-01-14", "window_end": "2027-01-16"},
    ]
    selected = interpretation_service._select_events_for_horizon(events, "year", date(2026, 8, 2))
    assert all(e["intensity"] == 4 for e in selected)  # le minime (intensité 1) est écarté au profit des majeurs


def test_select_events_for_horizon_excludes_events_outside_the_window():
    events = [
        {"intensity": 4, "peak_orb": 0.1, "peak_date": "2027-06-01", "window_start": "2027-05-30", "window_end": "2027-06-03"},
    ]
    selected = interpretation_service._select_events_for_horizon(events, "week", date(2026, 8, 2))
    assert selected == []


def test_timing_prompt_varies_by_horizon():
    week_prompt = interpretation_service._build_system_prompt(
        schemas.ReadingRequest(reading_type="timing", timing_horizon="week")
    )
    year_prompt = interpretation_service._build_system_prompt(
        schemas.ReadingRequest(reading_type="timing", timing_horizon="year")
    )
    assert week_prompt != year_prompt
    assert "PONCTUEL" in week_prompt
    assert "GRANDS ARCS" in year_prompt


def test_timing_prompt_lists_timing_rating_axes():
    prompt = interpretation_service._build_system_prompt(schemas.ReadingRequest(reading_type="timing"))
    assert "timing_ratings" in prompt
    assert "developpement_personnel" in prompt
    assert "sante" in prompt


def test_timing_max_tokens_scale_by_horizon():
    week_tokens = interpretation_service._timing_max_tokens(schemas.ReadingRequest(reading_type="timing", timing_horizon="week"))
    month_tokens = interpretation_service._timing_max_tokens(schemas.ReadingRequest(reading_type="timing", timing_horizon="month"))
    year_tokens = interpretation_service._timing_max_tokens(schemas.ReadingRequest(reading_type="timing", timing_horizon="year"))
    assert week_tokens < month_tokens < year_tokens


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
    assert set(payload["lots"].keys()) == {"Fortune", "Esprit"}
    for lot_entry in payload["lots"].values():
        assert lot_entry["current_l1"] is not None
        assert lot_entry["current_l2"] is not None
        assert len(lot_entry["current_l1_l2_periods"]) > 0
        assert lot_entry["signification"]


def test_zodiacal_releasing_reading_payload_honors_selected_lots():
    chart = _make_chart()
    request = schemas.ReadingRequest(
        reading_type="zodiacal_releasing", zr_selected_lots=["Éros", "Mariage", "Enfants"]
    )
    payload = interpretation_service._build_user_payload(chart, request)
    assert set(payload["lots"].keys()) == {"Éros", "Mariage", "Enfants"}


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
        reading_type="zodiacal_releasing", zr_selected_lots=["Éros", "Mariage"]
    )
    prompt = interpretation_service._build_system_prompt(request)
    assert "COMPILE-les en un seul récit" in prompt
    assert "convergence" in prompt


def test_zodiacal_releasing_prompt_goes_deep_for_a_single_lot():
    request = schemas.ReadingRequest(reading_type="zodiacal_releasing", zr_selected_lots=["Victoire"])
    prompt = interpretation_service._build_system_prompt(request)
    assert "lecture approfondie" in prompt
    assert "COMPILE-les en un seul récit" not in prompt
    assert "convergence" not in prompt


def test_zodiacal_releasing_predictive_prompt_asks_for_strong_years_and_concrete_scenarios():
    request = schemas.ReadingRequest(
        reading_type="zodiacal_releasing", zr_selected_lots=["Substance", "Mariage"], zr_mode="predictive"
    )
    prompt = interpretation_service._build_system_prompt(request)
    assert "ANNÉES FORTES" in prompt
    assert "scénarios concrets" in prompt
    assert "SIGNE" in prompt and "ruling_planet" in prompt


def test_zodiacal_releasing_max_tokens_scale_with_lots_and_mode():
    few_current = schemas.ReadingRequest(reading_type="zodiacal_releasing")
    many_predictive = schemas.ReadingRequest(
        reading_type="zodiacal_releasing",
        zr_selected_lots=["Éros", "Mariage", "Enfants", "Victoire"],
        zr_mode="predictive",
    )
    assert interpretation_service._zodiacal_releasing_max_tokens(
        many_predictive
    ) > interpretation_service._zodiacal_releasing_max_tokens(few_current)


def test_zodiacal_releasing_axis_prompt_injects_layer1_qualification_and_prudence():
    request = schemas.ReadingRequest(
        reading_type="zodiacal_releasing",
        zr_selected_lots=["Fortune", "Maladie", "Mort", "Nécessité"],
        zr_mode="predictive",
        zr_axis_key="corps_circonstances",
    )
    prompt = interpretation_service._build_system_prompt(request)
    assert "AXE : Corps & Circonstances matérielles" in prompt
    assert "Couche 1" in prompt
    assert "JAMAIS de diagnostic" in prompt


def test_zodiacal_releasing_axis_prompt_absent_when_mode_is_current():
    request = schemas.ReadingRequest(
        reading_type="zodiacal_releasing",
        zr_selected_lots=["Fortune", "Maladie"],
        zr_mode="current",
        zr_axis_key="corps_circonstances",
    )
    prompt = interpretation_service._build_system_prompt(request)
    assert "AXE : Corps & Circonstances matérielles" not in prompt


def test_zodiacal_releasing_axis_payload_includes_natal_focal_data():
    chart = _make_chart()
    request = schemas.ReadingRequest(
        reading_type="zodiacal_releasing",
        zr_selected_lots=["Éros", "Mariage", "Amis"],
        zr_mode="predictive",
        zr_axis_key="amour_relations",
    )
    payload = interpretation_service._build_user_payload(chart, request)
    assert payload["axis"] == "amour_relations"
    assert "angles" in payload["natal_focal_data"]
    assert "derived_houses" in payload["natal_focal_data"]


def test_zodiacal_releasing_vue_complete_axis_has_no_natal_focal_data():
    chart = _make_chart()
    request = schemas.ReadingRequest(
        reading_type="zodiacal_releasing",
        zr_mode="predictive",
        zr_axis_key="vue_complete",
    )
    payload = interpretation_service._build_user_payload(chart, request)
    assert "natal_focal_data" not in payload
    prompt = interpretation_service._build_system_prompt(request)
    assert "AXE : Vue complète" in prompt


def test_specialized_system_prompts_are_distinct_per_reading_type():
    prompts = {
        rtype: interpretation_service._build_system_prompt(schemas.ReadingRequest(reading_type=rtype))
        for rtype in ["global", "lots", "derived_houses", "timing", "zodiacal_releasing", "compatibility"]
    }
    assert len(set(prompts.values())) == 6  # les 6 prompts doivent différer
    assert "LOTS" in prompts["lots"]
    assert "MAISONS DÉRIVÉES" in prompts["derived_houses"]
    assert "PRONOSTIC" in prompts["timing"]
    assert "RÉPARTITION ZODIACALE" in prompts["zodiacal_releasing"]
    assert "COMPATIBILITÉ" in prompts["compatibility"]


def test_system_prompt_maps_language_code_to_full_name():
    fr_prompt = interpretation_service._build_system_prompt(schemas.ReadingRequest(reading_type="global", language="fr"))
    en_prompt = interpretation_service._build_system_prompt(schemas.ReadingRequest(reading_type="global", language="en"))
    es_prompt = interpretation_service._build_system_prompt(schemas.ReadingRequest(reading_type="global", language="es"))
    assert "en français" in fr_prompt
    assert "en anglais (English)" in en_prompt
    assert "en espagnol (español)" in es_prompt


def test_compatibility_reading_payload_includes_both_persons_and_synastry_data():
    chart_a = _make_chart()
    chart_b = _make_chart_b()
    request = schemas.ReadingRequest(reading_type="compatibility", relationship_mode="romantic", chart_b_id="chart-b")
    payload = interpretation_service._build_user_payload(chart_a, request, chart_b=chart_b)

    assert payload["relationship_mode"] == "romantic"
    assert payload["person_b"]["name"] == "Partenaire"
    assert "identity" in payload["person_a"]
    assert "identity" in payload["person_b"]
    assert len(payload["inter_aspects"]) > 0
    assert "a_planets_in_b_houses" in payload["house_overlay"]
    assert "Sun" in payload["composite_chart"]["points"]
    assert payload["charts_time_known"] == {"chart_a": True, "chart_b": True}
    assert "houses_meanings" in payload["reference"]


def test_compatibility_reading_payload_defaults_to_romantic_mode():
    chart_a = _make_chart()
    chart_b = _make_chart_b()
    request = schemas.ReadingRequest(reading_type="compatibility", chart_b_id="chart-b")
    payload = interpretation_service._build_user_payload(chart_a, request, chart_b=chart_b)
    assert payload["relationship_mode"] == "romantic"


def test_compatibility_prompt_mentions_the_chosen_relationship_mode():
    request = schemas.ReadingRequest(reading_type="compatibility", relationship_mode="professional")
    prompt = interpretation_service._build_system_prompt(request)
    assert "relation professionnelle" in prompt
    assert "romantique" not in prompt


def test_compatibility_prompt_forbids_closed_relationship_verdicts():
    request = schemas.ReadingRequest(reading_type="compatibility", relationship_mode="romantic")
    prompt = interpretation_service._build_system_prompt(request)
    assert "verdict fermé" in prompt
    assert "recommandations" in prompt.lower()


def test_compatibility_prompt_lists_rating_axes_for_the_chosen_mode():
    romantic_prompt = interpretation_service._build_system_prompt(
        schemas.ReadingRequest(reading_type="compatibility", relationship_mode="romantic")
    )
    professional_prompt = interpretation_service._build_system_prompt(
        schemas.ReadingRequest(reading_type="compatibility", relationship_mode="professional")
    )
    assert "passion_alchimie" in romantic_prompt
    assert "engagement_duree" in romantic_prompt
    assert "communication_pro" not in romantic_prompt

    assert "communication_pro" in professional_prompt
    assert "rigueur_fiabilite" in professional_prompt
    assert "passion_alchimie" not in professional_prompt


# ---------------------------------------------------------------------------
# Notation chiffrée de compatibilité : extraction/validation du bloc JSON final.
# ---------------------------------------------------------------------------
def test_extract_compatibility_ratings_parses_trailing_json_block():
    text = """## Vue d'ensemble
Une belle dynamique.

```json
{"compatibility_ratings": {"passion_alchimie": {"score": 8, "justification": "Vénus-Mars en trigone serré."}}}
```"""
    cleaned, ratings = interpretation_service._extract_compatibility_ratings(text)
    assert "```json" not in cleaned
    assert "Une belle dynamique." in cleaned
    assert ratings == {"passion_alchimie": {"score": 8, "justification": "Vénus-Mars en trigone serré."}}


def test_extract_compatibility_ratings_returns_none_when_no_block():
    text = "Une lecture sans bloc de notation."
    cleaned, ratings = interpretation_service._extract_compatibility_ratings(text)
    assert cleaned == text
    assert ratings is None


def test_extract_compatibility_ratings_returns_none_for_malformed_json():
    text = """Texte.

```json
{"compatibility_ratings": {"passion_alchimie": }}
```"""
    cleaned, ratings = interpretation_service._extract_compatibility_ratings(text)
    assert cleaned == text
    assert ratings is None


def test_sanitize_compatibility_ratings_drops_unknown_keys_and_invalid_scores():
    raw = {
        "passion_alchimie": {"score": 8, "justification": "ok"},
        "unknown_axis": {"score": 5, "justification": "should be dropped"},
        "complicite_emotionnelle": {"score": 15, "justification": "out of range"},
        "engagement_duree": {"score": "sept", "justification": "not an int"},
    }
    sanitized = interpretation_service._sanitize_compatibility_ratings(raw, "romantic")
    assert sanitized == {"passion_alchimie": {"score": 8, "justification": "ok"}}


def test_sanitize_compatibility_ratings_returns_none_for_empty_or_none_input():
    assert interpretation_service._sanitize_compatibility_ratings(None, "romantic") is None
    assert interpretation_service._sanitize_compatibility_ratings({}, "romantic") is None


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
    # Certains modèles refusent le préremplissage (la conversation ne peut pas se terminer par
    # un tour "assistant") : le texte partiel est repassé en tour "assistant" suivi d'un tour
    # "user" demandant de continuer, pour que le deuxième appel se termine bien par "user".
    second_call_messages = fake_client.messages.calls[1]["messages"]
    assert second_call_messages[-2] == {"role": "assistant", "content": "Première partie de la lecture, coupée en pl"}
    assert second_call_messages[-1]["role"] == "user"
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


def test_generate_reading_extracts_compatibility_ratings_and_strips_json_block(monkeypatch):
    chart_a = _make_chart()
    chart_b = _make_chart_b()
    request = schemas.ReadingRequest(reading_type="compatibility", relationship_mode="romantic", chart_b_id="chart-b")

    reading_body = "## Vue d'ensemble\nUne belle dynamique entre vous deux."
    json_block = (
        '```json\n{"compatibility_ratings": {'
        '"passion_alchimie": {"score": 8, "justification": "Vénus-Mars en trigone serré."}, '
        '"complicite_emotionnelle": {"score": 6, "justification": "Lune en sextile."}'
        "}}\n```"
    )
    fake_client = _FakeAnthropicClient([_FakeResponse(f"{reading_body}\n\n{json_block}", stop_reason="end_turn")])
    monkeypatch.setattr(interpretation_service, "get_settings", _settings_with_key)
    monkeypatch.setattr(interpretation_service, "AsyncAnthropic", lambda api_key: fake_client)

    result = asyncio.run(interpretation_service.generate_reading(chart_a, request, chart_b=chart_b))

    assert "```json" not in result["reading_text"]
    assert "Une belle dynamique" in result["reading_text"]
    assert result["compatibility_ratings"] == {
        "passion_alchimie": {"score": 8, "justification": "Vénus-Mars en trigone serré."},
        "complicite_emotionnelle": {"score": 6, "justification": "Lune en sextile."},
    }


def test_generate_reading_compatibility_ratings_none_for_other_reading_types(monkeypatch):
    chart = _make_chart()
    request = schemas.ReadingRequest(reading_type="global", focus_areas=["general"])

    fake_client = _FakeAnthropicClient([_FakeResponse("Lecture générale sans notation.", stop_reason="end_turn")])
    monkeypatch.setattr(interpretation_service, "get_settings", _settings_with_key)
    monkeypatch.setattr(interpretation_service, "AsyncAnthropic", lambda api_key: fake_client)

    result = asyncio.run(interpretation_service.generate_reading(chart, request))
    assert result["compatibility_ratings"] is None
    assert result["timing_ratings"] is None


def test_generate_reading_extracts_timing_ratings_and_strips_json_block(monkeypatch):
    chart = _make_chart()
    request = schemas.ReadingRequest(reading_type="timing", timing_horizon="week")

    reading_body = "## Tendance de la semaine\nUne semaine plutôt active."
    json_block = (
        '```json\n{"timing_ratings": {'
        '"amour": {"score": 7, "justification": "Vénus en trigone avec le Soleil natal."}, '
        '"sante": {"score": 5, "justification": "Aucun transit marquant sur ce plan."}'
        "}}\n```"
    )
    fake_client = _FakeAnthropicClient([_FakeResponse(f"{reading_body}\n\n{json_block}", stop_reason="end_turn")])
    monkeypatch.setattr(interpretation_service, "get_settings", _settings_with_key)
    monkeypatch.setattr(interpretation_service, "AsyncAnthropic", lambda api_key: fake_client)

    result = asyncio.run(interpretation_service.generate_reading(chart, request))

    assert "```json" not in result["reading_text"]
    assert "Une semaine plutôt active" in result["reading_text"]
    assert result["compatibility_ratings"] is None
    assert result["timing_ratings"] == {
        "amour": {"score": 7, "justification": "Vénus en trigone avec le Soleil natal."},
        "sante": {"score": 5, "justification": "Aucun transit marquant sur ce plan."},
    }


def test_basic_reading_types_include_focus_zone_section():
    request = schemas.ReadingRequest(reading_type="love", focus_areas=["love"])
    prompt = interpretation_service._build_system_prompt(request)
    assert "ZONES À COUVRIR" in prompt


def test_specialized_reading_types_omit_focus_zone_section():
    request = schemas.ReadingRequest(reading_type="lots")
    prompt = interpretation_service._build_system_prompt(request)
    assert "ZONES À COUVRIR" not in prompt


def test_astrocartography_forecast_prompt_is_distinct_and_transit_framed():
    request = schemas.ReadingRequest(reading_type="astrocartography_forecast")
    prompt = interpretation_service._build_system_prompt(request)
    astro_prompt = interpretation_service._build_system_prompt(schemas.ReadingRequest(reading_type="astrocartography"))
    assert prompt != astro_prompt
    assert "PRÉVISION CYCLOCARTOGRAPHIQUE PLURIANNUELLE" in prompt
    assert "TRANSIT" in prompt


def test_astrocartography_forecast_payload_includes_reduced_windows():
    chart = _make_chart()
    request = schemas.ReadingRequest(
        reading_type="astrocartography_forecast",
        astro_focus_latitude=48.8566,
        astro_focus_longitude=2.3522,
        astro_focus_label="Paris",
        forecast_start_date=date(2024, 1, 1),
        forecast_years=10,
        forecast_threshold_km=300,
    )
    payload = interpretation_service._build_user_payload(chart, request)

    assert payload["focus_location"] == {"label": "Paris", "latitude": 48.8566, "longitude": 2.3522}
    assert payload["forecast_period"]["years"] == 10
    assert payload["total_windows_found"] >= len(payload["forecast_windows"])
    assert len(payload["forecast_windows"]) <= 25
    # Fenêtres re-triées chronologiquement pour la lecture (pas par proximité).
    starts = [w["start_date"] for w in payload["forecast_windows"]]
    assert starts == sorted(starts)
    for window in payload["forecast_windows"]:
        assert "meaning" in window and window["planet"] and window["line_type"]


def test_astrocartography_forecast_payload_defaults_focus_to_birthplace():
    chart = _make_chart()
    request = schemas.ReadingRequest(reading_type="astrocartography_forecast", forecast_years=1)
    payload = interpretation_service._build_user_payload(chart, request)
    assert payload["focus_location"]["label"] == chart.birth_city


def test_select_significant_forecast_windows_keeps_closest_and_sorts_chronologically():
    windows = [
        {"planet": "Sun", "line_type": "MC", "start_date": date(2030, 1, 1), "peak_distance_km": 500},
        {"planet": "Venus", "line_type": "MC", "start_date": date(2025, 1, 1), "peak_distance_km": 10},
        {"planet": "Mars", "line_type": "MC", "start_date": date(2027, 1, 1), "peak_distance_km": 50},
    ]
    selected = interpretation_service._select_significant_forecast_windows(windows, max_count=2)
    assert [w["planet"] for w in selected] == ["Venus", "Mars"]  # les 2 plus proches
    assert [w["start_date"] for w in selected] == sorted(w["start_date"] for w in selected)


def test_all_reading_type_payloads_are_strictly_json_serializable():
    """request_payload est stocké dans une colonne JSON (SavedReading, SQLAlchemy/SQLite) avec le
    sérialiseur JSON par défaut (pas de `default=str`) : tout objet non nativement sérialisable
    (ex. `datetime.date`) glissé dans le payload par une branche de _build_user_payload ferait
    échouer db.commit() APRÈS l'appel LLM déjà payé, au lieu d'une erreur propre en amont — c'est
    exactement le bug qui affectait 'astrocartography_forecast' (dates non converties en ISO).
    Ce test couvre tous les types de lecture avec des dates fournies là où c'est pertinent, pour
    empêcher toute régression de ce genre à l'avenir."""
    chart = _make_chart()
    chart_b = _make_chart_b()
    requests_by_type = [
        (schemas.ReadingRequest(reading_type="global", focus_areas=["general"]), None),
        (schemas.ReadingRequest(reading_type="lots"), None),
        (schemas.ReadingRequest(reading_type="derived_houses"), None),
        (schemas.ReadingRequest(reading_type="timing", as_of_date=date(2026, 1, 1)), None),
        (schemas.ReadingRequest(reading_type="zodiacal_releasing", as_of_date=date(2026, 1, 1)), None),
        (
            schemas.ReadingRequest(reading_type="compatibility", chart_b_id=chart_b.id, relationship_mode="romantic"),
            chart_b,
        ),
        (schemas.ReadingRequest(reading_type="astrocartography", astro_map_mode="natal"), None),
        (
            schemas.ReadingRequest(reading_type="astrocartography", astro_map_mode="transit", as_of_date=date(2026, 1, 1)),
            None,
        ),
        (
            schemas.ReadingRequest(
                reading_type="astrocartography_forecast",
                astro_focus_latitude=48.8566,
                astro_focus_longitude=2.3522,
                forecast_start_date=date(2024, 1, 1),
                forecast_years=5,
            ),
            None,
        ),
        (schemas.ReadingRequest(reading_type="witchy_calendar", witchy_calendar_year=2027), None),
        (schemas.ReadingRequest(reading_type="witchy_day_detail", witchy_day_detail_date=date(2027, 1, 22)), None),
    ]
    for request, cb in requests_by_type:
        payload = interpretation_service._build_user_payload(chart, request, chart_b=cb)
        try:
            json.dumps(payload)  # pas de default=str : mêmes contraintes qu'une colonne JSON SQLAlchemy
        except TypeError as exc:
            raise AssertionError(f"payload non JSON-sérialisable pour reading_type={request.reading_type!r} : {exc}")
