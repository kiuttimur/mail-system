"""Точка входа FastAPI-приложения mail-core."""

from fastapi import FastAPI

from app.api.auth import router as auth_router
from app.api.letters import router as letters_router
from app.api.users import router as users_router
from app.ui import router as ui_router

app = FastAPI(title="Mail Core Service", version="1.0.0")

# Подключаем UI и REST API в одном приложении, чтобы сервис можно было
# использовать и через браузер, и через Swagger/HTTP-клиент.
app.include_router(ui_router)
app.include_router(auth_router)
app.include_router(users_router)
app.include_router(letters_router)


@app.get("/health")
def health():
    return {"status": "ok"}
