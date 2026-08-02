from app.core.traits import compute_character_traits

BASE_ELEMENTS = {"fire": 5, "earth": 1, "air": 2, "water": 2}
BASE_MODALITIES = {"cardinal": 6, "fixed": 2, "mutable": 2}


def _planet(name: str, sign: str, house: int) -> dict:
    return {"name": name, "sign": sign, "sign_fr": sign, "house": house}


def _make_planets(overrides: dict[str, tuple[str, int]] | None = None) -> list[dict]:
    """10 planètes classiques, toutes en Bélier maison 1 par défaut, sauf `overrides`
    (planet_name -> (sign, house))."""
    overrides = overrides or {}
    names = ["Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto"]
    return [_planet(name, *overrides.get(name, ("Aries", 1))) for name in names]


def test_traits_combine_all_personal_and_social_planets():
    planets = _make_planets(
        {
            "Sun": ("Aries", 10),
            "Moon": ("Cancer", 4),
            "Mercury": ("Gemini", 3),
            "Venus": ("Libra", 7),
            "Mars": ("Scorpio", 8),
            "Jupiter": ("Sagittarius", 9),
            "Saturn": ("Capricorn", 10),
        }
    )
    result = compute_character_traits(
        planets=planets,
        ascendant_sign="Libra",
        elements_balance=BASE_ELEMENTS,
        modality_balance=BASE_MODALITIES,
    )

    assert "fonceur" in result["keywords"]  # Soleil en Bélier
    assert "hypersensible" in result["keywords"]  # Lune en Cancer
    assert "diplomate" in result["keywords"]  # Ascendant Balance
    assert "entreprenant" in [t.lower() for t in result["keywords"]]  # modalité dominante : cardinal
    # 5 personnels + ascendant + 2 sociaux + 2 dominantes = 10 sources
    assert len(result["sources"]) == 10
    assert {s["origin"] for s in result["sources"]} == {
        "ascendant", "sun", "moon", "mercury", "venus", "mars", "jupiter", "saturn",
        "dominant_element", "dominant_modality",
    }


def test_house_context_attached_to_personal_and_social_planets():
    planets = _make_planets({"Sun": ("Aries", 10)})
    result = compute_character_traits(
        planets=planets, ascendant_sign="Aries", elements_balance=BASE_ELEMENTS, modality_balance=BASE_MODALITIES
    )
    sun_source = next(s for s in result["sources"] if s["origin"] == "sun")
    assert sun_source["house"] == 10
    assert "carrière" in sun_source["house_context"]

    ascendant_source = next(s for s in result["sources"] if s["origin"] == "ascendant")
    assert ascendant_source["house"] is None
    assert ascendant_source["house_context"] is None


def test_generational_planets_excluded_from_tag_cloud_but_listed_separately():
    planets = _make_planets({"Uranus": ("Aquarius", 11), "Neptune": ("Pisces", 12), "Pluto": ("Scorpio", 8)})
    result = compute_character_traits(
        planets=planets, ascendant_sign="Aries", elements_balance=BASE_ELEMENTS, modality_balance=BASE_MODALITIES
    )
    assert {s["origin"] for s in result["sources"]}.isdisjoint({"uranus", "neptune", "pluto"})
    assert len(result["generational_placements"]) == 3
    placements = {p["planet"]: p for p in result["generational_placements"]}
    assert placements["Uranus"]["sign"] == "Aquarius"
    assert placements["Uranus"]["house"] == 11
    assert placements["Uranus"]["note"]  # phrase non vide issue de planets_in_houses_full.json


def test_dominant_traits_flagged_when_tag_repeats_across_sources():
    # Soleil et Ascendant dans le même signe : leurs listes de tags partagent des mots.
    planets = _make_planets({"Sun": ("Leo", 5)})
    result = compute_character_traits(
        planets=planets, ascendant_sign="Leo", elements_balance=BASE_ELEMENTS, modality_balance=BASE_MODALITIES
    )
    assert "charismatique" in result["dominant_traits"]
    assert result["keywords"].count("charismatique") == 1  # dédupliqué malgré la répétition


def test_dominant_balance_tie_break_is_deterministic():
    planets = _make_planets()
    result = compute_character_traits(
        planets=planets,
        ascendant_sign="Gemini",
        elements_balance={"fire": 3, "earth": 3, "air": 3, "water": 3},
        modality_balance={"cardinal": 3, "fixed": 3, "mutable": 3},
    )
    element_source = next(s for s in result["sources"] if s["origin"] == "dominant_element")
    modality_source = next(s for s in result["sources"] if s["origin"] == "dominant_modality")
    assert element_source["label"] == "fire"
    assert modality_source["label"] == "cardinal"
