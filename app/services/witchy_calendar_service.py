"""Calcul et mise en cache du calendrier ésotérique annuel (voir app/core/witchy_calendar.py).
Une seule ligne de cache par année civile, partagée par tous les utilisateurs — ce calendrier
ne dépend d'aucun thème natal, même principe de cache paresseux que les lignes de transit de
l'astrocartographie (app/services/astrocartography_service.py)."""

from __future__ import annotations

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import models
from app.core.witchy_calendar import compute_witchy_calendar


def get_or_compute_witchy_calendar(db: Session, year: int) -> list[dict]:
    existing = db.query(models.GlobalWitchyCalendarCache).filter_by(year=year).first()
    if existing:
        return existing.events

    events = compute_witchy_calendar(year)
    row = models.GlobalWitchyCalendarCache(year=year, events=events)
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        # Cache partagé par tous les utilisateurs : une autre requête concurrente pour la même
        # année a déjà inséré le calendrier en premier. On relit son résultat plutôt que
        # d'échouer (voir la même correction pour les lignes d'astrocartographie).
        db.rollback()
        existing = db.query(models.GlobalWitchyCalendarCache).filter_by(year=year).first()
        return existing.events

    return events
