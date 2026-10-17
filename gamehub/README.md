# GameHub - проект для QA-портфолио

GameHub - учебное веб-приложение с каталогом игроков, командами, матчами и REST API. Этот README - главная точка входа для знакомства с продуктом, локального запуска и материалов тестирования.

## Где смотреть QA-проект

**[Открыть QA-проект GameHub](qa-project/README.md)**

В QA-проекте находятся:
- [Хронология действий](qa-project/ACTION_HISTORY.md) - что мы проверяли и исправляли по порядку.
- [Стратегия тестирования](qa-project/TEST_STRATEGY.md).
- [Тест-кейсы](qa-project/TEST_CASES.md).
- [Баг-репорты](qa-project/BUG_REPORTS.md).
- [Чек-лист регрессии](qa-project/REGRESSION_CHECKLIST.md).
- [Матрица трассировки](qa-project/TRACEABILITY.md).
- [Шаблон отчёта о тестировании](qa-project/TEST_RUN_TEMPLATE.md).
- [Скриншоты и доказательства](qa-project/screenshots/README.md).

Краткая версия тест-плана: [QA_TEST_PLAN.md](QA_TEST_PLAN.md).

## Стенд

- **Опубликованный стенд:** https://gamehub-055p.onrender.com
- **Swagger/OpenAPI:** https://gamehub-055p.onrender.com/docs
- **Репозиторий:** https://github.com/aKatrenko-true/game

## Локальный запуск на Windows

Открой PowerShell в папке `gamehub`:

```powershell
py -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m uvicorn app:app --reload
```

Открой http://127.0.0.1:8000. Документация API доступна по адресу http://127.0.0.1:8000/docs.

## Основные API-маршруты

- `GET /api/health`
- `GET /api/players`
- `POST /api/players`
- `GET /api/teams`
- `POST /api/teams`
- `GET /api/matches`
- `POST /api/matches`
- `PATCH /api/matches/{id}`

Актуальный контракт необходимо сверять в OpenAPI/Swagger на проверяемой версии стенда.

## Технологии и QA-области

FastAPI, Python, JavaScript, HTML/CSS, PostgreSQL на опубликованном окружении и SQLite для локального режима. Проверки включают UI, REST API, валидацию, сохранение данных, регрессию, адаптивность и PWA.

## Тестирование API

Из папки `gamehub`:

```powershell
py -m pip install -r requirements.txt
pytest -q
```

## Текущий статус тестирования

- Пользователь подтвердил, что игроки отображаются и новые записи сохраняются.
- Исправлен дефект отображения каталога, связанный с вызовом `.forEach()` у результата одиночного DOM-селектора.
- Ранее наблюдавшаяся ошибка Service Worker требует отдельного повторного тестирования.
- Полный прогон админки, LFG, адаптивности и безопасности не подтверждён. Непроверенные сценарии не считать пройденными.

## Ограничения и безопасность

- Использовать только демонстрационные данные.
- Не публиковать пароли, токены, cookies или значения секретных переменных окружения.
- Бесплатная PostgreSQL-база Render по ранее проверенной настройке требовала решения о продлении/переносе до 12 ноября 2026 г.
- Учебный проект не следует считать production-ready без отдельной проверки аутентификации, авторизации, безопасности и резервного копирования.
