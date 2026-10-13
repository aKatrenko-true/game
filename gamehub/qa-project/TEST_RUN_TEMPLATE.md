# Отчёт о тестировании GameHub — шаблон

## 1. Информация о прогоне
- **Run ID:** GH-TR-YYYY-MM-DD-01
- **Дата/время:**
- **Стенд:** local / Render
- **URL:**
- **Ветка / commit:**
- **Браузер / ОС / viewport:**
- **Тип:** smoke / functional / API / regression / responsive / PWA
- **Изменение:**

## 2. Сводка
- Всего кейсов:
- Pass:
- Fail:
- Blocked:
- Not Run:
- Открытые P0/P1:
- **Итог:** Not evaluated / Ready with risks / Not Ready

## 3. Результаты
| Test ID | Статус | Фактический результат | Bug ID | Доказательство |
|---|---|---|---|---|
| GH-SM-001 | Not Run | — | — | — |
| GH-SM-002 | Not Run | — | — | — |
| GH-API-001 | Not Run | — | — | — |

Статусы: **Pass** — совпадает с ожиданием; **Fail** — не совпадает; **Blocked** — невозможно проверить; **Not Run** — не запускалось. **Confirmed by user** — пользователь сообщил результат, это не независимый запуск.

## 4. Retest / регрессия
| Bug ID | Исправление | Retest | Regression | Доказательство |
|---|---|---|---|---|
| GH-BUG-001 | Не подтверждено | Not Run | Not Run | — |
| GH-BUG-002 | Исторический SQLite-сценарий | Not Run | Not Run | — |
| GH-BUG-003 | Позже API подтверждён пользователем | Confirmed by user | Not Run | GH-DB-018-postgres-deploy.png |
| GH-BUG-004 | Исправлен селектор в app.js | Confirmed by user | Not Run | GH-BUG-006-after-fix.png |

## 5. Доказательства
Использовать только реальные ссылки из [реестра скриншотов](screenshots/README.md). Не указывать имя файла как приложенное доказательство, если ссылка/файл отсутствует.

## 6. Вывод
- Что проверено:
- Что не проверено:
- Открытые дефекты:
- Риски:
- Следующий шаг:
