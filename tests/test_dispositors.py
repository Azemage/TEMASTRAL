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


def test_strong_convergence_when_all_chains_end_at_same_dispositor():
    # Sun (Leo, auto-disposé), Moon/Mercury/Venus toutes en Lion -> maître Soleil.
    planet_signs = {"Sun": "Leo", "Moon": "Leo", "Mercury": "Leo", "Venus": "Leo"}
    result = compute_dispositors(planet_signs, "traditional")
    convergence = result["convergence"]

    assert convergence["dominant_dispositor"] == "Sun"
    assert convergence["dominant_count"] == 4
    assert convergence["total_chains"] == 4
    assert convergence["convergence_ratio"] == 1.0
    assert convergence["level"] == "forte"


def test_notable_but_not_strong_convergence():
    # Soleil, Mercure et Vénus convergent vers Soleil (3/5, sous le seuil "forte" de 80%).
    planet_signs = {"Sun": "Leo", "Mercury": "Leo", "Venus": "Leo", "Moon": "Cancer", "Mars": "Aries"}
    result = compute_dispositors(planet_signs, "traditional")
    convergence = result["convergence"]

    assert convergence["dominant_dispositor"] == "Sun"
    assert convergence["total_chains"] == 5
    assert convergence["dominant_count"] == 3
    assert convergence["convergence_ratio"] == 0.6
    assert convergence["level"] == "notable"


def test_no_convergence_when_dispositors_are_evenly_split():
    # Soleil+Mercure convergent vers Soleil (2/5), Vénus+Mars vers Mars (2/5) : aucune planète
    # ne domine (40% chacune, sous le seuil "notable" de 50%).
    planet_signs = {"Sun": "Leo", "Mercury": "Leo", "Venus": "Aries", "Mars": "Aries", "Moon": "Cancer"}
    result = compute_dispositors(planet_signs, "traditional")
    convergence = result["convergence"]

    assert convergence["total_chains"] == 5
    assert convergence["dominant_count"] == 2
    assert convergence["level"] == "aucune"


def test_no_convergence_when_no_final_dispositor_available():
    # Uniquement des chaînes en boucle (aucun final_dispositor) -> pas de convergence.
    planet_signs = {"Mercury": "Capricorn", "Saturn": "Gemini"}
    result = compute_dispositors(planet_signs, "traditional")
    convergence = result["convergence"]

    assert convergence["dominant_dispositor"] is None
    assert convergence["level"] == "aucune"
