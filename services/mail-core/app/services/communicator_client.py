import httpx

from app.core.config import settings


async def notify_new_letter(letter_id: int, recipient_id: int, subject: str) -> None:
    """
    В ЛР2 это может быть выключено (COMMUNICATOR_URL=None).
    В ЛР3 будет communicator и просто зададим COMMUNICATOR_URL.
    """
    if not settings.communicator_url:
        return

    url = settings.communicator_url.rstrip("/") + "/notify/new-letter"
    payload = {
        "letter_id": letter_id,
        "recipient_id": recipient_id,
        "subject": subject,
    }

    try:
        async with httpx.AsyncClient(timeout=settings.communicator_timeout_seconds) as client:
            await client.post(url, json=payload)
    except Exception:
        # Письмо уже сохранено — уведомление "лучшей попыткой".
        # В ЛР3 можно улучшить через outbox/очередь, но сейчас оставим просто.
        return