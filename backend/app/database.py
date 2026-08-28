from collections.abc import Generator
from pathlib import Path

from sqlmodel import Session, SQLModel, create_engine, select

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
        data_source,
        evidence_file,
        face_detection,
        message,
        person,
        registry_artifact,
        report,
        timeline_event,
        transcript,
        user,
    )

    SQLModel.metadata.create_all(engine)
    _add_missing_columns()
    _backfill_data_sources()


def _add_missing_columns() -> None:
    """create_all() only creates missing tables, never alters existing ones --
    there's no migration framework here, so a newly-added column on a table
    that already exists on disk needs a manual ADD COLUMN."""
    if not settings.database_url.startswith("sqlite"):
        return
    with engine.connect() as conn:
        existing = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(evidencefile)").fetchall()}
        if "data_source_id" not in existing:
            conn.exec_driver_sql("ALTER TABLE evidencefile ADD COLUMN data_source_id INTEGER")
            conn.commit()


def _backfill_data_sources() -> None:
    """Cases created before the multi-data-source feature only have
    Case.source_path/status. Give each of those a matching DataSource row so
    they show up in the data-sources list alongside newly-added sources."""
    from app.models.case import Case
    from app.models.data_source import DataSource, DataSourceStatus

    with Session(engine) as session:
        cases_without_source = session.exec(
            select(Case).where(~Case.id.in_(select(DataSource.case_id)))
        ).all()
        if not cases_without_source:
            return
        # CaseStatus has an extra "processing" value (mid-AI-pipeline) that
        # DataSourceStatus doesn't track; ingest itself already succeeded by then.
        status_map = {"created": DataSourceStatus.created, "ingesting": DataSourceStatus.ingesting, "failed": DataSourceStatus.failed}
        for c in cases_without_source:
            session.add(
                DataSource(
                    case_id=c.id,
                    name=Path(c.source_path).name or c.source_path,
                    source_path=c.source_path,
                    status=status_map.get(c.status.value, DataSourceStatus.ready),
                    created_by=c.created_by,
                    created_at=c.created_at,
                    updated_at=c.updated_at,
                )
            )
        session.commit()


def get_session() -> Generator[Session, None, None]:
    # expire_on_commit=False: request handlers often commit more than once per
    # request (e.g. a business-logic commit followed by an audit_log.append_entry
    # commit). With the SQLAlchemy default, that second commit expires every
    # object touched earlier, so the object FastAPI serializes for the response
    # comes back empty. Keeping attributes populated after commit avoids that.
    with Session(engine, expire_on_commit=False) as session:
        yield session
