"""Эндпоинты отправки и чтения писем внутри почтового сервиса."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, desc, select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.models.letter import Letter
from app.models.user import User
from app.schemas.letter import LetterCreate, LetterOut, MarkReadRequest
from app.services.communicator_client import notify_new_letter

router = APIRouter(prefix="/letters", tags=["letters"])


def _ensure_user_exists(db: Session, user_id: int, name: str):
    # Используем общий хелпер, чтобы sender/recipient проверялись одинаково.
    if not db.get(User, user_id):
        raise HTTPException(status_code=404, detail=f"{name} user not found")


@router.post("", response_model=LetterOut, status_code=status.HTTP_201_CREATED)
async def send_letter(payload: LetterCreate, db: Session = Depends(get_db)):
    if payload.sender_id == payload.recipient_id:
        raise HTTPException(status_code=400, detail="sender_id cannot equal recipient_id")

    _ensure_user_exists(db, payload.sender_id, "sender")
    _ensure_user_exists(db, payload.recipient_id, "recipient")

    letter = Letter(
        sender_id=payload.sender_id,
        recipient_id=payload.recipient_id,
        subject=payload.subject.strip(),
        body=payload.body.strip(),
    )
    db.add(letter)
    db.commit()
    db.refresh(letter)

    # best-effort уведомление коммуникатору (в ЛР2 может быть выключено)
    await notify_new_letter(letter_id=letter.id, recipient_id=letter.recipient_id, subject=letter.subject)

    return letter


@router.get("/{letter_id}", response_model=LetterOut)
def get_letter(letter_id: int, db: Session = Depends(get_db)):
    letter = db.get(Letter, letter_id)
    if not letter:
        raise HTTPException(status_code=404, detail="letter not found")
    return letter


@router.get("/inbox/{user_id}", response_model=list[LetterOut])
def inbox(
    user_id: int,
    unread_only: bool = Query(False),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    _ensure_user_exists(db, user_id, "recipient")

    # unread_only управляет только фильтром, а сортировку и пагинацию
    # сохраняем одинаковыми для всех вариантов выборки.
    cond = [Letter.recipient_id == user_id]
    if unread_only:
        cond.append(Letter.is_read.is_(False))

    letters = db.scalars(
        select(Letter)
        .where(and_(*cond))
        .order_by(desc(Letter.created_at), desc(Letter.id))
        .limit(limit)
        .offset(offset)
    ).all()
    return list(letters)


@router.get("/sent/{user_id}", response_model=list[LetterOut])
def sent(
    user_id: int,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    _ensure_user_exists(db, user_id, "sender")

    letters = db.scalars(
        select(Letter)
        .where(Letter.sender_id == user_id)
        .order_by(desc(Letter.created_at), desc(Letter.id))
        .limit(limit)
        .offset(offset)
    ).all()
    return list(letters)


@router.post("/{letter_id}/read", response_model=LetterOut)
def mark_read(letter_id: int, payload: MarkReadRequest, db: Session = Depends(get_db)):
    letter = db.get(Letter, letter_id)
    if not letter:
        raise HTTPException(status_code=404, detail="letter not found")

    if payload.user_id != letter.recipient_id:
        raise HTTPException(status_code=403, detail="only recipient can mark as read")

    if not letter.is_read:
        # Повторная отметка "прочитано" не должна менять данные лишний раз.
        letter.is_read = True
        letter.read_at = datetime.now(timezone.utc)
        db.add(letter)
        db.commit()
        db.refresh(letter)

    return letter
