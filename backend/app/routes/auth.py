from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import bearer, current_user, public_user
from ..models import AuthSession, User
from ..security import new_token, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginIn(BaseModel):
    username: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=1, max_length=200)


class SwitchIn(BaseModel):
    username: str = Field(min_length=1, max_length=50)


def _open_session(db: Session, user: User) -> dict:
    token = new_token()
    db.add(AuthSession(token=token, username=user.username, created_at=datetime.now(timezone.utc)))
    db.commit()
    return {"token": token, "user": public_user(user)}


@router.post("/login")
def login(payload: LoginIn, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.username == payload.username.strip()))
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Wrong username or password")
    return _open_session(db, user)


@router.get("/users")
def list_users(db: Session = Depends(get_db)):
    users = db.scalars(select(User).order_by(User.role, User.username)).all()
    return [{"username": u.username, "name": u.name, "role": u.role} for u in users]


@router.post("/switch")
def switch(payload: SwitchIn, db: Session = Depends(get_db)):
    """Demo role switch: issues a session for the chosen user without a password."""
    user = db.scalar(select(User).where(User.username == payload.username))
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    return _open_session(db, user)


@router.get("/me")
def me(user: dict = Depends(current_user)):
    return user


@router.post("/logout", status_code=204)
def logout(creds: HTTPAuthorizationCredentials | None = Depends(bearer), db: Session = Depends(get_db)):
    if creds is not None:
        session = db.scalar(select(AuthSession).where(AuthSession.token == creds.credentials))
        if session is not None:
            db.delete(session)
            db.commit()
