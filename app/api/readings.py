from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models, schemas
from app.api.deps import get_session
from app.database import get_db
from app.services import chart_service
from app.services.interpretation_service import generate_reading

router = APIRouter(prefix="/api/charts/{chart_id}/readings", tags=["readings"])


@router.post("", response_model=schemas.ReadingResponse, status_code=201)
async def create_reading(
    chart_id: str,
    payload: schemas.ReadingRequest,
    db: Session = Depends(get_db),
    session: models.AnonymousSession = Depends(get_session),
):
    try:
        chart = chart_service.get_chart(db, session, chart_id)
    except chart_service.ChartAccessError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    if chart is None:
        raise HTTPException(status_code=404, detail="Thème introuvable.")

    try:
        result = await generate_reading(chart, payload)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    reading = models.SavedReading(
        natal_chart_id=chart.id,
        reading_type=payload.reading_type,
        focus_areas=payload.focus_areas,
        request_payload=result["request_payload"],
        reading_text=result["reading_text"],
        model_used=result["model_used"],
        tokens_used=result["tokens_used"],
    )
    db.add(reading)
    db.commit()
    db.refresh(reading)
    return reading


@router.get("", response_model=list[schemas.ReadingResponse])
def list_readings(
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
    return chart.readings
