import sqlite3
import tempfile
from pathlib import Path

from sqlalchemy import create_engine

from app import models  # noqa: F401  (enregistre les modèles sur Base.metadata)
from app.database import Base, add_missing_columns


def _make_stale_db() -> str:
    """Un fichier SQLite avec la table saved_readings telle qu'avant l'ajout de
    compatibility_ratings/timing_ratings, pour simuler une base existante non migrée."""
    tmp_path = Path(tempfile.mkdtemp()) / "stale.db"
    conn = sqlite3.connect(tmp_path)
    conn.execute(
        """
        CREATE TABLE saved_readings (
            id VARCHAR(36) PRIMARY KEY,
            natal_chart_id VARCHAR(36) NOT NULL,
            reading_type VARCHAR(30) NOT NULL,
            focus_areas JSON,
            request_payload JSON NOT NULL,
            reading_text TEXT NOT NULL,
            model_used VARCHAR(50),
            tokens_used INTEGER,
            created_at DATETIME
        )
        """
    )
    conn.commit()
    conn.close()
    return f"sqlite:///{tmp_path}"


def test_add_missing_columns_adds_columns_absent_from_an_existing_table():
    engine = create_engine(_make_stale_db(), connect_args={"check_same_thread": False})

    before = {row[1] for row in engine.connect().exec_driver_sql('PRAGMA table_info("saved_readings")')}
    assert "compatibility_ratings" not in before
    assert "timing_ratings" not in before

    add_missing_columns(engine)

    after = {row[1] for row in engine.connect().exec_driver_sql('PRAGMA table_info("saved_readings")')}
    assert "compatibility_ratings" in after
    assert "timing_ratings" in after
    # Les colonnes préexistantes ne doivent pas être touchées.
    assert before <= after


def test_add_missing_columns_allows_writing_to_the_newly_added_column():
    engine = create_engine(_make_stale_db(), connect_args={"check_same_thread": False})
    add_missing_columns(engine)

    with engine.begin() as conn:
        conn.exec_driver_sql(
            "INSERT INTO saved_readings "
            "(id, natal_chart_id, reading_type, request_payload, reading_text, timing_ratings) "
            "VALUES ('r1', 'c1', 'timing', '{}', 'texte', '{\"amour\": {\"score\": 5}}')"
        )
        row = conn.exec_driver_sql("SELECT timing_ratings FROM saved_readings WHERE id = 'r1'").fetchone()
    assert row[0] == '{"amour": {"score": 5}}'


def test_add_missing_columns_is_a_noop_on_an_up_to_date_schema():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)

    add_missing_columns(engine)  # ne doit pas lever, même si tout est déjà à jour

    columns = {row[1] for row in engine.connect().exec_driver_sql('PRAGMA table_info("saved_readings")')}
    assert "compatibility_ratings" in columns
    assert "timing_ratings" in columns


def test_add_missing_columns_skips_non_sqlite_engines():
    class _FakeDialect:
        name = "postgresql"

    class _FakeEngine:
        dialect = _FakeDialect()

        def begin(self):
            raise AssertionError("ne devrait pas être appelé pour un moteur non-SQLite")

    add_missing_columns(_FakeEngine())  # ne doit pas lever ni tenter de se connecter
