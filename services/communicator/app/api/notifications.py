"""Эндпоинты получения событий от mail-core."""

from fastapi import APIRouter

from app.core.config import settings
from app.schemas.communicator import NewLetterEvent, NewLetterNotificationResult
from app.services.mail_core_client import MailCoreClientError, get_telegram_contact
from app.services.telegram_client import TelegramClientError, send_text_message

router = APIRouter(prefix="/notify", tags=["notifications"])


def _log(message: str) -> None:
    print(f"{settings.communicator_log_prefix} {message}", flush=True)


@router.post("/new-letter", response_model=NewLetterNotificationResult)
async def notify_new_letter(payload: NewLetterEvent):
    # Сначала всегда логируем событие в консоль, даже если Telegram не настроен.
    _log(
        f"new letter received: letter_id={payload.letter_id} "
        f"recipient_id={payload.recipient_id} subject={payload.subject!r}"
    )

    try:
        # communicator не хранит пользователей сам: за текущим chat_id идём в mail-core.
        contact = await get_telegram_contact(payload.recipient_id)
    except MailCoreClientError as exc:
        return NewLetterNotificationResult(
            delivered_to_console=True,
            delivered_to_telegram=False,
            detail=str(exc),
        )

    if not contact.telegram_chat_id:
        # Это не ошибка доставки письма: просто у получателя ещё нет Telegram-привязки.
        return NewLetterNotificationResult(
            delivered_to_console=True,
            delivered_to_telegram=False,
            detail="recipient has no linked telegram chat",
        )

    try:
        sent = await send_text_message(
            contact.telegram_chat_id,
            (
                f"New letter #{payload.letter_id}\n"
                f"Subject: {payload.subject}"
            ),
        )
    except TelegramClientError as exc:
        return NewLetterNotificationResult(
            delivered_to_console=True,
            delivered_to_telegram=False,
            detail=str(exc),
        )

    detail = "telegram notification sent" if sent else "telegram bot is not configured"
    return NewLetterNotificationResult(
        delivered_to_console=True,
        delivered_to_telegram=sent,
        detail=detail,
    )
