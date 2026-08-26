"""Creates demo users on first run. Run with `python -m app.seed` or it's called automatically
by main.py's startup hook if the users table is empty.

DEMO CREDENTIALS ONLY — rotate/remove before any non-demo deployment.
"""

from sqlmodel import Session, select

from app.database import engine, init_db
from app.models.user import Role, User
from app.security import hash_password

DEMO_USERS = [
    ("investigator", "investigator123", Role.investigator, "Demo Investigator"),
    ("reviewer", "reviewer123", Role.reviewer, "Demo Reviewer"),
    ("viewer", "viewer123", Role.read_only, "Demo Read-Only User"),
]


def seed_demo_users(session: Session) -> list[str]:
    created = []
    for username, password, role, full_name in DEMO_USERS:
        existing = session.exec(select(User).where(User.username == username)).first()
        if existing:
            continue
        session.add(User(username=username, hashed_password=hash_password(password), role=role, full_name=full_name))
        created.append(username)
    session.commit()
    return created


if __name__ == "__main__":
    init_db()
    with Session(engine) as session:
        created = seed_demo_users(session)
        if created:
            print(f"Created demo users: {', '.join(created)}")
        else:
            print("Demo users already exist.")
