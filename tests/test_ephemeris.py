"""app/core/ephemeris.py : chemin d'éphémérides pour Chiron/astéroïdes (seas_18.se1) et sa
robustesse multi-thread (voir _ensure_ephe_path_for_this_thread)."""

import threading

import swisseph as swe

from app.core import ephemeris


def test_chiron_calc_works_without_error():
    jd = swe.julday(2026, 8, 25, 12.0)
    position = ephemeris.calc_planet(jd, ephemeris.PLANET_IDS["chiron"])
    assert 0 <= position.longitude < 360


def test_asteroid_calc_works_without_error():
    jd = swe.julday(2026, 8, 25, 12.0)
    for name in ("ceres", "pallas", "juno", "vesta"):
        position = ephemeris.calc_planet(jd, ephemeris.PLANET_IDS[name])
        assert 0 <= position.longitude < 360


def test_chiron_calc_works_from_a_background_thread():
    """Régression : swe.set_ephe_path est THREAD-LOCAL dans pyswisseph — un appel fait
    uniquement au chargement du module (thread principal) ne suffit pas pour les threads du
    pool utilisés par FastAPI (run_in_threadpool). calc_planet doit se repositionner lui-même
    dans chaque thread (_ensure_ephe_path_for_this_thread), sinon Chiron/les astéroïdes échouent
    silencieusement dès qu'une requête HTTP réelle les calcule."""
    jd = swe.julday(2026, 8, 25, 12.0)
    result = {}

    def worker():
        try:
            result["longitude"] = ephemeris.calc_planet(jd, ephemeris.PLANET_IDS["chiron"]).longitude
        except Exception as exc:  # noqa: BLE001 - on veut voir n'importe quelle erreur du thread
            result["error"] = exc

    thread = threading.Thread(target=worker)
    thread.start()
    thread.join()

    assert "error" not in result, f"Chiron a échoué dans le thread worker : {result.get('error')}"
    assert 0 <= result["longitude"] < 360
