# Travel Friends

FastAPI backend для Telegram Mini App, обычного сайта и будущего мобильного клиента. Общие пользователи и PostgreSQL;
Telegram — отдельная интеграция. Исходный HTML сохранён без изменений в `frontend/legacy/index.html`. Новый клиент —
SolidJS + TypeScript + Tailwind; хостится отдельно от API.

Документация для дальнейшей работы: [обзор проекта](docs/PROJECT_STATE.md), [план миграции frontend](docs/FRONTEND_MIGRATION.md), [индекс docs](docs/README.md).

## Frontend: разработка, сборка и проверка

```sh
npm --prefix frontend ci
npm --prefix frontend run dev
# Vite: http://127.0.0.1:5173/, API proxy → localhost:8000
npm --prefix frontend run typecheck
npm --prefix frontend run test
npm --prefix frontend run build
```

Frontend собирается в `frontend/dist` и размещается на отдельном статическом хостинге.
FastAPI обслуживает только API, `/docs` и `/health`.
Локально Vite проксирует `/api` на backend; production-сборка использует `VITE_API_URL`.

## Production: Railway + Neon + отдельный frontend

Backend-сервис Railway: корень репозитория `/`, config `/railway.json`.
Docker собирает только backend с production-зависимостями. Railway запускает API на `$PORT`,
проверяет `/health` (включая соединение с базой) и выполняет Alembic перед деплоем.
Один API worker и одна реплика сохраняют поведение ограничителей в памяти.

В Variables backend-сервиса перенесите значения существующего Neon из `.env.production`:

- `DATABASE_URL` — существующий pooled URL Neon.
- `MIGRATION_DATABASE_URL` — direct URL **той же базы** Neon для Alembic.
- Сохраните параметры `sslmode` и `channel_binding` в обоих URL.
- `WEBAPP_URL=https://your-frontend.example` — публичный адрес фронтенда для Telegram.
- `CORS_ORIGINS=https://your-frontend.example` — разрешённый origin без пути;
  несколько доменов разделяются запятыми.
- `BOT_TOKEN`, `BOT_USERNAME`, `ADMIN_ID` — при использовании Telegram.
- `FORWARDED_ALLOW_IPS` — доверенные адреса proxy, видимые Uvicorn.

Новая база не создаётся. Секреты задаются в Railway Variables, не в `railway.json`;
локальные `.env.production` и `.env.neon` не входят в Docker image.
Pre-deploy применяет миграции к указанной базе Neon; проверьте её адрес перед первым деплоем.
При ошибке миграции Railway не запускает новый deployment.

На хостинге фронтенда задайте корень `frontend`, команду сборки `npm ci && npm run build`,
каталог результата `dist` и build-переменную `VITE_API_URL=https://your-api.up.railway.app`
(без `/api`). Это публичный адрес, не секрет; изменение требует пересборки.
Добавьте origin этого хостинга в `CORS_ORIGINS` backend-сервиса.

Telegram bot-worker при необходимости запускается отдельным сервисом:
`python -m app.worker`. Не применяйте к нему API start command и `/health` из `railway.json`;
миграции выполняет API-сервис. Для токена должен работать один polling-процесс.

```sh
cd frontend
npx playwright install chromium webkit
npm run test:baseline # оригинальный HTML → эталонные изображения
npm run test:visual   # Solid → сравнение с эталонами без их обновления
npm run test:webkit   # сценарии на движке Safari
```

Тесты используют Telegram/API-заглушки, фиксированные дату и данные, локальные шрифты.
В CI сравнение выполняется в закреплённом Linux-контейнере Playwright; локальные macOS-эталоны
хранятся отдельно. Подробности и ограничения: [миграция frontend](docs/FRONTEND_MIGRATION.md).
Email-вход и самостоятельный браузерный клиент в эту миграцию не входят.

## Локальный запуск без Docker

Рекомендуемый вариант для разработки — Postgres.app и база `travelfriends_db`.

```sh
cp .env.local.example .env.local
# При необходимости укажите своего PostgreSQL-пользователя в DATABASE_URL.
.venv/bin/alembic -c backend/alembic.ini upgrade head
.venv/bin/uvicorn app.main:app --app-dir backend --reload
```

Backend автоматически читает `.env.local`; переменные процесса имеют приоритет. Секретные `.env.local` и `.env.neon` исключены из Git. Для выбора другого файла используется `ENV_FILE`.

Neon подключается существующим драйвером psycopg: приложение использует pooled URL, Alembic — `MIGRATION_DATABASE_URL` с direct URL. TLS и channel binding сохраняются.

```sh
# Проверка миграции без изменения схемы:
ENV_FILE=.env.neon .venv/bin/alembic -c backend/alembic.ini current
# Запуск API с Neon (после отдельного применения миграций):
ENV_FILE=.env.neon .venv/bin/uvicorn app.main:app --app-dir backend --reload
```

Изменение локальной схемы не изменяет Neon: переключение базы делается явно через `ENV_FILE`.

Production использует локальный секретный `.env.production` с Neon: `DATABASE_URL` — pooled,
`MIGRATION_DATABASE_URL` — direct. Файл исключён из Git и Docker build context.
Перед запуском заполните публичный HTTPS `WEBAPP_URL`, при использовании Telegram —
`BOT_TOKEN` и `ADMIN_ID`; задайте доверенные IP reverse proxy в `FORWARDED_ALLOW_IPS`.
Выбор production-окружения явный (по умолчанию по-прежнему `.env.local`):

```sh
ENV_FILE=.env.production .venv/bin/alembic -c backend/alembic.ini upgrade head
ENV_FILE=.env.production .venv/bin/uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

Эти команды применяют миграции к production и запускают API; подготовка файла сама по себе
не выполняет миграции или deploy. Для контейнера передавайте настройки через
`--env-file .env.production`; файл не включается в образ.

Swagger `/docs` сгруппирован по разделам: Авторизация, Профиль и онбординг, Поездки,
Заявки, Чаты, Отзывы, Модерация, Платежи и Система.


## Запуск через Docker Compose (опционально)

```sh
cp .env.example .env
# Укажите случайный POSTGRES_PASSWORD (буквы/цифры).
docker compose up --build -d
```

API: http://localhost:8000, OpenAPI: http://localhost:8000/docs, проверка базы: `/health`.
Compose сначала ждёт PostgreSQL, затем выполняет `alembic upgrade head` и запускает API. Данные хранятся в volume `postgres_data`. API не требует токена и не запускает бота.

Для Telegram заполните `BOT_TOKEN`, `BOT_USERNAME` (без @), `WEBAPP_URL` (публичный HTTPS URL), при необходимости `ADMIN_ID`, затем:

```sh
docker compose --profile telegram up --build -d
```

Бот работает отдельным процессом. Для одного токена запускайте один bot-worker. При переносе с Render остановите прежний polling-процесс. `ADMIN_ID` — Telegram ID администратора; аргументы `/ban` и `/unban` — внутренние ID пользователей, указанные в жалобах.

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
compose.yaml
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
`.env.local`), включая подстановки `${VAR}`. Загрузка не меняет `os.environ`. Pydantic проверяет типы, положительную
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

Создание аккаунта не завершает профиль: затем нужны `/api/rules` и `/api/register` (дата рождения 18+, пол). Сессия действует 30 дней по умолчанию (`SESSION_TTL`, секунды); в БД хранится только SHA-256 токена. Пароли хранятся как scrypt с индивидуальной солью, число одновременных вычислений ограничено. Для входа/регистрации действует общий для API-процессов лимит запросов по IP в PostgreSQL.

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

## Тесты

Перед разделением исходного `main.py`: **23 теста, 92% покрытия строк**. Результат: `docs/plans/baseline-test-results.txt`.

Быстрые тесты на временной SQLite:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r backend/requirements-dev.txt
.venv/bin/python -m pytest -q
```

Полный набор на настоящем PostgreSQL:

```sh
docker compose --profile test run --rm tests
# Или против выделенной тестовой базы:
TEST_DATABASE_URL=postgresql+psycopg://user:password@localhost/test_db \
  .venv/bin/python -m pytest --cov=app --cov-report=term-missing -q
```

Каждый PostgreSQL-тест получает отдельную случайную schema; таблицы приложения не удаляются. Тесты применяют настоящую
Alembic-миграцию. Проверяются контракты API, ограничения доступа, платежи и повторная доставка charge, сессии, перенос
SQLite, lifecycle API/бота, атомарность последнего места и конкуренция принятия заявки с прямым вступлением. Telegram
вызовы заменены заглушками. GitHub Actions проверяет Ruff и запускает SQLite- и PostgreSQL-тесты с порогом покрытия 90%.
Проверяются также настройки, переводы, архитектурные границы, откат участия при ошибке записи системного сообщения и
отправка уведомления после commit.

## Локальная разработка без Docker

Настройки локальной разработки берутся из `.env.local` либо из переменных процесса. Можно переопределить их явно:

```sh
export DATABASE_URL='postgresql+psycopg://user:password@localhost/travelfriends_db'
.venv/bin/alembic -c backend/alembic.ini upgrade head
.venv/bin/uvicorn app.main:app --app-dir backend --reload
# Отдельно при необходимости:
PYTHONPATH=backend .venv/bin/python -m app.worker
```

`uvicorn main:app` из корня также поддерживается. Для временного локального запуска можно использовать `DATABASE_URL=sqlite:///data.db`, предварительно выполнив миграцию. Существующий старый SQLite-файл нужно переносить через импортер, а не накатывать новую начальную миграцию поверх него.

Публичный адрес обслуживайте через HTTPS reverse proxy. Для него задайте `FORWARDED_ALLOW_IPS` — точные доверенные IP proxy, которые видит Uvicorn внутри контейнера (при proxy на хосте это может быть IP Docker gateway). Proxy должен устанавливать `X-Forwarded-For` и `X-Forwarded-Proto`. Иначе пользователи за proxy будут делить один лимит входа. Не задавайте `*`, если к API могут обращаться недоверенные клиенты. Compose по умолчанию публикует API только на `127.0.0.1:8000`; PostgreSQL наружу не публикуется. Резервные копии PostgreSQL нужно настроить отдельно. Ограничители сообщений и паузы между уведомлениями пока хранятся в памяти API-процесса, поэтому для прежнего поведения используйте один API worker.

## Стиль Python-кода

Ruff закреплён в `backend/requirements-dev.txt`, конфигурация — в корневом `pyproject.toml`: строки до 100 символов,
двойные кавычки, сортировка импортов и базовые проверки `E4`, `E7`, `E9`, `F`, `I`. Проверки охватывают приложение,
тесты, миграции, скрипты и корневой entrypoint.

```sh
# Исправление импортов и форматирование
.venv/bin/python -m ruff check --fix .
.venv/bin/python -m ruff format .

# Те же проверки, что в CI, без изменения файлов
.venv/bin/python -m ruff check .
.venv/bin/python -m ruff format --check .
.venv/bin/python -m pytest --cov=app --cov-report=term-missing --cov-fail-under=90 -q
```

В редакторе можно включить Ruff как форматтер при сохранении. Между проверками, работой с данными и отправкой
уведомлений добавляйте смысловые пустые строки вручную; форматтер не определяет этапы сценария и не форматирует
содержимое SQL-строк.
