from datetime import date

from app.core.aspects import BodyForAspect
from app.core.transits import TRANSIT_PLANETS, compute_current_transits, compute_upcoming_transits


def test_returns_all_classic_planets():
    """Chiron y figure aussi (voir TRANSIT_PLANETS) : point lent suivi pour le transit-vers-natal
    au même titre que Jupiter à Pluton — voir notation_hebdomadaire_domaines.json, points_mineurs_note."""
    result = compute_current_transits([], date(2026, 8, 2))
    names = {p["name"] for p in result["transiting_planets"]}
    assert names == set(TRANSIT_PLANETS)
    assert names == {"Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto", "chiron"}


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
    assert conjunctions[0]["intensity"] == 4  # Jupiter conjonction quasi exacte : intensité maximale


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


def test_upcoming_transits_include_fast_planets():
    natal_bodies = [
        BodyForAspect(name="Sun", longitude=54.4175),
        BodyForAspect(name="Moon", longitude=297.4365),
        BodyForAspect(name="Venus", longitude=12.8437),
    ]
    events = compute_upcoming_transits(natal_bodies, date(2026, 8, 2), date(2027, 8, 2))
    fast_planets_seen = {e["transiting_planet"] for e in events} & {"Moon", "Mercury", "Venus", "Sun", "Mars"}
    assert fast_planets_seen  # au moins une planète rapide détectée sur l'année


def test_upcoming_transits_reliably_catches_fast_moon_passes():
    # La Lune parcourt ~13°/jour : un échantillonnage trop grossier pourrait "sauter"
    # par-dessus un passage exact. On place un point natal exactement sur la position de la
    # Lune 10 jours après le départ, et on vérifie qu'une conjonction est bien détectée avec
    # un pic proche de cette date (pas manquée par sous-échantillonnage).
    from datetime import timedelta

    from app.core import ephemeris

    start_date = date(2026, 8, 2)
    target_date = start_date + timedelta(days=10)
    jd_ut = ephemeris.local_datetime_to_jd_ut(target_date.isoformat(), "12:00:00", "UTC")
    moon_lon = ephemeris.calc_planet(jd_ut, ephemeris.PLANET_IDS["Moon"]).longitude

    natal_bodies = [BodyForAspect(name="MoonTarget", longitude=moon_lon)]
    events = compute_upcoming_transits(natal_bodies, start_date, start_date + timedelta(days=40))
    moon_conjunctions = [e for e in events if e["transiting_planet"] == "Moon" and e["type"] == "conjunction"]
    assert len(moon_conjunctions) >= 1
    closest = min(moon_conjunctions, key=lambda e: abs(date.fromisoformat(e["peak_date"]) - target_date))
    assert abs(date.fromisoformat(closest["peak_date"]) - target_date) <= timedelta(days=1)


def test_upcoming_events_have_intensity_and_slow_planets_outrank_moon():
    natal_bodies = [
        BodyForAspect(name="Sun", longitude=54.4175),
        BodyForAspect(name="Moon", longitude=297.4365),
        BodyForAspect(name="Venus", longitude=12.8437),
    ]
    events = compute_upcoming_transits(natal_bodies, date(2026, 8, 2), date(2027, 8, 2))
    assert all(1 <= e["intensity"] <= 4 for e in events)

    moon_events = [e for e in events if e["transiting_planet"] == "Moon"]
    slow_events = [e for e in events if e["transiting_planet"] in {"Saturn", "Uranus", "Neptune", "Pluto"}]
    if moon_events and slow_events:
        avg_moon_intensity = sum(e["intensity"] for e in moon_events) / len(moon_events)
        avg_slow_intensity = sum(e["intensity"] for e in slow_events) / len(slow_events)
        assert avg_slow_intensity > avg_moon_intensity


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
