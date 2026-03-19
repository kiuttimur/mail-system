from datetime import datetime
from pydantic import BaseModel, Field


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=50)


class UserOut(BaseModel):
    id: int
    username: str
    created_at: datetime

    model_config = {"from_attributes": True}