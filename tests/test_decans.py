from app.core.decans import analyze_decan, decan_breakdown_for_sign, decan_number, decan_ruler


def test_decan_number_boundaries():
    assert decan_number(0) == 1
    assert decan_number(9.99) == 1
    assert decan_number(10) == 2
    assert decan_number(19.99) == 2
    assert decan_number(20) == 3
    assert decan_number(29.99) == 3


def test_decan_ruler_aries_starts_with_its_own_ruler():
    # Convention chaldéenne : le 1er décan d'un signe cardinal de feu commence par son propre
    # maître (Mars pour le Bélier), puis continue le cycle chaldéen (Soleil, Vénus...).
    assert decan_ruler("Aries", 0) == "Mars"
    assert decan_ruler("Aries", 15) == "Sun"
    assert decan_ruler("Aries", 25) == "Venus"


def test_decan_ruler_cycle_continues_across_signs():
    # Le cycle chaldéen (Mars, Soleil, Vénus, Mercure, Lune, Saturne, Jupiter) continue sans
    # interruption d'un signe à l'autre : le 1er décan du Taureau suit le 3e décan du Bélier.
    assert decan_ruler("Taurus", 0) == "Mercury"
    assert decan_ruler("Taurus", 15) == "Moon"
    assert decan_ruler("Taurus", 25) == "Saturn"
    assert decan_ruler("Gemini", 0) == "Jupiter"


def test_analyze_decan_returns_number_and_ruler():
    result = analyze_decan("Leo", 12.5)
    assert result == {"decan_number": 2, "decan_ruler": "Jupiter"}


def test_decan_breakdown_for_sign_covers_full_thirty_degrees():
    breakdown = decan_breakdown_for_sign("Scorpio")
    assert len(breakdown) == 3
    assert [d["ruler"] for d in breakdown] == ["Mars", "Sun", "Venus"]
    assert breakdown[0] == {"decan_number": 1, "ruler": "Mars", "start_degree": 0, "end_degree": 10}
    assert breakdown[2] == {"decan_number": 3, "ruler": "Venus", "start_degree": 20, "end_degree": 30}


def test_every_sign_has_three_decan_rulers():
    from app.core.zodiac import SIGNS

    for sign in SIGNS:
        breakdown = decan_breakdown_for_sign(sign)
        assert len(breakdown) == 3
        assert all(d["ruler"] for d in breakdown)
