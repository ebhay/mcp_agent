from datetime import datetime, timezone

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from pymongo.database import Database

from ..db import get_db
from ..deps import current_user

router = APIRouter(prefix="/api/mail", tags=["mail"])


class MailIn(BaseModel):
    to_username: str = Field(min_length=1, max_length=50)
    subject: str = Field(min_length=1, max_length=150)
    body: str = Field(min_length=1, max_length=5000)


def utc_iso(value: datetime) -> str:
    # MongoDB returns naive datetimes; they are stored in UTC, so mark them explicitly.
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()


def to_out(doc: dict) -> dict:
    return {
        "id": str(doc["_id"]),
        "from_username": doc["from_username"],
        "from_name": doc["from_name"],
        "to_username": doc["to_username"],
        "to_name": doc["to_name"],
        "subject": doc["subject"],
        "body": doc["body"],
        "is_read": doc["is_read"],
        "created_at": utc_iso(doc["created_at"]),
    }


def parse_id(message_id: str) -> ObjectId:
    try:
        return ObjectId(message_id)
    except InvalidId:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Message not found")


@router.get("/recipients")
def recipients(user: dict = Depends(current_user), db: Database = Depends(get_db)):
    people = db.users.find({"username": {"$ne": user["username"]}}, {"_id": 0, "username": 1, "name": 1, "role": 1})
    return list(people)


@router.post("", status_code=201)
def send(payload: MailIn, user: dict = Depends(current_user), db: Database = Depends(get_db)):
    target = db.users.find_one({"username": payload.to_username.strip()})
    if target is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Recipient not found")
    # Admins can message anyone; coaches can only reply to admins.
    allowed = user["role"] == "admin" or (user["role"] == "coach" and target["role"] == "admin")
    if not allowed:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Your role cannot send to this recipient")
    doc = {
        "from_username": user["username"],
        "from_name": user["name"],
        "to_username": target["username"],
        "to_name": target["name"],
        "subject": payload.subject.strip(),
        "body": payload.body.strip(),
        "is_read": False,
        "created_at": datetime.now(timezone.utc),
    }
    doc["_id"] = db.messages.insert_one(doc).inserted_id
    return to_out(doc)


@router.get("/inbox")
def inbox(user: dict = Depends(current_user), db: Database = Depends(get_db),
          limit: int = Query(50, le=200), unread: bool = Query(False)):
    query: dict = {"to_username": user["username"]}
    if unread:
        query["is_read"] = False
    docs = db.messages.find(query).sort("created_at", -1).limit(limit)
    return [to_out(d) for d in docs]


@router.get("/sent")
def sent(user: dict = Depends(current_user), db: Database = Depends(get_db), limit: int = Query(50, le=200)):
    docs = db.messages.find({"from_username": user["username"]}).sort("created_at", -1).limit(limit)
    return [to_out(d) for d in docs]


@router.get("/unread-count")
def unread_count(user: dict = Depends(current_user), db: Database = Depends(get_db)):
    return {"count": db.messages.count_documents({"to_username": user["username"], "is_read": False})}


@router.get("/{message_id}")
def read(message_id: str, user: dict = Depends(current_user), db: Database = Depends(get_db)):
    oid = parse_id(message_id)
    doc = db.messages.find_one({"_id": oid, "$or": [{"to_username": user["username"]}, {"from_username": user["username"]}]})
    if doc is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Message not found")
    if doc["to_username"] == user["username"] and not doc["is_read"]:
        db.messages.update_one({"_id": oid}, {"$set": {"is_read": True}})
        doc["is_read"] = True
    return to_out(doc)
