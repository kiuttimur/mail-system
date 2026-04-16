from fastapi import FastAPI

from app.core.db import engine
from app.models.base import Base
from app.api.users import router as users_router
from app.api.letters import router as letters_router

app = FastAPI(title="Mail Core Service", version="1.0.0")

app.include_router(users_router)
app.include_router(letters_router)


@app.get("/health")
def health():
    return {"status": "ok"}


