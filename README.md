# Travel Friends

FastAPI backend и отдельный SolidJS + TypeScript frontend. Caddy внутри frontend
раздаёт только статические файлы; API работает отдельным сервисом. Ingress не настроен.

## Полный стек через корневой Compose

`compose.yaml` запускает production-сборки frontend и API, PostgreSQL и Alembic-миграции.

```sh
cp .env.example .env
# Задайте POSTGRES_PASSWORD.
docker compose up --build -d
```

Frontend: http://localhost:8080. API: http://localhost:8000, OpenAPI: `/docs`.
API запускается после миграций, frontend — после успешной проверки схемы через `/health`.
Данные PostgreSQL сохраняются в volume. Перезапуск не удаляет данные.

Для VDS задайте `VITE_API_URL` с публичным адресом API, `WEBAPP_URL` с адресом фронта
и соответствующий origin в `CORS_ORIGINS`. Для прямого доступа извне задайте
`API_BIND_HOST=0.0.0.0` и `FRONTEND_BIND_HOST=0.0.0.0`; по умолчанию порты доступны
только через loopback. `API_PORT` и `FRONTEND_PORT` меняют опубликованные порты.
Caddy не проксирует `/api`: браузер обращается к адресу `VITE_API_URL`.
Изменение этого адреса требует пересборки frontend.

Для внешней PostgreSQL/Neon задайте `DATABASE_URL` и `MIGRATION_DATABASE_URL`;
приложение и миграции используют эти адреса вместо встроенной БД.
Встроенный db-сервис при обычном полном запуске также стартует.

Telegram bot-worker включается отдельно:

```sh
docker compose --profile telegram up --build -d
```

У API нет polling-процесса. Для одного BOT_TOKEN запускайте один bot-worker.

## Backend отдельно: разработка в Docker

```sh
docker compose --env-file /dev/null -f backend/compose.yaml up --build
# То же из backend/:
# docker compose up --build
```

Запускаются отдельная development-БД, миграции и API на http://localhost:8000.
Код backend смонтирован из рабочей директории; Uvicorn перезапускается при изменениях.
Production и development Compose имеют разные project names и volumes.
При запуске из корня --env-file /dev/null исключает случайное использование
корневого production .env. Из директории backend можно запускать docker compose напрямую.
`backend/.env.local` при наличии передаёт дополнительные настройки, например BOT_TOKEN.
DATABASE_URL по умолчанию переопределяется на БД Compose, а не на localhost контейнера.

Чтобы запустить только API с внешней БД, например Neon, выберите env-файл явно:

```sh
docker compose -f backend/compose.yaml --env-file backend/.env.neon run --rm --no-deps migrate
docker compose -f backend/compose.yaml --env-file backend/.env.neon up --build --no-deps api
```

Если PostgreSQL запущен на компьютере, в URL контейнера используйте
`host.docker.internal` вместо `localhost`. Для Linux development Compose содержит
соответствующий host-gateway mapping. При доступе к backend через host-gateway
он должен слушать доступный контейнеру интерфейс: задайте API_BIND_HOST=0.0.0.0
для backend Compose или --host 0.0.0.0 при нативном запуске.

Backend-тесты в Docker:

```sh
docker compose -f backend/compose.yaml --profile test run --rm tests
```

## Backend отдельно: запуск без Docker

Все Python-конфигурации находятся в `backend/`. Корневые `main.py`, `requirements.txt`,
`pytest.ini` и `pyproject.toml` больше не нужны.

```sh
cd backend
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
cp .env.example .env.local
# Для Postgres.app настройте DATABASE_URL и создайте travelfriends_db.
.venv/bin/alembic -c alembic.ini upgrade head
.venv/bin/uvicorn app.main:app --reload
```

Backend автоматически читает `backend/.env.local`; переменные процесса имеют приоритет.
Существующие `.env.local`, `.env.neon`, `.env.production` перенесены в `backend/`
и исключены из Git и Docker build context. Для выбора другого файла используйте ENV_FILE:

```sh
cd backend
ENV_FILE=.env.neon .venv/bin/alembic -c alembic.ini current
ENV_FILE=.env.neon .venv/bin/uvicorn app.main:app --reload
```

`DATABASE_URL` Neon — pooled URL, `MIGRATION_DATABASE_URL` — direct URL той же базы.
Сохраняйте параметры sslmode/channel_binding. Проверка `alembic current` схему не меняет.
Бот при необходимости запускается из backend отдельной командой `python -m app.worker`.

## Frontend отдельно: разработка

В Docker:

```sh
docker compose --env-file /dev/null -f frontend/compose.yaml up --build
```

Vite доступен на http://localhost:5173. `/api` проксируется на
`http://host.docker.internal:8000`: backend может работать в отдельном Compose
или напрямую на компьютере. Для другого адреса задайте `API_PROXY_TARGET`.
Для прямых браузерных запросов вместо development-прокси задайте `VITE_API_URL`.
Это прокси только Vite для разработки; production Caddy раздаёт только frontend.

Без Docker:

```sh
cd frontend
npm ci
npm run dev
npm run typecheck
npm run test
npm run build
```

Локальный Vite проксирует API на `127.0.0.1:8000`. Пример настроек — `frontend/.env.example`.
Для production-сборки на отдельном хостинге задайте
`VITE_API_URL=https://your-api.example` без `/api`; результат — `frontend/dist`.

## Railway production

Оба сервиса определены в `.railway/railway.ts`; JSON-конфиги заменены на IaC.

| Настройка      | Backend                             | Frontend            |
|----------------|-------------------------------------|---------------------|
| Сервис         | travelfriends-api                   | travelfriends-web   |
| Root Directory | /backend                            | /frontend           |
| Dockerfile     | backend/Dockerfile                  | frontend/Dockerfile |
| Процесс        | Uvicorn                             | Caddy               |
| Порт           | 8080                                | 8080                |
| Pre-deploy     | alembic -c alembic.ini upgrade head | отсутствует         |
| Healthcheck    | /health с проверкой схемы           | /health             |

Существующая Neon остаётся внешней БД; URL и Telegram-секреты сохраняются через preserve().
Локальные env-файлы не переносятся в Railway Variables автоматически.

```sh
npm --prefix .railway ci
.railway/node_modules/.bin/railway link --project travel-friends --environment production
npm --prefix .railway run plan
npm --prefix .railway run apply
```

Проверяйте план перед apply. IaC не применяется от одного push: выполняйте plan/apply,
затем deploy приложения. BOT_TOKEN нужен API для проверки Telegram initData;
polling-бот требует отдельного процесса. Для него не используйте API start/healthcheck.

## Структура

```text
backend/
  app/
    main.py                  # сборка API, lifecycle, health
    worker.py                # отдельный процесс бота
    api/                     # HTTP-контракты и зависимости авторизации
    services/                # сценарии, бизнес-проверки, общие транзакции
    repositories/            # SQL и SQLAlchemy Core через переданный Transaction
    config.py                # типизированные настройки окружения
    constants.py             # доменные значения и лимиты
    texts.py                 # тексты RU/EN и render_text
    errors.py                # стабильные машинные коды ошибок API
    integrations/telegram/   # bot, initData, Stars
    db/                      # SQLAlchemy Core schema и транзакции
    schemas/                 # Pydantic request bodies
  migrations/                # Alembic
  scripts/import_sqlite.py  # перенос старой базы
  tests/
frontend/src/                # SolidJS: app, features, API, Telegram adapter
frontend/legacy/index.html   # исходный Mini App
frontend/tests/              # Playwright и Vitest
backend/Dockerfile
backend/compose.yaml
backend/pyproject.toml
frontend/Dockerfile
frontend/compose.yaml
compose.yaml                 # полный production-стек
```

Выбраны SQLAlchemy Core и параметризованные SQL-запросы: существующая логика перенесена постепенно, без полной замены на ORM. ID пользователей — внутренние; Telegram ID хранится в `auth_identities`. У импортированных пользователей прежние числовые ID сохраняются вместе со связями.

Обработчики HTTP и Telegram передают сценарии сервисам. Сервисы проверяют бизнес-правила и открывают транзакции,
репозитории выполняют запросы через переданный `Transaction`. Репозитории не делают commit/rollback, не создают
HTTP-ошибки и не отправляют уведомления. При вступлении и принятии заявки блокировка поездки, проверка вместимости,
запись участника и системного сообщения выполняются в одной транзакции. Уведомления отправляются после её завершения.

`services/common.py` содержит только чистые функции дат и нормализации. Составные операции участия находятся в
`participation_service.py`. Сервисы не импортируют API; проверки авторизации находятся в `auth_service.py`, FastAPI
dependencies — в `api/auth.py`. Архитектурные тесты защищают эти границы.

Настройки загружаются через `get_settings()`: окружение имеет приоритет над файлом `ENV_FILE` (по умолчанию
`backend/.env.local`), включая подстановки `${VAR}`. Загрузка не меняет `os.environ`. Pydantic проверяет типы,
положительную
стоимость продвижения и TTL сессии; ошибки не выводят входные значения и секреты. Доменным лимитам и переводам
соответствуют отдельные модули. Тексты берутся через `render_text(key, lang, **params)` с английским fallback; коды
ошибок и payload системных событий сохраняют прежний формат.

## Авторизация

Прежний HTML продолжает отправлять `X-Init-Data`. Новые клиенты используют `Authorization: Bearer <access_token>`:

- `POST /api/auth/telegram` — `{"init_data":"..."}`: проверка Telegram и выдача сессии.
- `POST /api/auth/register` — `{"email":"user@example.com","password":"at-least-12-characters","name":"User"}`: независимый аккаунт.
- `POST /api/auth/login` — email и пароль.
- `POST /api/auth/logout` — отзыв текущей Bearer-сессии.
- `POST /api/auth/link/telegram` — initData + текущая Bearer-сессия: привязка свободного Telegram-аккаунта. Аккаунты разных пользователей автоматически не объединяются.

Создание аккаунта не завершает профиль: затем нужен `/api/register` с данными профиля и обязательным
`rules_accepted: true` (дата рождения 18+, пол). Backend также сохраняет старый `/api/rules` для совместимости. Сессия
действует 30 дней по умолчанию (`SESSION_TTL`, секунды); в БД хранится только SHA-256 токена. Пароли хранятся как scrypt
с индивидуальной солью, число одновременных вычислений ограничено. Для входа/регистрации действует общий для
API-процессов лимит запросов по IP в PostgreSQL.

Оба frontend пока остаются интерфейсами Telegram Mini App: отдельную форму email-входа в него не добавляли. Независимый
вход доступен через REST API. Подтверждение email, восстановление пароля и OAuth пока не реализованы. Stars доступны
пользователям с привязанным Telegram; независимый платёжный провайдер не добавлен.

## Перенос SQLite

Сначала сделайте резервную копию старого `data.db` и остановите запись в старое приложение. Целевая база должна быть пустой и с применённой миграцией. Исходный файл открывается только для чтения; перенос выполняется одной транзакцией. Импортер сохраняет ID и обновляет PostgreSQL sequences.

```sh
docker compose up -d db
docker compose run --rm migrate
docker compose run --rm -v /absolute/path/backup.db:/backup/data.db:ro api \
  python -m scripts.import_sqlite /backup/data.db
```

Проверьте итоговые количества строк перед переключением сервиса. Если в старой базе есть ссылки на отсутствующих пользователей/поездки/сообщения, перенос остановится с названиями таблиц и ID. Исправляйте только копию backup согласно выбранному решению (например, удаление устаревшей блокировки после проверки); строки автоматически не удаляются. Повторный импорт в непустую базу запрещён.

## Проверки

Из backend/:

```sh
.venv/bin/python -m ruff check .
.venv/bin/python -m ruff format --check .
.venv/bin/python -m pytest -q
```

PostgreSQL-тесты используют отдельные случайные schema и не удаляют таблицы приложения:

```sh
TEST_DATABASE_URL=postgresql+psycopg://user:password@localhost/test_db \
  .venv/bin/python -m pytest --cov=app --cov-report=term-missing -q
```

Frontend-проверки из frontend/:

```sh
npm run check
npm run typecheck
npm run test
npm run build
npm run test:production
```

Playwright production-проверки используют статическую сборку через Vite preview.
Telegram/API-запросы подменяются заглушками; production-секреты им не нужны.

При ошибке `relation "auth_limits" does not exist` проверьте применение миграций
к базе API. `/health` возвращает 503 для пустой/неполной схемы или устаревшей Alembic-версии.
При CORS error проверьте `Configured CORS origins` в startup-логах backend и его Variables.
Изменение CORS_ORIGINS требует перезапуска backend.
