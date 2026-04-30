from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker, Session
from core.config import get_settings

settings = get_settings()

# SQLite necesita check_same_thread=False para funcionar con FastAPI
connect_args = {"check_same_thread": False} if settings.is_sqlite else {}

engine = create_engine(
    settings.database_url,
    connect_args=connect_args,
    echo=settings.environment == "development",
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    """Dependency para FastAPI — provee una sesión de DB y la cierra al terminar."""
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Crea todas las tablas si no existen. Llamar al arrancar la app."""
    from core.models import task, project  # noqa: F401 — importar para registrar modelos
    Base.metadata.create_all(bind=engine)
