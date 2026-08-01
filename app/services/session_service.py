from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app import models


def get_or_create_session(db: Session, session_token: str | None) -> models.AnonymousSession:
    if session_token:
        existing = (
            db.query(models.AnonymousSession)
            .filter(models.AnonymousSession.session_token == session_token)
            .first()
        )
        if existing and existing.expires_at.replace(tzinfo=timezone.utc) > datetime.now(timezone.utc):
            return existing

    new_session = models.AnonymousSession()
    db.add(new_session)
    db.commit()
    db.refresh(new_session)
    return new_session
