from app.core.spiritual_gifts import compute_spiritual_gifts_signals


def _planet(name, sign, house):
    return {"name": name, "sign": sign, "house": house}


def _aspect(planet1, planet2, aspect_type):
    return {"planet1": planet1, "planet2": planet2, "type": aspect_type, "orb": 1.0}


def _chart(planets, aspects):
    return {"planets": planets, "aspects": aspects}


def test_key_house_occupants_grouped_correctly():
    chart = _chart(
        [
            _planet("Sun", "Leo", 5),
            _planet("Moon", "Cancer", 4),
            _planet("Pluto", "Scorpio", 8),
            _planet("Neptune", "Pisces", 12),
            _planet("Venus", "Pisces", 12),
        ],
        [],
    )
    signals = compute_spiritual_gifts_signals(chart)
    assert signals["key_house_occupants"] == {
        4: ["Moon"],
        8: ["Pluto"],
        12: ["Neptune", "Venus"],
    }


def test_documented_aspect_detected_regardless_of_order():
    chart = _chart(
        [_planet("Moon", "Cancer", 1), _planet("Neptune", "Pisces", 5)],
        [_aspect("Neptune", "Moon", "trine")],  # ordre inversé par rapport à la table de référence
    )
    signals = compute_spiritual_gifts_signals(chart)
    assert len(signals["documented_aspects_present"]) == 1
    assert signals["documented_aspects_present"][0]["gift_type"] == "perception"


def test_undocumented_aspect_pair_not_included():
    chart = _chart(
        [_planet("Venus", "Taurus", 2), _planet("Mars", "Aries", 1)],
        [_aspect("Venus", "Mars", "trine")],
    )
    signals = compute_spiritual_gifts_signals(chart)
    assert signals["documented_aspects_present"] == []


def test_water_stellium_requires_at_least_three_classic_planets():
    two_water = _chart(
        [_planet("Moon", "Cancer", 1), _planet("Neptune", "Pisces", 5), _planet("Sun", "Leo", 6)], []
    )
    assert compute_spiritual_gifts_signals(two_water)["has_water_stellium"] is False

    three_water = _chart(
        [_planet("Moon", "Cancer", 1), _planet("Neptune", "Pisces", 5), _planet("Pluto", "Scorpio", 8)], []
    )
    assert compute_spiritual_gifts_signals(three_water)["has_water_stellium"] is True


def test_water_grand_trine_requires_all_three_mutual_trines():
    planets = [_planet("Moon", "Cancer", 1), _planet("Neptune", "Pisces", 5), _planet("Pluto", "Scorpio", 8)]
    complete = _chart(
        planets,
        [_aspect("Moon", "Neptune", "trine"), _aspect("Neptune", "Pluto", "trine"), _aspect("Moon", "Pluto", "trine")],
    )
    assert compute_spiritual_gifts_signals(complete)["water_grand_trine"] is not None

    incomplete = _chart(planets, [_aspect("Moon", "Neptune", "trine"), _aspect("Neptune", "Pluto", "trine")])
    assert compute_spiritual_gifts_signals(incomplete)["water_grand_trine"] is None


def test_notable_asteroids_only_included_when_present_in_chart():
    chart = _chart([_planet("lilith_mean", "Scorpio", 8)], [])
    signals = compute_spiritual_gifts_signals(chart)
    assert signals["notable_asteroids"] == {"lilith_mean": {"sign": "Scorpio", "house": 8}}


def test_south_node_included_only_when_present():
    with_node = _chart([_planet("south_node", "Leo", 5)], [])
    assert compute_spiritual_gifts_signals(with_node)["south_node_sign_house"] == {"sign": "Leo", "house": 5}

    without_node = _chart([_planet("Sun", "Leo", 5)], [])
    assert compute_spiritual_gifts_signals(without_node)["south_node_sign_house"] is None
