from app.core.dispositors import compute_dispositors


def test_self_disposed_planet():
    result = compute_dispositors({"Sun": "Leo"}, "traditional")
    assert result["dispositors"][0]["self_disposed"] is True
    assert result["dispositor_chains"][0]["final_dispositor"] == "Sun"
    assert result["dispositor_chains"][0]["type"] == "linear"


def test_linear_chain_to_final_dispositor():
    planet_signs = {"Moon": "Taurus", "Venus": "Leo", "Sun": "Leo"}
    result = compute_dispositors(planet_signs, "traditional")
    chains = {c["chain"][0]: c for c in result["dispositor_chains"]}

    assert chains["Moon"]["chain"] == ["Moon", "Venus", "Sun"]
    assert chains["Moon"]["final_dispositor"] == "Sun"
    assert chains["Moon"]["type"] == "linear"


def test_mutual_reception_and_loop_detection():
    # Mercure en Capricorne (maître trad. Saturne) / Saturne en Gémeaux (maître trad. Mercure)
    planet_signs = {"Mercury": "Capricorn", "Saturn": "Gemini"}
    result = compute_dispositors(planet_signs, "traditional")

    assert len(result["mutual_receptions"]) == 1
    reception = result["mutual_receptions"][0]
    assert set(reception["planets"]) == {"Mercury", "Saturn"}

    mercury_chain = next(c for c in result["dispositor_chains"] if c["chain"][0] == "Mercury")
    assert mercury_chain["type"] == "loop"
    assert mercury_chain["final_dispositor"] is None


def test_traditional_vs_modern_rulership_differs_for_scorpio():
    planet_signs = {"Pluto": "Scorpio"}
    traditional = compute_dispositors(planet_signs, "traditional")
    modern = compute_dispositors(planet_signs, "modern")

    assert traditional["dispositors"][0]["self_disposed"] is False  # maître trad. de Scorpion = Mars
    assert modern["dispositors"][0]["self_disposed"] is True  # maître moderne de Scorpion = Pluton
