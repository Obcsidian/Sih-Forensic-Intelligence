from app.services import audit_log


def test_first_entry_chains_from_genesis(session):
    entry = audit_log.append_entry(session, actor="system", action="case.create", payload={"name": "test"})
    assert entry.prev_hash == audit_log.GENESIS_HASH
    assert len(entry.hash) == 64


def test_chain_grows_and_verifies(session):
    audit_log.append_entry(session, actor="system", action="a", payload={"n": 1})
    audit_log.append_entry(session, actor="system", action="b", payload={"n": 2})
    e3 = audit_log.append_entry(session, actor="system", action="c", payload={"n": 3})

    result = audit_log.verify_chain(session)
    assert result.valid is True
    assert result.total_entries == 3
    assert e3.prev_hash != audit_log.GENESIS_HASH


def test_tampering_with_a_past_entry_breaks_verification(session):
    from sqlmodel import select

    from app.models.audit_log import AuditLogEntry

    e1 = audit_log.append_entry(session, actor="system", action="a", payload={"n": 1})
    audit_log.append_entry(session, actor="system", action="b", payload={"n": 2})

    stored = session.exec(select(AuditLogEntry).where(AuditLogEntry.id == e1.id)).one()
    stored.payload_json = '{"n": 9999}'
    session.add(stored)
    session.commit()

    result = audit_log.verify_chain(session)
    assert result.valid is False
    assert result.first_broken_entry_id == e1.id


def test_deleting_a_past_entry_breaks_verification(session):
    from sqlmodel import select

    from app.models.audit_log import AuditLogEntry

    e1 = audit_log.append_entry(session, actor="system", action="a", payload={"n": 1})
    audit_log.append_entry(session, actor="system", action="b", payload={"n": 2})

    session.delete(session.exec(select(AuditLogEntry).where(AuditLogEntry.id == e1.id)).one())
    session.commit()

    result = audit_log.verify_chain(session)
    assert result.valid is False
