from collections.abc import Generator

from sqlmodel import Session, SQLModel, create_engine

from app.config import get_settings

settings = get_settings()

connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, echo=False, connect_args=connect_args)


def init_db() -> None:
    # Import models so their tables are registered on SQLModel.metadata before create_all.
    from app.models import (  # noqa: F401
        audit_log,
        call,
        case,
        contact,
        evidence_file,
        face_detection,
        message,
        person,
        report,
        timeline_event,
        transcript,
        user,
    )

    SQLModel.metadata.create_all(engine)


def get_session() -> Generator[Session, None, None]:
    # expire_on_commit=False: request handlers often commit more than once per
    # request (e.g. a business-logic commit followed by an audit_log.append_entry
    # commit). With the SQLAlchemy default, that second commit expires every
    # object touched earlier, so the object FastAPI serializes for the response
    # comes back empty. Keeping attributes populated after commit avoids that.
    with Session(engine, expire_on_commit=False) as session:
        yield session
