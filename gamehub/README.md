# GameHub — QA portfolio project

GameHub is a learning project for testing a gaming community website. It includes a responsive UI, REST API, SQLite database, seeded demo players, teams and matches, and basic profile creation.

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

## QA ideas
Test profile creation, nickname uniqueness, validation boundaries, search and game filters, team creation, match creation, match status changes, empty states, and API response codes.

## Limitations
This is a local educational app, not a production service. There is no password-based authentication, authorization, email verification, or production database configuration. Do not use real personal information.
