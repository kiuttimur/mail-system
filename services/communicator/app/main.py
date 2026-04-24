"""Точка входа FastAPI-приложения communicator."""

from fastapi import FastAPI

from app.api.notifications import router as notifications_router
from app.api.telegram import router as telegram_router

app = FastAPI(title="Communicator Service", version="1.0.0")

app.include_router(notifications_router)
app.include_router(telegram_router)


@app.get("/health")
def health():
    return {"status": "ok"}
