from fastapi import Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

from app import models
from app.config import get_settings
from app.database import get_db
from app.services import chart_service
from app.services.session_service import get_or_create_session


def get_session(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> models.AnonymousSession:
    settings = get_settings()
    token = request.cookies.get(settings.session_cookie_name) or request.headers.get("X-Session-Token")

    session = get_or_create_session(db, token)

    response.set_cookie(
        key=settings.session_cookie_name,
        value=session.session_token,
        max_age=settings.session_ttl_days * 24 * 3600,
        httponly=True,
        samesite="lax",
    )
    return session


def get_owned_chart(chart_id: str, db: Session, session: models.AnonymousSession) -> models.NatalChart:
    """Récupère un thème natal en vérifiant qu'il appartient à la session courante,
    ou lève une HTTPException 403/404 appropriée. Partagé par les routes timing/lots/
    zodiacal-releasing qui ont toutes besoin de ce même contrôle d'accès."""
    try:
        chart = chart_service.get_chart(db, session, chart_id)
    except chart_service.ChartAccessError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    if chart is None:
        raise HTTPException(status_code=404, detail="Thème introuvable.")
    return chart
