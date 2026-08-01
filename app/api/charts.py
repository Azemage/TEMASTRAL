from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models, schemas
from app.api.deps import get_session
from app.database import get_db
from app.services import chart_service

router = APIRouter(prefix="/api/charts", tags=["charts"])


@router.post("", response_model=schemas.NatalChartResponse, status_code=201)
def create_chart(
    payload: schemas.ChartCreateRequest,
    db: Session = Depends(get_db),
    session: models.AnonymousSession = Depends(get_session),
):
    try:
        chart = chart_service.create_natal_chart(db, session, payload)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return chart


@router.get("", response_model=list[schemas.NatalChartResponse])
def list_charts(
    db: Session = Depends(get_db),
    session: models.AnonymousSession = Depends(get_session),
):
    return chart_service.list_charts(db, session)


@router.get("/{chart_id}", response_model=schemas.NatalChartResponse)
def get_chart(
    chart_id: str,
    db: Session = Depends(get_db),
    session: models.AnonymousSession = Depends(get_session),
):
    try:
        chart = chart_service.get_chart(db, session, chart_id)
    except chart_service.ChartAccessError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    if chart is None:
        raise HTTPException(status_code=404, detail="Thème introuvable.")
    return chart
