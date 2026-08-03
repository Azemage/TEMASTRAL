from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import get_settings

settings = get_settings()

connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    from app import models  # noqa: F401  (ensure models are registered)

    Base.metadata.create_all(bind=engine)
    add_missing_columns(engine)


def add_missing_columns(target_engine) -> None:
    """Filet de sécurité pour SQLite : `create_all()` ne modifie jamais les tables déjà
    présentes en base, donc une colonne ajoutée à un modèle après la toute première exécution
    (ex. `compatibility_ratings`, `timing_ratings`) reste absente d'un fichier .db existant tant
    qu'on ne le supprime pas à la main — ce qui casse silencieusement l'écriture (erreur SQLite
    'no such column', renvoyée comme 500 par l'API). On répare ça ici avec de simples
    `ALTER TABLE ... ADD COLUMN`, proportionné à un projet sans outil de migration dédié plutôt
    que d'exiger de l'utilisateur qu'il recrée sa base à chaque évolution du schéma."""
    if target_engine.dialect.name != "sqlite":
        return
    with target_engine.begin() as conn:
        for table in Base.metadata.sorted_tables:
            existing_columns = {row[1] for row in conn.exec_driver_sql(f'PRAGMA table_info("{table.name}")')}
            if not existing_columns:
                continue  # table pas encore créée (ne devrait pas arriver juste après create_all)
            for column in table.columns:
                if column.name not in existing_columns:
                    col_type = column.type.compile(dialect=target_engine.dialect)
                    conn.exec_driver_sql(f'ALTER TABLE "{table.name}" ADD COLUMN "{column.name}" {col_type}')
