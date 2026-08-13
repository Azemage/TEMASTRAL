from datetime import date as date_type

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app import schemas
from app.database import get_db
from app.services import witchy_calendar_service

router = APIRouter(tags=["witchy-calendar"])


@router.get("/api/witchy-calendar", response_model=schemas.WitchyCalendarResponse)
def get_witchy_calendar(
    year: int = Query(default_factory=lambda: date_type.today().year, ge=1900, le=2200),
    db: Session = Depends(get_db),
):
    events = witchy_calendar_service.get_or_compute_witchy_calendar(db, year)
    return {"year": year, "events": events}
