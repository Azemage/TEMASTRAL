from fastapi import Depends, Request, Response
from sqlalchemy.orm import Session

from app import models
from app.config import get_settings
from app.database import get_db
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
