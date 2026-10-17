# Скриншоты GameHub

Изображения ниже доступны как GitHub-вложения, а не как отдельные PNG-файлы в репозитории.

## Frontend: до и после исправления

### GH-FE-002-console-error.png - до исправления

В Console была ошибка `$(...).forEach is not a function`.

<img alt="GH-FE-002-console-error - ошибка JavaScript до исправления" src="https://github.com/user-attachments/assets/66f72233-875c-4de8-8943-dffa22ff4735" />

### GH-FE-001-network-before-fix.png - вкладка Network

Фильтр `api` показывал 0 совпадений из 26 запросов. Это само по себе не доказывает, что API-запросы не выполнялись.

<img alt="GH-FE-001-network-before-fix - Network до исправления" src="https://github.com/user-attachments/assets/c3d6f48c-6af9-4626-88b5-cd816b7646f8" />

### GH-BUG-006-after-fix.png - после исправления

На экране видны 64 игрока, 6 команд, 5 матчей и результат поиска `abc` - `ABCPOG`. Скриншот относится к баг-репорту GH-BUG-004.

<img alt="GH-BUG-006-after-fix - GameHub после исправления" src="https://github.com/user-attachments/assets/dec8d4ae-0fb5-4bf3-a500-123f83a59490" />

## PostgreSQL и Render

### GH-DB-015-postgres-connect.png - статус базы

<img alt="GH-DB-015-postgres-connect - PostgreSQL в Render" src="https://github.com/user-attachments/assets/07dc29a1-7cf2-460f-9900-5c50e2051dc5" />

### GH-DB-017-environment.png - переменные окружения

Перед публикацией проверь, что значения секретов замаскированы.

<img alt="GH-DB-017-environment - Environment Render" src="https://github.com/user-attachments/assets/96403648-8967-4517-b6d6-2006874614ab" />

### GH-DB-018-postgres-deploy.png - деплой

На момент скриншота Render был Live на ветке `feature/postgres-persistence`, commit `b13e037`.

<img alt="GH-DB-018-postgres-deploy - Render deployment" src="https://github.com/user-attachments/assets/e9eb3597-14ba-49ec-ad57-e1fd570ce35d" />

## Чего не хватает

Нет отдельного скриншота точного JSON-ответа `/api/players`, финальной Console после исправления и ошибки Service Worker `Response body is already used`. Не добавлять фиктивные доказательства.

## Связанные документы

- [Баг-репорты](../BUG_REPORTS.md)
- [Тест-кейсы](../TEST_CASES.md)
- [Регрессионный чек-лист](../REGRESSION_CHECKLIST.md)
- [История работы](../ACTION_HISTORY.md)

Не публиковать пароли, токены, cookies, персональные данные или открытые значения секретных переменных Render.
