from datetime import date as date_type

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app import models, schemas
from app.api.deps import get_session
from app.database import get_db
from app.services import chart_service
from app.services.timing_service import compute_timing

router = APIRouter(prefix="/api/charts/{chart_id}/timing", tags=["timing"])


@router.get("", response_model=schemas.TimingResponse)
def get_timing(
    chart_id: str,
    date: date_type | None = Query(None, description="Date pour transits/profection (défaut : aujourd'hui)"),
    db: Session = Depends(get_db),
    session: models.AnonymousSession = Depends(get_session),
):
    try:
        chart = chart_service.get_chart(db, session, chart_id)
    except chart_service.ChartAccessError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    if chart is None:
        raise HTTPException(status_code=404, detail="Thème introuvable.")

    return compute_timing(chart, date)
