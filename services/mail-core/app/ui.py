"""Роут, который отдаёт простую HTML-страницу поверх REST API."""

from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter(include_in_schema=False)

INDEX_HTML_PATH = Path(__file__).resolve().parent / "templates" / "index.html"


@router.get("/", response_class=HTMLResponse)
def web_app() -> HTMLResponse:
    # Храним HTML как отдельный файл шаблона, чтобы UI можно было менять
    # без смешивания большой разметки с python-кодом роутов.
    return HTMLResponse(INDEX_HTML_PATH.read_text(encoding="utf-8"))
