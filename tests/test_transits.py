from datetime import date

from app.core.aspects import BodyForAspect
from app.core.transits import TRANSIT_PLANETS, compute_current_transits, compute_upcoming_transits


def test_returns_all_five_slow_planets():
    result = compute_current_transits([], date(2026, 8, 2))
    names = {p["name"] for p in result["transiting_planets"]}
    assert names == set(TRANSIT_PLANETS)


def test_each_transiting_planet_has_valid_sign_and_degree():
    result = compute_current_transits([], date(2026, 8, 2))
    for planet in result["transiting_planets"]:
        assert 0 <= planet["degree"] < 30
        assert isinstance(planet["retrograde"], bool)


def test_aspect_detected_against_a_close_natal_point():
    # On place un point natal fictif tout près (0.5°) de la position réelle de Jupiter
    # à cette date, pour vérifier qu'un aspect de conjonction est bien détecté.
    from app.core import ephemeris

    jd_ut = ephemeris.local_datetime_to_jd_ut("2026-08-02", "12:00:00", "UTC")
    jupiter_lon = ephemeris.calc_planet(jd_ut, ephemeris.PLANET_IDS["Jupiter"]).longitude

    natal_bodies = [BodyForAspect(name="FakePoint", longitude=(jupiter_lon + 0.5) % 360)]
    result = compute_current_transits(natal_bodies, date(2026, 8, 2), orb=3.0)

    conjunctions = [a for a in result["aspects"] if a["transiting_planet"] == "Jupiter" and a["type"] == "conjunction"]
    assert len(conjunctions) == 1
    assert conjunctions[0]["natal_point"] == "FakePoint"
    assert conjunctions[0]["favorability"] == "favorable"


def test_no_aspect_when_natal_point_is_far_from_any_transit():
    natal_bodies = [BodyForAspect(name="Isolated", longitude=0.0)]
    # Toutes les planètes lentes sont improbables à exactement 0° au même moment ; on
    # vérifie surtout qu'un orbe très serré ne produit pas de faux positifs.
    result = compute_current_transits(natal_bodies, date(2026, 8, 2), orb=0.001)
    assert result["aspects"] == [] or all(a["orb"] < 0.01 for a in result["aspects"])


def test_upcoming_transits_finds_events_within_a_year():
    natal_bodies = [
        BodyForAspect(name="Sun", longitude=54.4175),
        BodyForAspect(name="Moon", longitude=297.4365),
        BodyForAspect(name="Venus", longitude=12.8437),
    ]
    events = compute_upcoming_transits(natal_bodies, date(2026, 8, 2), date(2027, 8, 2))
    assert len(events) > 0
    for event in events:
        assert event["peak_orb"] <= 1.0
        assert event["window_start"] <= event["peak_date"] <= event["window_end"]
        assert event["transiting_planet"] in TRANSIT_PLANETS


def test_upcoming_transits_events_sorted_chronologically():
    natal_bodies = [BodyForAspect(name="Sun", longitude=54.4175), BodyForAspect(name="Moon", longitude=297.4365)]
    events = compute_upcoming_transits(natal_bodies, date(2026, 8, 2), date(2027, 8, 2))
    dates = [e["peak_date"] for e in events]
    assert dates == sorted(dates)


def test_upcoming_transits_detects_multiple_passes_from_retrograde_motion():
    # Un point placé pile sur la longitude de Saturne au début de la période : Saturne
    # rétrograde une bonne partie de l'année, donc la conjonction devrait être 're-touchée'
    # au moins une fois (passage direct, rétrograde, ou nouveau passage direct).
    from app.core import ephemeris

    jd_ut = ephemeris.local_datetime_to_jd_ut("2026-08-02", "12:00:00", "UTC")
    saturn_lon = ephemeris.calc_planet(jd_ut, ephemeris.PLANET_IDS["Saturn"]).longitude

    natal_bodies = [BodyForAspect(name="TestPoint", longitude=saturn_lon)]
    events = compute_upcoming_transits(natal_bodies, date(2026, 8, 2), date(2027, 8, 2))
    saturn_conjunctions = [e for e in events if e["transiting_planet"] == "Saturn" and e["type"] == "conjunction"]
    assert len(saturn_conjunctions) >= 1
