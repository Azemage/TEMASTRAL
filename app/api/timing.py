from datetime import date as date_type

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app import models, schemas
from app.api.deps import get_owned_chart, get_session
from app.database import get_db
from app.services.timing_service import compute_forecast, compute_timing

router = APIRouter(prefix="/api/charts/{chart_id}/timing", tags=["timing"])


@router.get("", response_model=schemas.TimingResponse)
def get_timing(
    chart_id: str,
    date: date_type | None = Query(None, description="Date pour transits/profection (défaut : aujourd'hui)"),
    db: Session = Depends(get_db),
    session: models.AnonymousSession = Depends(get_session),
):
    chart = get_owned_chart(chart_id, db, session)
    return compute_timing(chart, date)


@router.get("/forecast", response_model=schemas.TransitForecastResponse)
def get_timing_forecast(
    chart_id: str,
    date: date_type | None = Query(None, description="Date de départ du balayage (défaut : aujourd'hui)"),
    months: int = Query(12, ge=1, le=24, description="Nombre de mois à balayer"),
    db: Session = Depends(get_db),
    session: models.AnonymousSession = Depends(get_session),
):
    chart = get_owned_chart(chart_id, db, session)
    return compute_forecast(chart, date, months)
