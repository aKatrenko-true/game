# GameHub - мой проект для практики QA

Я развиваю GameHub как учебный проект, на котором разбираюсь в тестировании веб-приложения. В проекте есть адаптивный интерфейс, REST API, база SQLite, демонстрационные игроки, команды и матчи, а также создание профиля. Я постепенно добавляю проверки, разбираю найденные ошибки и фиксирую результаты в документации.

## Run on Windows
1. Open PowerShell in this folder.
2. Create and activate a virtual environment:
   `py -m venv .venv`
   `.venv\\Scripts\\Activate.ps1`
   If PowerShell blocks activation, skip activation and use `.venv\\Scripts\\python.exe -m pip install -r requirements.txt` and `.venv\\Scripts\\python.exe -m uvicorn app:app --reload`.
3. Install dependencies: `py -m pip install -r requirements.txt`
4. Start: `py -m uvicorn app:app --reload`
5. Open http://127.0.0.1:8000 and API docs at http://127.0.0.1:8000/docs.

## API
- GET /api/health
- GET /api/players?q=Aveli&game=CS2
- POST /api/players
- GET /api/teams
- POST /api/teams
- GET /api/matches?status=Live
- POST /api/matches
- PATCH /api/matches/{id}

## Что я проверяю
Я проверяю создание профиля, уникальность никнейма, граничные значения валидации, поиск и фильтры по играм, создание команд и матчей, изменение статуса матча, пустые состояния и HTTP-коды API.

## Limitations
This is a local educational app, not a production service. There is no password-based authentication, authorization, email verification, or production database configuration. Do not use real personal information.
