from app.core.traits import compute_character_traits


def test_traits_combine_sun_moon_ascendant_and_dominant_balances():
    result = compute_character_traits(
        sun_sign="Aries",
        moon_sign="Cancer",
        ascendant_sign="Libra",
        elements_balance={"fire": 5, "earth": 1, "air": 2, "water": 2},
        modality_balance={"cardinal": 6, "fixed": 2, "mutable": 2},
    )

    assert result["keywords"][:2] == ["Énergique", "Impulsif"]  # traits du Soleil en premier
    assert "Sensible" in result["keywords"]  # Lune en Cancer
    assert "Diplomate" in result["keywords"]  # Ascendant Balance
    assert "Spontané" in result["keywords"]  # élément dominant : feu
    assert "Entreprenant" in result["keywords"]  # modalité dominante : cardinal
    assert len(result["sources"]) == 5


def test_traits_deduplicated_when_same_sign_repeats():
    # Soleil et Ascendant dans le même signe : les traits ne doivent apparaître qu'une fois.
    result = compute_character_traits(
        sun_sign="Leo",
        moon_sign="Leo",
        ascendant_sign="Leo",
        elements_balance={"fire": 10, "earth": 0, "air": 0, "water": 0},
        modality_balance={"cardinal": 0, "fixed": 10, "mutable": 0},
    )
    assert result["keywords"].count("Généreux") == 1
    assert result["keywords"].count("Charismatique") == 1


def test_dominant_balance_tie_break_is_deterministic():
    # Égalité parfaite entre tous les éléments -> le feu (premier de la priorité) l'emporte.
    result = compute_character_traits(
        sun_sign="Gemini",
        moon_sign="Gemini",
        ascendant_sign="Gemini",
        elements_balance={"fire": 3, "earth": 3, "air": 3, "water": 3},
        modality_balance={"cardinal": 3, "fixed": 3, "mutable": 3},
    )
    element_source = next(s for s in result["sources"] if s["origin"] == "dominant_element")
    modality_source = next(s for s in result["sources"] if s["origin"] == "dominant_modality")
    assert element_source["label"] == "fire"
    assert modality_source["label"] == "cardinal"
