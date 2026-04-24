FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
# Зависимости ставим отдельным слоем, чтобы Docker лучше использовал кеш сборки.
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./alembic.ini
COPY seed.py ./seed.py
# В контейнер кладём безопасный шаблон env, а не локальный .env с секретами.
COPY .env.example ./.env

EXPOSE 8001

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
