#!/usr/bin/env python3
"""Outil de RECHERCHE : compare l'estimation de la technique hellénistique/médiévale du
Hyleg/Alcocoden (app/core/lifespan_estimate.py) à l'âge réel atteint par des personnes dont la
naissance ET la mort sont des faits publics déjà survenus — la même démarche de validation que
l'exemple Charlie Chaplin du document source.

Volontairement un script en ligne de commande, PAS une route de l'API web ni un bouton de
l'interface : voir la docstring de app/core/lifespan_estimate.py pour pourquoi.

Usage :
    python scripts/backtest_lifespan.py --csv mon_fichier.csv
    python scripts/backtest_lifespan.py            # lance le petit jeu d'exemple ci-dessous

Format du CSV (en-tête requis) :
    name,birth_date,birth_time,timezone,latitude,longitude,death_date
    - birth_date, death_date : AAAA-MM-JJ
    - birth_time : HH:MM:SS, ou vide si l'heure de naissance est inconnue (les maisons/l'Ascendant
      seront alors approximatifs, et le Hyleg avec — voir la colonne 'note' du résultat)
    - timezone : nom IANA (ex. Europe/Paris)
    - death_date : AAAA-MM-JJ, ou vide (le script affiche alors juste l'estimation, sans écart)
"""

from __future__ import annotations

import argparse
import csv
import sys
from datetime import date as date_type
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core import ephemeris
from app.core.chart_calculator import DEFAULT_TIME_WHEN_UNKNOWN, calculate_natal_chart
from app.core.lifespan_estimate import estimate_lifespan

# Jeu d'exemple volontairement fictif (pas de personne réelle) : sert uniquement à vérifier que
# le script tourne correctement de bout en bout avant d'y brancher vos propres données de
# personnages historiques (heure de naissance bien sourcée requise pour un résultat exploitable).
SAMPLE_ROWS = [
    {
        "name": "Exemple A (fictif)",
        "birth_date": "1920-03-14",
        "birth_time": "08:15:00",
        "timezone": "Europe/Paris",
        "latitude": "48.8566",
        "longitude": "2.3522",
        "death_date": "1975-11-02",
    },
    {
        "name": "Exemple B (fictif, heure inconnue)",
        "birth_date": "1875-07-01",
        "birth_time": "",
        "timezone": "Europe/London",
        "latitude": "51.5074",
        "longitude": "-0.1278",
        "death_date": "1940-01-20",
    },
]


def _years_between(start: date_type, end: date_type) -> float:
    return round((end - start).days / 365.25, 2)


def _process_row(row: dict) -> dict:
    birth_date = row["birth_date"]
    birth_time = row.get("birth_time") or None
    time_known = bool(birth_time)
    timezone = row["timezone"]
    latitude = float(row["latitude"])
    longitude = float(row["longitude"])

    effective_time = birth_time if time_known else DEFAULT_TIME_WHEN_UNKNOWN
    jd_ut = ephemeris.local_datetime_to_jd_ut(birth_date, effective_time, timezone)

    chart_data = calculate_natal_chart(
        birth_date=birth_date,
        birth_time=birth_time,
        time_known=time_known,
        timezone=timezone,
        latitude=latitude,
        longitude=longitude,
    )
    result = estimate_lifespan(chart_data, jd_ut)

    death_date_str = row.get("death_date") or None
    actual_years = None
    if death_date_str:
        actual_years = _years_between(date_type.fromisoformat(birth_date), date_type.fromisoformat(death_date_str))

    return {
        "name": row["name"],
        "time_known": time_known,
        "result": result,
        "actual_years": actual_years,
    }


def _print_report(entry: dict) -> None:
    result = entry["result"]
    print(f"\n=== {entry['name']} ===")
    if not entry["time_known"]:
        print("  (heure de naissance inconnue : Ascendant/maisons/Hyleg approximatifs)")
    if not result["available"]:
        print(f"  Hyleg : {result['hyleg']['name']} ({result['hyleg']['sign']} {result['hyleg']['degree']}°)")
        print(f"  {result['note']}")
        return

    hyleg = result["hyleg"]
    alcocoden = result["alcocoden"]
    print(f"  Hyleg      : {hyleg['name']} ({hyleg['sign']} {hyleg['degree']}°, maison {hyleg['house']})")
    print(f"  Alcocoden  : {alcocoden['name']} (dignité au degré du Hyleg : {alcocoden['dignity_score_at_hyleg']}/15)")
    print(f"  Niveau     : {result['year_level']} ({result['base_years']} ans de base)")
    for adj in result["adjustments"]:
        sign = "+" if adj["delta_years"] >= 0 else ""
        print(f"    ajustement {adj['planet']} ({adj['aspect_type']}) : {sign}{adj['delta_years']} ans")
    print(f"  Estimation : {result['estimated_years']} ans")
    if entry["actual_years"] is not None:
        diff = round(result["estimated_years"] - entry["actual_years"], 2)
        print(f"  Âge réel   : {entry['actual_years']} ans (écart : {diff:+.2f} ans)")
    print(f"  ({result['warning']})")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--csv", type=Path, help="Fichier CSV de personnes à traiter (voir format dans l'en-tête du script)")
    args = parser.parse_args()

    if args.csv:
        with open(args.csv, encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
    else:
        print("Aucun --csv fourni : lancement du jeu d'exemple fictif (vérification que tout fonctionne).")
        rows = SAMPLE_ROWS

    for row in rows:
        try:
            entry = _process_row(row)
        except Exception as exc:  # une ligne mal formée ne doit pas interrompre tout le lot
            print(f"\n=== {row.get('name', '?')} === ERREUR : {exc}")
            continue
        _print_report(entry)


if __name__ == "__main__":
    main()
