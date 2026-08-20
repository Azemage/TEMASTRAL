from datetime import date as date_type
from datetime import timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app import models, schemas
from app.api.deps import get_owned_chart, get_session
from app.core.weekly_weather import compute_generic_weekly_by_sign
from app.database import get_db
from app.services import weekly_weather_service

router = APIRouter(tags=["weekly-weather"])


@router.get("/api/weekly-weather", response_model=schemas.WeeklyWeatherResponse)
def get_weekly_weather(
    start_date: date_type = Query(default_factory=date_type.today),
    db: Session = Depends(get_db),
):
    return weekly_weather_service.get_or_compute_weekly_weather(db, start_date)


@router.get("/api/weekly-weather/by-sign", response_model=schemas.WeeklyWeatherBySignResponse)
def get_weekly_weather_by_sign(
    start_date: date_type = Query(default_factory=date_type.today),
    db: Session = Depends(get_db),
):
    collective = weekly_weather_service.get_or_compute_weekly_weather(db, start_date)
    main_event_sign = collective["main_event"]["sign"]
    return {"main_event_sign": main_event_sign, "by_sign": compute_generic_weekly_by_sign(main_event_sign)}


@router.get(
    "/api/charts/{chart_id}/weekly-weather/domain-scores",
    response_model=schemas.WeeklyWeatherDomainScoresResponse,
)
def get_weekly_weather_domain_scores(
    chart_id: str,
    start_date: date_type = Query(default_factory=date_type.today),
    db: Session = Depends(get_db),
    session: models.AnonymousSession = Depends(get_session),
):
    # Personnel (croise le thème natal réel) : PAS mis en cache, contrairement à la couche
    # collective ci-dessus — voir weekly_weather_service.compute_domain_scores_for_chart.
    chart = get_owned_chart(chart_id, db, session)
    scores = weekly_weather_service.compute_domain_scores_for_chart(db, chart, start_date)
    return {"period_start": start_date, "period_end": start_date + timedelta(days=6), "scores": scores}
