FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
# Зависимости ставим до копирования всего кода, чтобы повторные сборки были быстрее.
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
# В образ попадает только шаблон настроек; реальные секреты задаются при запуске.
COPY .env.example ./.env

EXPOSE 8002

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8002"]
