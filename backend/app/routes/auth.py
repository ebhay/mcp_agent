from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
from pymongo.database import Database

from ..db import get_db
from ..deps import bearer, current_user
from ..security import new_token, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginIn(BaseModel):
    username: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=1, max_length=200)


def public_user(user: dict) -> dict:
    return {"username": user["username"], "name": user["name"], "role": user["role"]}


@router.post("/login")
def login(payload: LoginIn, db: Database = Depends(get_db)):
    user = db.users.find_one({"username": payload.username.strip()})
    if user is None or not verify_password(payload.password, user["password_hash"]):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Wrong username or password")
    token = new_token()
    db.sessions.insert_one({"token": token, "username": user["username"], "created_at": datetime.now(timezone.utc)})
    return {"token": token, "user": public_user(user)}


@router.get("/users")
def list_users(db: Database = Depends(get_db)):
    return list(db.users.find({}, {"_id": 0, "username": 1, "name": 1, "role": 1}).sort("role", 1))


class SwitchIn(BaseModel):
    username: str = Field(min_length=1, max_length=50)


@router.post("/switch")
def switch(payload: SwitchIn, db: Database = Depends(get_db)):
    """Demo role switch: issues a session for the chosen user without a password."""
    user = db.users.find_one({"username": payload.username})
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    token = new_token()
    db.sessions.insert_one({"token": token, "username": user["username"], "created_at": datetime.now(timezone.utc)})
    return {"token": token, "user": public_user(user)}


@router.get("/me")
def me(user: dict = Depends(current_user)):
    return public_user(user)


@router.post("/logout", status_code=204)
def logout(creds: HTTPAuthorizationCredentials | None = Depends(bearer), db: Database = Depends(get_db)):
    if creds is not None:
        db.sessions.delete_one({"token": creds.credentials})
