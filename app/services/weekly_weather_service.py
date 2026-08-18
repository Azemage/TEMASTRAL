"""Calcul et mise en cache de la couche collective de la météo hebdomadaire (voir
app/core/weekly_weather.py). Une seule ligne de cache par semaine (identifiée par sa date de
début), partagée par tous les utilisateurs — même principe de cache paresseux que le calendrier
ésotérique annuel (app/services/witchy_calendar_service.py)."""

from __future__ import annotations

from datetime import date as date_type

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import models
from app.core.weekly_weather import compute_weekly_collective


def get_or_compute_weekly_weather(db: Session, start_date: date_type) -> dict:
    existing = db.query(models.GlobalWeeklyWeatherCache).filter_by(period_start=start_date).first()
    if existing:
        return existing.collective_data

    collective_data = compute_weekly_collective(start_date)
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
