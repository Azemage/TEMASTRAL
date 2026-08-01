from app.core.aspects import BodyForAspect, angular_separation, compute_aspects

DEFAULT_ORBS = {
    "conjunction": 8, "opposition": 8, "square": 7, "trine": 7, "sextile": 5,
    "semi_sextile": 2, "semi_square": 2, "sesquiquadrate": 2, "quincunx": 3, "quintile": 2,
}


def test_angular_separation_handles_wraparound():
    assert angular_separation(10, 350) == 20
    assert angular_separation(0, 180) == 180
    assert angular_separation(45, 45) == 0


def test_compute_aspects_detects_exact_trine():
    bodies = [
        BodyForAspect(name="Sun", longitude=0, speed_longitude=1.0),
        BodyForAspect(name="Moon", longitude=120, speed_longitude=13.0),
    ]
    aspects = compute_aspects(bodies, DEFAULT_ORBS, include_minor=False)
    assert len(aspects) == 1
    assert aspects[0]["type"] == "trine"
    assert aspects[0]["orb"] == 0


def test_compute_aspects_respects_orb_limit():
    bodies = [
        BodyForAspect(name="Sun", longitude=0, speed_longitude=1.0),
        BodyForAspect(name="Saturn", longitude=100, speed_longitude=0.03),  # 100° : hors orbe carré (7°) et trigone (7°)
    ]
    aspects = compute_aspects(bodies, DEFAULT_ORBS, include_minor=False)
    assert aspects == []


def test_compute_aspects_picks_closest_aspect_when_ambiguous():
    # 88° est à la fois hors-orbe conjonction/trigone mais dans l'orbe du carré (7°)
    bodies = [
        BodyForAspect(name="Sun", longitude=0, speed_longitude=1.0),
        BodyForAspect(name="Mars", longitude=88, speed_longitude=0.5),
    ]
    aspects = compute_aspects(bodies, DEFAULT_ORBS, include_minor=False)
    assert len(aspects) == 1
    assert aspects[0]["type"] == "square"


def test_applying_vs_separating():
    # Séparation Saturne-Soleil = 121° (1° au-delà du trigone à 120°). Le Soleil avance plus
    # vite que Saturne, donc l'écart Saturne-Soleil diminue avec le temps : il se rapproche
    # de 120° -> aspect applicatif.
    bodies_applying = [
        BodyForAspect(name="Sun", longitude=0, speed_longitude=1.0),
        BodyForAspect(name="Saturn", longitude=121, speed_longitude=0.03),
    ]
    aspects = compute_aspects(bodies_applying, DEFAULT_ORBS, include_minor=False)
    assert aspects[0]["applying"] is True

    # Ici l'écart est déjà passé sous 120° (119°) : il continue de diminuer, donc s'éloigne
    # de l'exactitude de l'aspect -> séparatif.
    bodies_separating = [
        BodyForAspect(name="Sun", longitude=0, speed_longitude=1.0),
        BodyForAspect(name="Saturn", longitude=119, speed_longitude=0.03),
    ]
    aspects_sep = compute_aspects(bodies_separating, DEFAULT_ORBS, include_minor=False)
    assert aspects_sep[0]["applying"] is False
