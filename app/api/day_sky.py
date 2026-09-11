from fastapi import APIRouter

from app import schemas
from app.core.day_sky import compute_day_sky

router = APIRouter(prefix="/api/day-sky", tags=["day-sky"])


@router.get("", response_model=schemas.DaySkyResponse)
def get_day_sky():
    return compute_day_sky()
