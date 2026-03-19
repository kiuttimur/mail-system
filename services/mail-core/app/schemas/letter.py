from datetime import datetime
from pydantic import BaseModel, Field


class LetterCreate(BaseModel):
    sender_id: int
    recipient_id: int
    subject: str = Field(min_length=1, max_length=120)
    body: str = Field(min_length=1, max_length=10_000)


class LetterOut(BaseModel):
    id: int
    sender_id: int
    recipient_id: int
    subject: str
    body: str
    created_at: datetime
    is_read: bool
    read_at: datetime | None

    model_config = {"from_attributes": True}


class MarkReadRequest(BaseModel):
    user_id: int  # кто отмечает (должен быть recipient)