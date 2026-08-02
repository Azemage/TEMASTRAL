from datetime import date as date_type

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app import models, schemas
from app.api.deps import get_owned_chart, get_session
from app.database import get_db
from app.services.zodiacal_releasing_service import compute_zodiacal_releasing_for_chart

router = APIRouter(prefix="/api/charts/{chart_id}/zodiacal-releasing", tags=["zodiacal-releasing"])


@router.get("", response_model=schemas.ZodiacalReleasingResponse)
def get_zodiacal_releasing(
    chart_id: str,
    date: date_type | None = Query(None, description="Date pour laquelle situer la phase actuelle (défaut : aujourd'hui)"),
    db: Session = Depends(get_db),
    session: models.AnonymousSession = Depends(get_session),
):
    chart = get_owned_chart(chart_id, db, session)
    return compute_zodiacal_releasing_for_chart(chart, date)
