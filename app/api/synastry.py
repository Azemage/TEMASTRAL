from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app import models, schemas
from app.api.deps import get_owned_chart, get_session
from app.core.synastry import SUPPORTED_RELATIONSHIP_MODES
from app.database import get_db
from app.services.synastry_service import compute_synastry_for_charts

router = APIRouter(prefix="/api/charts/{chart_id}/compatibility", tags=["synastry"])


@router.get("", response_model=schemas.SynastryResponse)
def get_compatibility(
    chart_id: str,
    chart_b_id: str = Query(..., description="Identifiant du second thème natal"),
    mode: str = Query(..., description=f"Mode de relation : {sorted(SUPPORTED_RELATIONSHIP_MODES)}"),
    db: Session = Depends(get_db),
    session: models.AnonymousSession = Depends(get_session),
):
    if mode not in SUPPORTED_RELATIONSHIP_MODES:
        raise HTTPException(
            status_code=422,
            detail=f"Mode de relation invalide : {mode!r}. Modes disponibles : {sorted(SUPPORTED_RELATIONSHIP_MODES)}.",
        )
    if chart_b_id == chart_id:
        raise HTTPException(status_code=422, detail="Les deux thèmes doivent être différents.")

    chart_a = get_owned_chart(chart_id, db, session)
    chart_b = get_owned_chart(chart_b_id, db, session)
    return compute_synastry_for_charts(chart_a, chart_b, mode)
