from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import current_user
from ..models import Message, User

router = APIRouter(prefix="/api/mail", tags=["mail"])


class MailIn(BaseModel):
    to_username: str = Field(min_length=1, max_length=50)
    subject: str = Field(min_length=1, max_length=150)
    body: str = Field(min_length=1, max_length=5000)


def utc_iso(value: datetime) -> str:
    # SQLite returns naive datetimes; they are stored in UTC, so mark them explicitly.
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()


def to_out(m: Message) -> dict:
    return {
        "id": str(m.id),
        "from_username": m.from_username,
        "from_name": m.from_name,
        "to_username": m.to_username,
        "to_name": m.to_name,
        "subject": m.subject,
        "body": m.body,
        "is_read": m.is_read,
        "created_at": utc_iso(m.created_at),
    }


def parse_id(message_id: str) -> int:
    try:
        return int(message_id)
    except ValueError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Message not found")


@router.get("/recipients")
def recipients(user: dict = Depends(current_user), db: Session = Depends(get_db)):
    people = db.scalars(select(User).where(User.username != user["username"]).order_by(User.name)).all()
    return [{"username": p.username, "name": p.name, "role": p.role} for p in people]


@router.post("", status_code=201)
def send(payload: MailIn, user: dict = Depends(current_user), db: Session = Depends(get_db)):
    target = db.scalar(select(User).where(User.username == payload.to_username.strip()))
    if target is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Recipient not found")
    # Admins can message anyone; coaches can only reply to admins.
    allowed = user["role"] == "admin" or (user["role"] == "coach" and target.role == "admin")
    if not allowed:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Your role cannot send to this recipient")
    message = Message(
        from_username=user["username"],
        from_name=user["name"],
        to_username=target.username,
        to_name=target.name,
        subject=payload.subject.strip(),
        body=payload.body.strip(),
        is_read=False,
        created_at=datetime.now(timezone.utc),
    )
    db.add(message)
    db.commit()
    db.refresh(message)
    return to_out(message)


@router.get("/inbox")
def inbox(user: dict = Depends(current_user), db: Session = Depends(get_db),
          limit: int = Query(50, le=200), unread: bool = Query(False)):
    query = select(Message).where(Message.to_username == user["username"])
    if unread:
        query = query.where(Message.is_read.is_(False))
    rows = db.scalars(query.order_by(Message.created_at.desc(), Message.id.desc()).limit(limit)).all()
    return [to_out(m) for m in rows]


@router.get("/sent")
def sent(user: dict = Depends(current_user), db: Session = Depends(get_db), limit: int = Query(50, le=200)):
    rows = db.scalars(
        select(Message).where(Message.from_username == user["username"])
        .order_by(Message.created_at.desc(), Message.id.desc()).limit(limit)
    ).all()
    return [to_out(m) for m in rows]


@router.get("/unread-count")
def unread_count(user: dict = Depends(current_user), db: Session = Depends(get_db)):
    count = db.scalar(
        select(func.count()).select_from(Message)
        .where(Message.to_username == user["username"], Message.is_read.is_(False))
    )
    return {"count": count or 0}


@router.get("/{message_id}")
def read(message_id: str, user: dict = Depends(current_user), db: Session = Depends(get_db)):
    mid = parse_id(message_id)
    message = db.scalar(
        select(Message).where(
            Message.id == mid,
            or_(Message.to_username == user["username"], Message.from_username == user["username"]),
        )
    )
    if message is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Message not found")
    if message.to_username == user["username"] and not message.is_read:
        message.is_read = True
        db.commit()
    return to_out(message)
