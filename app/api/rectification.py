from fastapi import APIRouter

from app import schemas
from app.core.rectification import LifeEvent, scan_candidate_times

router = APIRouter(prefix="/api/rectification", tags=["rectification"])


@router.post("/scan", response_model=schemas.RectificationScanResponse)
def post_rectification_scan(request: schemas.RectificationScanRequest):
    life_events = [
        LifeEvent(label=e.label, event_date=e.date, significance=e.significance) for e in request.life_events
    ]
    return scan_candidate_times(
        birth_date=request.birth_date,
        timezone=request.timezone,
        latitude=request.latitude,
        longitude=request.longitude,
        life_events=life_events,
        window_start=request.window_start,
        window_end=request.window_end,
        step_minutes=request.step_minutes,
        house_system=request.house_system,
        candidate_signs=request.candidate_signs,
    )
