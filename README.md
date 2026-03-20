# mail-system
Учебный проект: почтовая система на двух микросервисах

python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt

uvicorn app.main:app --reload --port 8001

http://localhost:8001/docs

Users

POST /users — создать пользователя

GET /users — список

GET /users/{id} — один пользователь

Letters

POST /letters — отправить письмо

GET /letters/inbox/{user_id} — входящие

GET /letters/sent/{user_id} — отправленные

GET /letters/{letter_id} — открыть письмо

POST /letters/{letter_id}/read — отметить прочитанным