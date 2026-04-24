"""Webhook-эндпоинт Telegram bot для подтверждения привязки."""

from fastapi import APIRouter

from app.core.config import settings
from app.schemas.communicator import TelegramUpdate, TelegramWebhookResult
from app.services.mail_core_client import MailCoreClientError, confirm_telegram_link
from app.services.telegram_client import TelegramClientError, send_text_message

router = APIRouter(prefix="/telegram", tags=["telegram"])


def _extract_start_token(update: TelegramUpdate) -> str | None:
    # Из Telegram webhook нас интересует только команда /start и её payload.
    if not update.message or not update.message.text:
        return None
    text = update.message.text.strip()
    if not text.startswith("/start"):
        return None
    parts = text.split(maxsplit=1)
    if len(parts) == 1:
        return ""
    return parts[1].strip()


async def _reply_to_chat(chat_id: str | int, text: str) -> None:
    # Ответ боту не должен валить обработку webhook, поэтому ошибки не пробрасываем дальше.
    try:
        await send_text_message(chat_id, text)
    except TelegramClientError:
        return


@router.post("/webhook", response_model=TelegramWebhookResult)
async def telegram_webhook(update: TelegramUpdate):
    token = _extract_start_token(update)
    if token is None:
        return TelegramWebhookResult(
            status="ignored",
            detail="update does not contain /start command",
        )

    if not update.message:
        return TelegramWebhookResult(
            status="ignored",
            detail="update has no message body",
        )

    chat_id = update.message.chat.id
    telegram_username = update.message.from_user.username if update.message.from_user else None

    if not token:
        # /start без payload не ломает webhook: просто подсказываем пользователю формат.
        await _reply_to_chat(
            chat_id,
            "Use /start <token> from the deep-link generated in mail-core.",
        )
        return TelegramWebhookResult(
            status="missing_token",
            detail="start command does not contain link token",
        )

    try:
        # communicator завершает flow привязки не локально у себя, а через mail-core,
        # чтобы именно mail-core оставался источником истины по пользователям.
        linked_user = await confirm_telegram_link(
            token=token,
            chat_id=str(chat_id),
            telegram_username=telegram_username,
        )
    except MailCoreClientError as exc:
        await _reply_to_chat(chat_id, f"Telegram link failed: {exc}")
        return TelegramWebhookResult(
            status="failed",
            detail=str(exc),
        )

    await _reply_to_chat(
        chat_id,
        f"Telegram linked to mail account {linked_user.username}.",
    )
    print(
        f"{settings.communicator_log_prefix} telegram linked: "
        f"user_id={linked_user.id} chat_id={chat_id} username={telegram_username!r}",
        flush=True,
    )
    return TelegramWebhookResult(
        status="linked",
        detail=f"telegram linked to user {linked_user.username}",
    )
