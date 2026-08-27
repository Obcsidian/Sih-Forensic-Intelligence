from datetime import datetime

from app.models.evidence_file import EvidenceFile, EvidenceKind
from app.services import anomaly_detection
from app.models.timeline_event import TimelineEvent, TimelineEventType


def test_deleted_then_recovered_file_is_flagged(session):
    ef = EvidenceFile(
        case_id=1,
        kind=EvidenceKind.photo,
        original_path="/x/photo.jpg",
        file_name="photo.jpg",
        sha256="deadbeef",
        deleted_then_recovered=True,
    )
    session.add(ef)
    session.commit()

    anomalies = anomaly_detection.detect(session, case_id=1)
    kinds = {a.kind for a in anomalies}
    assert "deleted_then_recovered" in kinds


def test_briefly_installed_app_is_flagged(session):
    session.add(
        TimelineEvent(
            case_id=1,
            event_type=TimelineEventType.app_install,
            timestamp=datetime(2026, 1, 1, 8, 0, 0),
            summary="SketchyApp",
            source_table="device_event",
            source_id=0,
        )
    )
    session.add(
        TimelineEvent(
            case_id=1,
            event_type=TimelineEventType.app_uninstall,
            timestamp=datetime(2026, 1, 1, 9, 30, 0),
            summary="SketchyApp",
            source_table="device_event",
            source_id=0,
        )
    )
    session.commit()

    anomalies = anomaly_detection.detect(session, case_id=1)
    kinds = {a.kind for a in anomalies}
    assert "briefly_installed_app" in kinds


def test_long_lived_app_is_not_flagged(session):
    session.add(
        TimelineEvent(
            case_id=1,
            event_type=TimelineEventType.app_install,
            timestamp=datetime(2026, 1, 1, 8, 0, 0),
            summary="NormalApp",
            source_table="device_event",
            source_id=0,
        )
    )
    session.add(
        TimelineEvent(
            case_id=1,
            event_type=TimelineEventType.app_uninstall,
            timestamp=datetime(2026, 2, 1, 8, 0, 0),
            summary="NormalApp",
            source_table="device_event",
            source_id=0,
        )
    )
    session.commit()

    anomalies = anomaly_detection.detect(session, case_id=1)
    assert "briefly_installed_app" not in {a.kind for a in anomalies}


def test_odd_hour_call_is_flagged(session):
    session.add(
        TimelineEvent(
            case_id=1,
            event_type=TimelineEventType.call,
            timestamp=datetime(2026, 1, 1, 3, 0, 0),
            summary="outgoing call with +1111111111",
            source_table="call",
            source_id=1,
        )
    )
    session.commit()

    anomalies = anomaly_detection.detect(session, case_id=1)
    assert "odd_hour_activity" in {a.kind for a in anomalies}


def test_detect_is_idempotent(session):
    ef = EvidenceFile(
        case_id=1,
        kind=EvidenceKind.photo,
        original_path="/x/photo.jpg",
        file_name="photo.jpg",
        sha256="deadbeef",
        deleted_then_recovered=True,
    )
    session.add(ef)
    session.commit()

    first = anomaly_detection.detect(session, case_id=1)
    second = anomaly_detection.detect(session, case_id=1)
    assert len(first) == len(second)
