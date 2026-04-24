"""HTTP-клиент communicator -> Telegram Bot API."""

import httpx

from app.core.config import settings


class TelegramClientError(RuntimeError):
    """Ошибка при отправке в Telegram Bot API."""


async def send_text_message(chat_id: str | int, text: str) -> bool:
    # Если бот ещё не настроен, communicator продолжает работать как console logger.
    if not settings.telegram_bot_token:
        return False

    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"

    try:
        # Telegram API используется только как внешний транспорт; бизнес-логика
        # успешной/неуспешной отправки остаётся на уровне communicator.
        async with httpx.AsyncClient(timeout=settings.telegram_request_timeout_seconds) as client:
            response = await client.post(
                url,
                json={
                    "chat_id": str(chat_id),
                    "text": text,
                },
            )
    except httpx.HTTPError as exc:
        raise TelegramClientError(f"telegram request failed: {exc}") from exc

    if response.status_code >= 400:
        raise TelegramClientError(f"telegram returned {response.status_code}: {response.text}")

    return True
