import json

from app.models.call import Call
from app.models.case import Case
from app.models.contact import Contact
from app.models.message import Message
from app.models.timeline_event import TimelineEvent, TimelineEventType
from app.services.ingestion import CaseFolderParser
from sqlmodel import select


def _make_case_folder(tmp_path):
    (tmp_path / "contacts.csv").write_text("name,phone_number\nAlice,+1111111111\nBob,+2222222222\n", encoding="utf-8")
    (tmp_path / "calls.csv").write_text(
        "number,direction,duration_seconds,timestamp\n"
        "+1111111111,outgoing,120,2026-01-01T10:00:00\n"
        "+2222222222,incoming,0,2026-01-02T03:15:00\n",
        encoding="utf-8",
    )
    (tmp_path / "messages.csv").write_text(
        "sender,recipient,body,timestamp,app\n"
        "device_owner,+1111111111,hey are we still on for tonight,2026-01-01T09:00:00,sms\n",
        encoding="utf-8",
    )
    (tmp_path / "device_events.json").write_text(
        json.dumps(
            [
                {"type": "app_install", "timestamp": "2026-01-01T08:00:00", "detail": "SketchyApp"},
                {"type": "app_uninstall", "timestamp": "2026-01-01T09:30:00", "detail": "SketchyApp"},
            ]
        ),
        encoding="utf-8",
    )
    return tmp_path


def test_ingest_populates_contacts_calls_messages_and_timeline(session, tmp_path):
    case = Case(name="Test Case", source_path=str(tmp_path))
    session.add(case)
    session.commit()
    session.refresh(case)

    folder = _make_case_folder(tmp_path)
    summary = CaseFolderParser().ingest(session, case, folder)

    assert summary.contacts == 2
    assert summary.calls == 2
    assert summary.messages == 1
    assert summary.device_events == 2

    contacts = session.exec(select(Contact).where(Contact.case_id == case.id)).all()
    assert {c.name for c in contacts} == {"Alice", "Bob"}

    calls = session.exec(select(Call).where(Call.case_id == case.id)).all()
    assert len(calls) == 2

    messages = session.exec(select(Message).where(Message.case_id == case.id)).all()
    assert messages[0].body.startswith("hey are we still")

    events = session.exec(select(TimelineEvent).where(TimelineEvent.case_id == case.id)).all()
    event_types = {e.event_type for e in events}
    assert TimelineEventType.call in event_types
    assert TimelineEventType.message in event_types
    assert TimelineEventType.app_install in event_types
    assert TimelineEventType.app_uninstall in event_types
