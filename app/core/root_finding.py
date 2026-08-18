"""Recherche de racines (croisements à zéro) par balayage échantillonné + bissection, réutilisée
par tout module qui doit détecter l'instant exact où une fonction astronomique continue change
de signe (élongation Lune-Soleil, vitesse apparente, longitude, écart angulaire dirigé entre
deux planètes...) — voir witchy_calendar.py (lunaisons, éclipses, stations, ingrès, grandes
conjonctions) et weekly_weather.py (aspects exacts entre planètes rapides sur une semaine)."""

from __future__ import annotations

from typing import Callable

_BISECTION_ITERATIONS = 30


def bisect_root(f: Callable[[float], float], lo: float, hi: float) -> float:
    """Racine de `f` (changement de signe) entre `lo` et `hi`, par bissection."""
    f_lo_negative = f(lo) < 0
    for _ in range(_BISECTION_ITERATIONS):
        mid = (lo + hi) / 2
        if (f(mid) < 0) == f_lo_negative:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def scan_zero_crossings(f: Callable[[float], float], start_jd: float, end_jd: float, step: float) -> list[float]:
    """Jours juliens où `f` change de signe dans [start_jd, end_jd], affinés par bissection.

    `step` doit être très inférieur à l'espacement minimal réel entre deux occurrences de la
    racine cherchée, sans quoi une occurrence pourrait être manquée entre deux échantillons.
    """
    results: list[float] = []
    jd = start_jd
    prev = f(jd)
    while jd < end_jd:
        next_jd = min(jd + step, end_jd)
        curr = f(next_jd)
        if prev == 0:
            results.append(jd)
        elif (prev < 0) != (curr < 0) and abs(curr - prev) < 180:
            # Le "< 180" exclut les discontinuités de rebouclage (ex. offset qui saute de +179°
            # à -180° à l'opposé exact de la cible, pour une fonction construite avec un modulo
            # centré) : une vraie racine ne change que d'un pas d'échantillonnage, jamais de
            # ~360° d'un coup.
            results.append(bisect_root(f, jd, next_jd))
        jd = next_jd
        prev = curr
    return results
