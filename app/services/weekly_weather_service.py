"""Calcul et mise en cache de la couche collective de la météo hebdomadaire (voir
app/core/weekly_weather.py). Une seule ligne de cache par semaine (identifiée par sa date de
début), partagée par tous les utilisateurs — même principe de cache paresseux que le calendrier
ésotérique annuel (app/services/witchy_calendar_service.py).

Expose aussi `compute_domain_scores_for_chart`, qui combine cette couche collective (réutilisée
telle quelle depuis le cache) avec le thème natal réel d'une personne pour la notation par
domaine de vie (voir app/core/weekly_weather_domains.py) — PAS mis en cache, car personnel à
chaque thème (même principe que les autres calculs "à la volée" propres à un chart_id, ex.
timing_service)."""

from __future__ import annotations

from datetime import date as date_type

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import models
from app.core.weekly_weather import SCHEMA_VERSION, compute_weekly_collective
from app.core.weekly_weather_domains import compute_weekly_domain_scores
from app.services import timing_service


def get_or_compute_weekly_weather(db: Session, start_date: date_type) -> dict:
    existing = db.query(models.GlobalWeeklyWeatherCache).filter_by(period_start=start_date).first()
    if existing and existing.collective_data.get("schema_version") == SCHEMA_VERSION:
        return existing.collective_data

    collective_data = compute_weekly_collective(start_date)

    if existing:
        # Ligne déjà présente mais d'une forme périmée (compute_weekly_collective a changé
        # depuis — nouveau champ, etc.) : on la met à jour plutôt que de la servir telle quelle
        # indéfiniment, le cache étant partagé par tous les visiteurs de cette semaine et ne se
        # rafraîchissant sinon jamais tout seul.
        existing.collective_data = collective_data
        db.commit()
        return collective_data

    row = models.GlobalWeeklyWeatherCache(period_start=start_date, collective_data=collective_data)
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        # Cache partagé par tous les utilisateurs : une autre requête concurrente pour la même
        # semaine a déjà inséré le résultat en premier. On relit son résultat plutôt que
        # d'échouer (voir la même correction pour le calendrier witchy/astrocartographie).
        db.rollback()
        existing = db.query(models.GlobalWeeklyWeatherCache).filter_by(period_start=start_date).first()
        return existing.collective_data

    return collective_data


def compute_domain_scores_for_chart(db: Session, chart: models.NatalChart, start_date: date_type) -> dict:
    collective = get_or_compute_weekly_weather(db, start_date)

    forecast = timing_service.compute_forecast(chart, start_date)
    personal_highlights = timing_service.select_events_for_horizon(forecast["events"], "week", start_date)

    natal_planet_houses = {p["name"]: p["house"] for p in chart.computed_chart_data["planets"]}

    return compute_weekly_domain_scores(
        natal_planet_houses, personal_highlights, collective.get("generational_aspects", []), start_date
    )
