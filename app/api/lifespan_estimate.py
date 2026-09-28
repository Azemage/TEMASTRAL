from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import models, schemas
from app.api.deps import get_owned_chart, get_session
from app.database import get_db
from app.services.lifespan_estimate_service import compute_lifespan_estimate

router = APIRouter(prefix="/api/charts/{chart_id}/lifespan-estimate", tags=["lifespan"])


@router.get("", response_model=schemas.LifespanEstimateResponse)
def get_lifespan_estimate(
    chart_id: str,
    db: Session = Depends(get_db),
    session: models.AnonymousSession = Depends(get_session),
):
    chart = get_owned_chart(chart_id, db, session)
    return compute_lifespan_estimate(chart)
