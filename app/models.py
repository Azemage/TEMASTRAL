import uuid
from datetime import date as date_type
from datetime import datetime, timedelta, timezone

from sqlalchemy import JSON, Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text, Time, UniqueConstraint
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
    astrocartography_lines: Mapped[list["NatalAstrocartographyLine"]] = relationship(
        back_populates="natal_chart", cascade="all, delete-orphan"
    )
    saved_locations: Mapped[list["SavedLocation"]] = relationship(back_populates="natal_chart", cascade="all, delete-orphan")


class SavedReading(Base):
    __tablename__ = "saved_readings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    natal_chart_id: Mapped[str] = mapped_column(String(36), ForeignKey("natal_charts.id", ondelete="CASCADE"), nullable=False)

    reading_type: Mapped[str] = mapped_column(String(30), nullable=False)
    focus_areas: Mapped[list] = mapped_column(JSON, default=list)

    request_payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    reading_text: Mapped[str] = mapped_column(Text, nullable=False)
    compatibility_ratings: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    timing_ratings: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    model_used: Mapped[str | None] = mapped_column(String(50), nullable=True)
    tokens_used: Mapped[int | None] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    natal_chart: Mapped["NatalChart"] = relationship(back_populates="readings")


class NatalAstrocartographyLine(Base):
    """Lignes d'astrocartographie natales (ASC/DC/MC/IC par planète), calculées une seule
    fois à la première consultation du thème puis mises en cache — le thème natal ne change
    jamais, inutile de recalculer."""

    __tablename__ = "natal_astrocartography_lines"
    __table_args__ = (UniqueConstraint("natal_chart_id", "planet", "line_type"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    natal_chart_id: Mapped[str] = mapped_column(String(36), ForeignKey("natal_charts.id", ondelete="CASCADE"), nullable=False)

    planet: Mapped[str] = mapped_column(String(20), nullable=False)
    line_type: Mapped[str] = mapped_column(String(5), nullable=False)  # 'ASC' | 'DC' | 'MC' | 'IC'
    line_points: Mapped[list] = mapped_column(JSON, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    natal_chart: Mapped["NatalChart"] = relationship(back_populates="astrocartography_lines")


class GlobalTransitLinesCache(Base):
    """Cache global des lignes de transit (cyclocartographie) du jour : un seul calcul par
    jour, partagé par tous les utilisateurs — contrairement aux lignes natales, propres à
    chaque thème. Calculé paresseusement à la première requête du jour plutôt que par une
    tâche planifiée (pas d'infrastructure de cron dans cette application)."""

    __tablename__ = "global_transit_lines_cache"
    __table_args__ = (UniqueConstraint("calculation_date", "planet", "line_type"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    calculation_date: Mapped[date_type] = mapped_column(Date, nullable=False)

    planet: Mapped[str] = mapped_column(String(20), nullable=False)
    line_type: Mapped[str] = mapped_column(String(5), nullable=False)
    line_points: Mapped[list] = mapped_column(JSON, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class GlobalWitchyCalendarCache(Base):
    """Cache global du calendrier ésotérique annuel (lunaisons, éclipses, stations
    rétrogrades, ingrès de planètes lentes) : un seul calcul par année civile, partagé par
    tous les utilisateurs — ce calendrier ne dépend d'aucun thème natal (voir
    app/core/witchy_calendar.py). Calculé paresseusement à la première requête de l'année
    plutôt que par une tâche planifiée. Un seul événement calculé une fois par an ne justifie
    pas une ligne par événement : la liste complète est stockée en un seul bloc JSON."""

    __tablename__ = "global_witchy_calendar_cache"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    year: Mapped[int] = mapped_column(Integer, nullable=False, unique=True)
    events: Mapped[list] = mapped_column(JSON, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class GlobalWeeklyWeatherCache(Base):
    """Cache global de la couche collective de la météo hebdomadaire (Lune, Mercure/Vénus/Mars,
    aspects transit-transit, événements du calendrier witchy dans la semaine, highlights notés) :
    un seul calcul par semaine (identifiée par sa date de début), partagé par tous les
    utilisateurs — indépendant de tout thème natal (voir app/core/weekly_weather.py). Même
    principe de cache paresseux que le calendrier ésotérique annuel."""

    __tablename__ = "global_weekly_weather_cache"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    period_start: Mapped[date_type] = mapped_column(Date, nullable=False, unique=True)
    collective_data: Mapped[dict] = mapped_column(JSON, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class SavedLocation(Base):
    """Lieu sauvegardé/analysé par l'utilisateur (ex. "et si je déménageais à Lisbonne ?").
    Rattaché à la session anonyme (pas de table users dans ce MVP, voir AnonymousSession)."""

    __tablename__ = "saved_locations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    anonymous_session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("anonymous_sessions.id", ondelete="CASCADE"), nullable=False
    )
    natal_chart_id: Mapped[str] = mapped_column(String(36), ForeignKey("natal_charts.id", ondelete="CASCADE"), nullable=False)

    label: Mapped[str | None] = mapped_column(String(150), nullable=True)
    city: Mapped[str | None] = mapped_column(String(150), nullable=True)
    country: Mapped[str | None] = mapped_column(String(100), nullable=True)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)

    # Résultat de "quelles lignes natales passent près de ce point" (calcul déterministe, mis
    # en cache à la création plutôt que recalculé à chaque affichage).
    nearby_lines_analysis: Mapped[list | None] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    natal_chart: Mapped["NatalChart"] = relationship(back_populates="saved_locations")
