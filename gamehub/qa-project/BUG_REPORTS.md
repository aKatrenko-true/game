# Баг-репорты GameHub

Дата актуализации: 2026-10-13. Исторические проблемы не считать закрытыми без retest. Скриншоты: [реестр доказательств](screenshots/README.md).
## Шаблон нового дефекта
- ID / заголовок:
- Статус:
- Окружение и commit:
- Предусловия:
- Шаги:
- Фактический результат:
- Ожидаемый результат:
- Severity / Priority:
- Воспроизводимость:
- Доказательства:
- Исправление / commit:
- Retest:
- Regression:

## GH-BUG-001 - Ошибка Service Worker при обработке Response
- **Статус:** Historical / Retest required.
- **Компонент:** PWA / `gamehub/static/sw.js`.
- **Приоритет:** P2 предварительно; влияние не установлено.
- **Фактический результат:** в раннем скриншоте Console была ошибка `Failed to execute 'clone' on 'Response': Response body is already used`.
- **Ожидаемый результат:** Service Worker обрабатывает Response без повторного чтения body и необработанных исключений.
- **Влияние:** возможная проблема кэширования/обновления, не подтверждена.
- **Доказательство:** историческое наблюдение в переписке; отдельный скриншот с этой ошибкой отсутствует среди доступных файлов.
- **Retest / Regression:** Not Run.

## GH-BUG-002 - GET /api/players ранее падал из-за отсутствующей таблицы SQLite
- **Статус:** Historical / исходный сценарий не перепроверен.
- **Компонент:** Backend / SQLite initialization.
- **Приоритет:** P1.
- **Фактический результат:** исторический лог содержал `sqlite3.OperationalError: no such table: players`; health endpoint при этом отвечал успешно.
- **Ожидаемый результат:** схема создаётся до обработки запросов; endpoint возвращает массив игроков.
- **Текущее состояние:** позднее пользователь подтвердил, что API работает на текущем PostgreSQL-развёртывании. Это не подтверждает исходный SQLite-сценарий.
- **Retest:** Not Run для исходного SQLite-сценария.

## GH-BUG-003 - API-маршруты ранее возвращали Not Found
- **Статус:** Historical / пользователь подтвердил последующую работоспособность.
- **Компонент:** Deployment / API routing.
- **Приоритет:** P1.
- **Фактический результат:** ранее сообщалось о `Not Found` на `/api/players`, `/api/teams`, `/api/matches`.
- **Ожидаемый результат:** маршруты доступны и возвращают JSON-массивы.
- **Причина:** не установлена.
- **Последующее действие:** Render переключён на `feature/postgres-persistence`; пользователь сообщил, что API работает.
- **Доказательство:** [GH-DB-018-postgres-deploy.png](screenshots/README.md).
- **Ограничение:** отдельный отчёт с HTTP-кодами и ответами не сохранён.

## GH-BUG-004 - Игроки не отображались при наличии данных в API
- **Статус:** Fixed - retest confirmed by user.
- **Компонент:** Frontend / `gamehub/static/app.js`.
- **Приоритет:** P1; серьёзность Major по влиянию на каталог.
- **Предусловия:** `GET /api/players` возвращает массив.
- **Шаги:** открыть GameHub → раздел «Игроки» → проверить каталог/счётчики → открыть Console.
- **Фактический результат до исправления:** «Игроки не найдены», прочерки в статистике, ошибка `Uncaught TypeError: $(...).forEach is not a function`.
- **Ожидаемый результат:** игроки и статистика отображаются, указанная ошибка отсутствует.
- **Причина:** одиночный селектор `$("[data-go]")` использовался как коллекция.
- **Исправление:** заменён на `$$("[data-go]")`, возвращающий коллекцию элементов.
- **Retest:** пользователь подтвердил работу сайта, отображение игроков и сохранение новых записей.
- **Доказательства:** [ошибка до исправления](screenshots/README.md) и [скриншот после исправления](screenshots/README.md). На скриншоте после исправления видны 64 игрока, 6 команд, 5 матчей и результат поиска `abc` - `ABCPOG`.
- **Regression:** фильтры, навигация, команды и матчи требуют отдельного прогона.

## GH-BUG-005 - Риск публикации секретов в QA-скриншотах
- **Статус:** Preventive check; утечка не подтверждена.
- **Компонент:** QA evidence / Render environment.
- **Ожидаемый результат:** пароли, токены, cookies и значения секретных переменных не публикуются.
- **Действие:** перед коммитом проверить, что на скриншоте Environment значения замаскированы.

## GH-BUG-007 - Browser test expects CMS session to survive page reload

- **Статус:** Исправление теста внесено; CI retest in progress.
- **Компонент:** QA automation / `tests/test_cms_browser.py`.
- **Приоритет:** P1 для CI; это не подтверждённый дефект приложения.
- **Окружение:** GitHub Actions, Chromium, ветка `feature/site-cms-admin`.
- **Фактический результат:** `test_cms_section_edits_persist_after_reload` падал на ожидании видимости `#cms-app` после `page.reload()`; тайм-аут 30 секунд. До этого 7 из 8 браузерных CMS тестов прошли, а PostgreSQL job завершился успешно.
- **Ожидаемый результат:** после перезагрузки редактор требует повторную авторизацию; после ввода пароля тест проверяет, что изменения раздела сохранились.
- **Причина:** тест предполагал автоматическое сохранение авторизованного состояния, что противоречит изменению безопасности - пароль больше не хранится в `sessionStorage`.
- **Исправление:** в браузерный тест добавлен повторный ввод тестового пароля после перезагрузки, прежде чем проверять сохранённые поля.
- **Retest:** CI запущен, результат пока не подтверждён: [workflow run](https://github.com/aKatrenko-true/game/actions/runs/39034195390).
- **Доказательство:** логи GitHub Actions; отдельный скриншот не создан.
- **Связанные кейсы:** GH-CMS-AUTH-006, GH-CMS-CRUD-001…007, GH-CMS-ERR-003.


## GH-BUG-008 - CMS image URL validation before CSS interpolation
- **Статус:** Исправление внесено; CI retest ожидается.
- **Компонент:** Frontend security / `gamehub/static/cms-public.js`.
- **Severity / Priority:** Security hardening; P1 до проверки. Эксплуатация не подтверждена.
- **Предусловия:** CMS image URL сохранён в hero или настройке карточки игры.
- **Наблюдение:** hero URL попадал в CSS `backgroundImage` после замены только двойных кавычек; изображения карточек использовали другую фильтрацию. Значения из БД следует считать недоверенными при выводе в публичном UI.
- **Ожидаемый результат:** применяется только URL с разрешённой схемой и допустимым форматом; значения с кавычками, скобками, пробелами, переносами строк или неизвестной схемой не вставляются в CSS.
- **Исправление:** общий `safeImageUrl` разрешает HTTPS URL и base64 data URL поддерживаемых image MIME-типов; helper используется для hero и карточек игр.
- **Связанный тест:** `test_cms_image_urls_are_validated_before_css_background_interpolation`.
- **Доказательства:** исходный diff и CI после коммита; реальная эксплуатация не подтверждена.
- **Retest / Regression:** ожидается CI; ручной production retest Not Run.


## GH-BUG-009 - CMS appearance form can partially save settings
- **Статус:** Исправление внесено; CI retest ожидается.
- **Компонент:** CMS frontend/API / оформление.
- **Severity / Priority:** Major / P1: при сетевой или валидационной ошибке последовательные запросы могли сохранить часть настроек и оставить остальные старыми.
- **Предусловия:** администратор открыт на вкладке «Оформление».
- **Фактический результат до исправления:** форма отправляла отдельный PUT на каждый ключ; ошибка посреди цикла оставляла частично сохранённое состояние.
- **Ожидаемый результат:** весь набор настроек валидируется до записи; при невалидном значении ничего из отправленного набора не меняется.
- **Исправление:** добавлен `PUT /api/admin/cms/settings` с предварительной валидацией всего набора и записью в одной DB-транзакции; форма отправляет один запрос.
- **Связанные тесты:** `test_cms_bulk_settings_validates_all_values_before_writing`, `test_cms_bulk_settings_requires_admin_and_rejects_unknown_keys`, `test_cms_appearance_form_uses_single_bulk_settings_request`.
- **Retest / Regression:** CI ожидается; production retest Not Run.


## Findings from repository review - candidates for targeted verification

These items are not reported as reproduced runtime defects. They are review findings that need a focused test before changing their status.

### GH-RISK-001 - No application-level rate limiting visible on authentication endpoints
- **Status:** Code-review finding; runtime abuse scenario Not Run.
- **Component:** Backend / registration and login.
- **Priority:** P1 candidate; confirm exposure and existing edge protection before final severity.
- **Observation:** The reviewed application code does not show an application-level rate limiter around registration/login and shared-password CMS admin authentication.
- **Risk:** Repeated requests may consume resources or allow password-guessing attempts if no trusted upstream control exists.
- **Verification:** Inspect deployment-level rate limiting; in a local test environment, send a controlled burst of invalid attempts and record status codes, response behavior, and logs. Do not perform load or brute-force testing against production.
- **Expected result:** Repeated attempts are throttled with a documented response and without locking out unrelated users.
- **Evidence:** Capture only after a real controlled run. No synthetic screenshot should be treated as runtime evidence.
- **Retest:** Not Run.

### GH-RISK-002 - CMS content has no version history or rollback workflow
- **Status:** Product/recovery limitation from repository review; not a runtime defect.
- **Component:** CMS / content recovery.
- **Priority:** P1 candidate for production operations; impact depends on content criticality.
- **Observation:** The reviewed CMS flow does not provide draft/version history/one-click rollback.
- **Risk:** A mistaken save may immediately affect public content and require manual restoration.
- **Verification:** Confirm current UI and API behavior; test whether previous content can be restored using documented backup/recovery procedures.
- **Expected result:** A documented recovery path exists and has been exercised, or the limitation is explicitly accepted.
- **Evidence:** Attach real UI/API/restore evidence only after execution.
- **Retest:** Not Run.

### GH-RISK-003 - CMS images are stored as base64 data URLs in the database
- **Status:** Architecture/operations risk; not a confirmed defect.
- **Component:** CMS media storage and database backups.
- **Priority:** P2 candidate; assess actual payload limits, database growth and backup strategy.
- **Observation:** Supported image data URLs can be persisted as CMS setting values.
- **Risk:** Base64 media increases database and backup size; media recovery depends on database recovery.
- **Verification:** Measure representative image payload size, check configured request/body limits and verify backup/restore behavior in a non-production environment.
- **Expected result:** Limits and recovery behavior are documented and tested.
- **Evidence:** Use measured payloads and actual backup/restore logs; do not invent measurements.
- **Retest:** Not Run.
