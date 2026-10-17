# GameHub QA - реестр скриншотов и доказательств

Скриншоты ниже доступны как GitHub attachments, встроенные в этот документ. Это не отдельные PNG-файлы, закоммиченные по указанным именам. Если нужен именно файл в дереве репозитория, его нужно загрузить отдельно через GitHub **Add file → Upload files**.

## 1. Дефект frontend: до и после исправления

### GH-FE-002-console-error.png - до исправления
**Назначение:** доказательство ошибки JavaScript `$(...).forEach is not a function` в Console.

<img alt="GH-FE-002-console-error - ошибка JavaScript до исправления" src="https://github.com/user-attachments/assets/66f72233-875c-4de8-8943-dffa22ff4735" />

### GH-FE-001-network-before-fix.png - диагностика Network
**Назначение:** снимок Network до исправления. По нему нельзя утверждать, что API-запросы не выполнялись: фильтр `api` показывал 0 совпадений из 26 запросов.

<img alt="GH-FE-001-network-before-fix - Network до исправления" src="https://github.com/user-attachments/assets/c3d6f48c-6af9-4626-88b5-cd816b7646f8" />

### GH-BUG-006-after-fix.png - после исправления
**Назначение:** подтверждение результата после исправления. На экране видны 64 игрока, 6 команд, 5 матчей и результат поиска `abc` - `ABCPOG`. Этот файл относится к баг-репорту **GH-BUG-004**; имя сохранено в соответствии с ранее согласованным названием.

<img alt="GH-BUG-006-after-fix - GameHub после исправления" src="https://github.com/user-attachments/assets/dec8d4ae-0fb5-4bf3-a500-123f83a59490" />

## 2. PostgreSQL и Render

### GH-DB-015-postgres-connect.png - база данных
**Назначение:** статус PostgreSQL в Render. Не публиковать сам Internal Database URL.

<img alt="GH-DB-015-postgres-connect - PostgreSQL в Render" src="https://github.com/user-attachments/assets/07dc29a1-7cf2-460f-9900-5c50e2051dc5" />

### GH-DB-017-environment.png - переменные окружения
**Назначение:** наличие переменных окружения сервиса. Перед публикацией убедиться, что значения секретов замаскированы.

<img alt="GH-DB-017-environment - Environment Render" src="https://github.com/user-attachments/assets/96403648-8967-4517-b6d6-2006874614ab" />

### GH-DB-018-postgres-deploy.png - успешный деплой
**Назначение:** Render Live на ветке `feature/postgres-persistence`, commit `b13e037` на момент скриншота.

<img alt="GH-DB-018-postgres-deploy - Render deployment" src="https://github.com/user-attachments/assets/e9eb3597-14ba-49ec-ad57-e1fd570ce35d" />

## 3. Какие доказательства отсутствуют

В доступном наборе нет отдельного скриншота точного JSON-ответа `/api/players`, отдельного финального Console после исправления или Console с ошибкой `Response body is already used`. Не создавать для них фиктивные файлы и не отмечать их как приложенные.

## 4. Связанные документы

- [Баг-репорты](../BUG_REPORTS.md)
- [Тест-кейсы](../TEST_CASES.md)
- [Чек-лист регрессии](../REGRESSION_CHECKLIST.md)
- [Хронология действий](../ACTION_HISTORY.md)

## 5. Безопасность

Не публиковать пароли, токены, cookies, реальные персональные данные или открытые значения секретных переменных Render.
