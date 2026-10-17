# GameHub

GameHub - сайт с каталогом игроков, командами, матчами и REST API. В этом репозитории находится исходный код сайта и материалы по тестированию.

## Ссылки

- **Сайт:** https://gamehub-055p.onrender.com
- **Swagger / API:** https://gamehub-055p.onrender.com/docs
- **QA-документация:** [qa-project/README.md](qa-project/README.md)

## Локальный запуск на Windows

Открой PowerShell в папке `gamehub`:

```powershell
py -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m uvicorn app:app --reload
```

Открой http://127.0.0.1:8000. Документация API будет доступна по адресу http://127.0.0.1:8000/docs.

## Основные API-маршруты

- `GET /api/health`
- `GET /api/players`
- `POST /api/players`
- `GET /api/teams`
- `POST /api/teams`
- `GET /api/matches`
- `POST /api/matches`
- `PATCH /api/matches/{id}`

Актуальные маршруты и форматы ответов сверяй в Swagger на проверяемой версии сайта.

## Тесты

Из папки `gamehub`:

```powershell
py -m pip install -r requirements.txt
pytest -q
```

Запуск команды сам по себе не означает, что тесты прошли. Результат нужно проверить после выполнения.
