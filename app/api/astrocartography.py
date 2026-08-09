from datetime import date as date_type
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app import models, schemas
from app.api.deps import get_owned_chart, get_session
from app.core.astrocartography import ASTROCARTOGRAPHY_PLANETS, LINE_TYPES
from app.database import get_db
from app.services import astrocartography_service

router = APIRouter(tags=["astrocartography"])

# La Lune est exclue de la prévision multi-années par défaut : sa ligne balaie ~12°/jour, elle
# repasse près de n'importe quel lieu plusieurs fois par mois — pas pertinent sur un horizon de
# plusieurs années (voir compute_location_forecast). Reste sélectionnable explicitement via le
# paramètre `planets`.
_LOCATION_FORECAST_DEFAULT_PLANETS = [p for p in ASTROCARTOGRAPHY_PLANETS if p != "Moon"]


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


@router.get("/api/astrocartography/location-forecast", response_model=schemas.LocationForecastResponse)
def get_location_forecast(
    latitude: float = Query(..., ge=-90, le=90),
    longitude: float = Query(..., ge=-180, le=180),
    start_date: date_type = Query(default_factory=date_type.today),
    years: int = Query(10, ge=1, le=30),
    planets: str | None = Query(None, description="Planètes séparées par des virgules (défaut : toutes sauf la Lune)"),
    line_types: str | None = Query(None, description="Types de ligne séparés par des virgules (défaut : ASC,DC,MC,IC)"),
    threshold_km: float = Query(300.0, gt=0),
    step_days: int = Query(3, ge=1, le=30),
):
    selected_planets = [p.strip() for p in planets.split(",")] if planets else _LOCATION_FORECAST_DEFAULT_PLANETS
    unknown_planets = set(selected_planets) - set(ASTROCARTOGRAPHY_PLANETS)
    if unknown_planets:
        raise HTTPException(status_code=400, detail=f"Planète(s) inconnue(s) : {', '.join(sorted(unknown_planets))}")

    selected_line_types = [t.strip().upper() for t in line_types.split(",")] if line_types else list(LINE_TYPES)
    unknown_line_types = set(selected_line_types) - set(LINE_TYPES)
    if unknown_line_types:
        raise HTTPException(status_code=400, detail=f"Type(s) de ligne inconnu(s) : {', '.join(sorted(unknown_line_types))}")

    windows = astrocartography_service.compute_location_forecast(
        latitude=latitude,
        longitude=longitude,
        start_date=start_date,
        years=years,
        planets=selected_planets,
        line_types=selected_line_types,
        threshold_km=threshold_km,
        step_days=step_days,
    )
    end_date = start_date + timedelta(days=round(years * 365.25))
    return {
        "latitude": latitude,
        "longitude": longitude,
        "start_date": start_date,
        "end_date": end_date,
        "threshold_km": threshold_km,
        "windows": windows,
    }


@router.get("/api/charts/{chart_id}/astrocartography/interesting-cities", response_model=list[schemas.InterestingCity])
def get_interesting_cities(
    chart_id: str,
    threshold_km: float = Query(300.0, gt=0),
    top_n: int = Query(12, ge=1, le=50),
    db: Session = Depends(get_db),
    session: models.AnonymousSession = Depends(get_session),
):
    chart = get_owned_chart(chart_id, db, session)
    return astrocartography_service.compute_interesting_cities_for_chart(db, chart, threshold_km=threshold_km, top_n=top_n)


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
