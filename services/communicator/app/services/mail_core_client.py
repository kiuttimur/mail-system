"""HTTP-клиент communicator -> mail-core для внутренних сервисных вызовов."""

import httpx

from app.core.config import settings
from app.schemas.communicator import MailCoreTelegramContact, MailCoreUser


class MailCoreClientError(RuntimeError):
    """Ошибка при обращении к mail-core."""


def _build_mail_core_url(path: str) -> str:
    return settings.mail_core_url.rstrip("/") + path


async def _request_json(method: str, path: str, payload: dict | None = None) -> dict:
    try:
        # Используем единый AsyncClient и таймаут из конфига, чтобы поведение
        # communicator было одинаковым и для webhook, и для уведомлений.
        async with httpx.AsyncClient(timeout=settings.telegram_request_timeout_seconds) as client:
            response = await client.request(
                method,
                _build_mail_core_url(path),
                json=payload,
            )
    except httpx.HTTPError as exc:
        raise MailCoreClientError(f"mail-core request failed: {exc}") from exc

    if response.status_code >= 400:
        detail = response.text
        try:
            payload_json = response.json()
            detail = payload_json.get("detail", detail)
        except ValueError:
            pass
        raise MailCoreClientError(f"mail-core returned {response.status_code}: {detail}")

    return response.json()


async def get_telegram_contact(user_id: int) -> MailCoreTelegramContact:
    # Mail-core отдаёт только данные, которые действительно нужны для доставки.
    payload = await _request_json("GET", f"/users/{user_id}/telegram-contact")
    return MailCoreTelegramContact.model_validate(payload)


async def confirm_telegram_link(
    token: str,
    chat_id: str,
    telegram_username: str | None,
) -> MailCoreUser:
    payload = await _request_json(
        "POST",
        "/users/telegram/confirm",
        {
            "token": token,
            "chat_id": chat_id,
            "telegram_username": telegram_username,
        },
    )
    return MailCoreUser.model_validate(payload)
