from pymongo.database import Database

from .config import get_settings
from .security import hash_password


def demo_users() -> list[dict]:
    """Demo accounts; logins and passwords come from backend/.env."""
    s = get_settings()
    return [
        {"username": s.coach_login_id, "password": s.coach_password, "role": "coach", "name": "Coach One"},
        {"username": s.trainer_login_id, "password": s.trainer_password, "role": "trainer", "name": "Trainer One"},
        {"username": s.admin_login_id, "password": s.admin_password, "role": "admin", "name": "Admin One"},
    ]


def seed_users(db: Database) -> None:
    for user in demo_users():
        if not user["password"]:
            raise RuntimeError(f"Set the {user['role']} password in backend/.env before starting")
        if db.users.find_one({"username": user["username"]}) is None:
            db.users.insert_one({
                "username": user["username"],
                "name": user["name"],
                "role": user["role"],
                "password_hash": hash_password(user["password"]),
            })


def create_indexes(db: Database) -> None:
    db.users.create_index("username", unique=True)
    db.sessions.create_index("token", unique=True)
    db.messages.create_index("to_username")
    db.messages.create_index("from_username")
