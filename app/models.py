import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import JSON, Boolean, Date, DateTime, ForeignKey, Integer, String, Text, Time
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _default_expiry() -> datetime:
    return datetime.now(timezone.utc) + timedelta(days=365)


class AnonymousSession(Base):
    __tablename__ = "anonymous_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    session_token: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, default=_uuid)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_default_expiry)

    natal_charts: Mapped[list["NatalChart"]] = relationship(back_populates="anonymous_session", cascade="all, delete-orphan")


class NatalChart(Base):
    __tablename__ = "natal_charts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    anonymous_session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("anonymous_sessions.id", ondelete="CASCADE"), nullable=False
    )

    subject_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    relationship_to_user: Mapped[str] = mapped_column(String(50), default="self")

    birth_date: Mapped[Date] = mapped_column(Date, nullable=False)
    birth_time: Mapped[Time | None] = mapped_column(Time, nullable=True)
    birth_time_known: Mapped[bool] = mapped_column(Boolean, default=True)
    birth_timezone: Mapped[str] = mapped_column(String(50), nullable=False)
    birth_city: Mapped[str | None] = mapped_column(String(150), nullable=True)
    birth_country: Mapped[str | None] = mapped_column(String(100), nullable=True)
    birth_latitude: Mapped[float] = mapped_column(nullable=False)
    birth_longitude: Mapped[float] = mapped_column(nullable=False)

    house_system: Mapped[str] = mapped_column(String(30), default="placidus")
    zodiac_type: Mapped[str] = mapped_column(String(20), default="tropical")
    rulership_system: Mapped[str] = mapped_column(String(20), default="both")

    computed_chart_data: Mapped[dict] = mapped_column(JSON, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc)
    )

    anonymous_session: Mapped["AnonymousSession"] = relationship(back_populates="natal_charts")
    readings: Mapped[list["SavedReading"]] = relationship(back_populates="natal_chart", cascade="all, delete-orphan")


class SavedReading(Base):
    __tablename__ = "saved_readings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    natal_chart_id: Mapped[str] = mapped_column(String(36), ForeignKey("natal_charts.id", ondelete="CASCADE"), nullable=False)

    reading_type: Mapped[str] = mapped_column(String(30), nullable=False)
    focus_areas: Mapped[list] = mapped_column(JSON, default=list)

    request_payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    reading_text: Mapped[str] = mapped_column(Text, nullable=False)
    compatibility_ratings: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    model_used: Mapped[str | None] = mapped_column(String(50), nullable=True)
    tokens_used: Mapped[int | None] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    natal_chart: Mapped["NatalChart"] = relationship(back_populates="readings")
