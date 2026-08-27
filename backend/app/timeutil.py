from datetime import datetime, timezone


def utcnow() -> datetime:
    """Naive UTC 'now'. SQLite (and SQLModel's DateTime column) drops tzinfo on
    round-trip, so storing timezone-aware datetimes here would make a value
    read back from the DB differ from the value that was written — which
    breaks anything that recomputes a hash/comparison over it (see
    services/audit_log.py). Keep every stored timestamp naive UTC instead."""
    return datetime.now(timezone.utc).replace(tzinfo=None)
