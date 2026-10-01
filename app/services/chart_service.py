from datetime import time as time_type

from sqlalchemy.orm import Session

from app import models, schemas
from app.core.chart_calculator import calculate_natal_chart
from app.core.zodiac import sign_index


class ChartAccessError(Exception):
    """Levée quand un thème est demandé par une session qui n'en est pas propriétaire."""


def create_natal_chart(
    db: Session, session: models.AnonymousSession, request: schemas.ChartCreateRequest
) -> models.NatalChart:
    birth_data = request.birth_data
    settings = request.settings
    location = birth_data.location

    ascendant_override_longitude = None
    if birth_data.ascendant_override is not None:
        override = birth_data.ascendant_override
        ascendant_override_longitude = sign_index(override.sign) * 30 + override.degree_in_sign

    # Sans ville (ascendant fixé manuellement), latitude/longitude ne servent à rien — voir
    # calculate_natal_chart, qui les ignore dans ce cas — mais les colonnes DB restent NOT
    # NULL : 0.0/0.0 est une valeur sentinelle sans signification, jamais affichée comme lieu.
    latitude = location.latitude if location else 0.0
    longitude = location.longitude if location else 0.0

    computed = calculate_natal_chart(
        birth_date=birth_data.date.isoformat(),
        birth_time=birth_data.time,
        time_known=birth_data.time_known,
        timezone=birth_data.timezone,
        latitude=latitude,
        longitude=longitude,
        house_system=settings.house_system,
        aspect_orbs=settings.aspect_orbs.model_dump(),
        include_minor_aspects=settings.include_minor_aspects,
        optional_points=settings.optional_points,
        ascendant_override_longitude=ascendant_override_longitude,
    )

    chart = models.NatalChart(
        anonymous_session_id=session.id,
        subject_name=request.subject_name,
        relationship_to_user=request.relationship_to_user,
        birth_date=birth_data.date,
        birth_time=time_type.fromisoformat(birth_data.time) if birth_data.time else None,
        birth_time_known=birth_data.time_known,
        birth_timezone=birth_data.timezone,
        birth_city=location.city if location else None,
        birth_country=location.country if location else None,
        birth_latitude=latitude,
        birth_longitude=longitude,
        ascendant_override_longitude=ascendant_override_longitude,
        house_system=settings.house_system,
        zodiac_type=settings.zodiac_type,
        rulership_system=settings.rulership_system,
        computed_chart_data=computed,
    )
    db.add(chart)
    db.commit()
    db.refresh(chart)
    return chart


def get_chart(db: Session, session: models.AnonymousSession, chart_id: str) -> models.NatalChart | None:
    chart = db.query(models.NatalChart).filter(models.NatalChart.id == chart_id).first()
    if chart is None:
        return None
    if chart.anonymous_session_id != session.id:
        raise ChartAccessError("Ce thème n'appartient pas à cette session.")
    return chart


def list_charts(db: Session, session: models.AnonymousSession) -> list[models.NatalChart]:
    return (
        db.query(models.NatalChart)
        .filter(models.NatalChart.anonymous_session_id == session.id)
        .order_by(models.NatalChart.created_at.desc())
        .all()
    )
