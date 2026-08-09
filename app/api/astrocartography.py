from datetime import date as date_type

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app import models, schemas
from app.api.deps import get_owned_chart, get_session
from app.database import get_db
from app.services import astrocartography_service

router = APIRouter(tags=["astrocartography"])


@router.get("/api/charts/{chart_id}/astrocartography", response_model=schemas.NatalAstrocartographyResponse)
def get_natal_astrocartography(
    chart_id: str,
    db: Session = Depends(get_db),
    session: models.AnonymousSession = Depends(get_session),
):
    chart = get_owned_chart(chart_id, db, session)
    lines = astrocartography_service.get_or_compute_natal_lines(db, chart)
    return {
        "natal_chart_id": chart.id,
        "lines": [{"planet": line.planet, "line_type": line.line_type, "line_points": line.line_points} for line in lines],
    }


@router.get("/api/astrocartography/transit", response_model=schemas.TransitAstrocartographyResponse)
def get_transit_astrocartography(
    date: date_type | None = Query(None, description="Date pour la cyclocartographie (défaut : aujourd'hui, UTC)"),
    db: Session = Depends(get_db),
):
    lines = astrocartography_service.get_or_compute_transit_lines(db, date)
    calc_date = lines[0].calculation_date if lines else (date or date_type.today())
    return {
        "calculation_date": calc_date,
        "lines": [{"planet": line.planet, "line_type": line.line_type, "line_points": line.line_points} for line in lines],
    }


@router.post(
    "/api/charts/{chart_id}/saved-locations", response_model=schemas.SavedLocationResponse, status_code=201
)
def create_saved_location(
    chart_id: str,
    payload: schemas.SavedLocationCreateRequest,
    db: Session = Depends(get_db),
    session: models.AnonymousSession = Depends(get_session),
):
    chart = get_owned_chart(chart_id, db, session)
    return astrocartography_service.create_saved_location(
        db, session, chart, payload.label, payload.city, payload.country, payload.latitude, payload.longitude
    )


@router.get("/api/charts/{chart_id}/saved-locations", response_model=list[schemas.SavedLocationResponse])
def list_saved_locations(
    chart_id: str,
    db: Session = Depends(get_db),
    session: models.AnonymousSession = Depends(get_session),
):
    chart = get_owned_chart(chart_id, db, session)
    return astrocartography_service.list_saved_locations(db, chart)


@router.delete("/api/saved-locations/{location_id}", status_code=204)
def delete_saved_location(
    location_id: str,
    db: Session = Depends(get_db),
    session: models.AnonymousSession = Depends(get_session),
):
    try:
        deleted = astrocartography_service.delete_saved_location(db, session, location_id)
    except astrocartography_service.SavedLocationAccessError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    if not deleted:
        raise HTTPException(status_code=404, detail="Lieu sauvegardé introuvable.")
    return None
