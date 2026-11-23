from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import get_settings
from .db import get_engine
from .models import Base, User
from .security import hash_password


def demo_users() -> list[dict]:
    """Demo accounts; logins and passwords come from backend/.env."""
    s = get_settings()
    return [
        {"username": s.coach_login_id, "password": s.coach_password, "role": "coach", "name": "Coach One"},
        {"username": s.trainer_login_id, "password": s.trainer_password, "role": "trainer", "name": "Trainer One"},
        {"username": s.admin_login_id, "password": s.admin_password, "role": "admin", "name": "Admin One"},
    ]


def create_tables() -> None:
    """Creates any missing tables and indexes. Existing rows are kept."""
    Base.metadata.create_all(get_engine())


def seed_users(db: Session) -> None:
    for user in demo_users():
        if not user["password"]:
            raise RuntimeError(f"Set the {user['role']} password in backend/.env before starting")
        exists = db.scalar(select(User).where(User.username == user["username"]))
        if exists is None:
            db.add(User(
                username=user["username"],
                name=user["name"],
                role=user["role"],
                password_hash=hash_password(user["password"]),
            ))
    db.commit()
