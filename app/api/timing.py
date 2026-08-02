from datetime import date as date_type

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app import models, schemas
from app.api.deps import get_session
from app.database import get_db
from app.services import chart_service
from app.services.timing_service import compute_forecast, compute_timing

router = APIRouter(prefix="/api/charts/{chart_id}/timing", tags=["timing"])


def _get_owned_chart(chart_id: str, db: Session, session: models.AnonymousSession) -> models.NatalChart:
    try:
        chart = chart_service.get_chart(db, session, chart_id)
    except chart_service.ChartAccessError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    if chart is None:
        raise HTTPException(status_code=404, detail="Thème introuvable.")
    return chart


@router.get("", response_model=schemas.TimingResponse)
def get_timing(
    chart_id: str,
    date: date_type | None = Query(None, description="Date pour transits/profection (défaut : aujourd'hui)"),
    db: Session = Depends(get_db),
    session: models.AnonymousSession = Depends(get_session),
):
    chart = _get_owned_chart(chart_id, db, session)
    return compute_timing(chart, date)


@router.get("/forecast", response_model=schemas.TransitForecastResponse)
def get_timing_forecast(
    chart_id: str,
    date: date_type | None = Query(None, description="Date de départ du balayage (défaut : aujourd'hui)"),
    months: int = Query(12, ge=1, le=24, description="Nombre de mois à balayer"),
    db: Session = Depends(get_db),
    session: models.AnonymousSession = Depends(get_session),
):
    chart = _get_owned_chart(chart_id, db, session)
    return compute_forecast(chart, date, months)
