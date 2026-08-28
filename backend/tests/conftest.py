import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine


@pytest.fixture
def session():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)

    # Import models so their tables register on SQLModel.metadata before create_all.
    from app.models import (  # noqa: F401
        audit_log,
        call,
        case,
        contact,
        data_source,
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
    with Session(engine) as s:
        yield s
