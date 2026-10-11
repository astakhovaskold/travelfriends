import logging
from alembic.config import Config
from alembic.script import ScriptDirectory
from app import errors
from app.api import auth, chats, reviews, trips, users
from app.config import get_settings
from app.db.models import metadata
from app.db.session import get_engine
from app.integrations.telegram import payments
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pathlib import Path
from sqlalchemy import inspect, text
from sqlalchemy.exc import SQLAlchemyError


@asynccontextmanager
async def lifespan(app):
    logging.getLogger("uvicorn.error").info(
        "Configured CORS origins: %s", get_settings().CORS_ORIGINS
    )
    yield
    get_engine().dispose()


OPENAPI_TAGS = [
    {"name": "Авторизация", "description": "Вход, аккаунты, сессии и привязка Telegram."},
    {"name": "Профиль и онбординг", "description": "Правила, регистрация профиля и пользователи."},
    {"name": "Поездки", "description": "Каталог, создание поездок и управление участием."},
    {"name": "Заявки", "description": "Заявки на участие и решения автора поездки."},
    {"name": "Чаты", "description": "Участники, сообщения и реакции."},
    {"name": "Отзывы", "description": "Отзывы после поездки."},
    {"name": "Модерация", "description": "Блокировки и жалобы на пользователей и сообщения."},
    {"name": "Платежи", "description": "Продвижение поездок через Telegram Stars."},
    {"name": "Система", "description": "Конфигурация клиента и проверка доступности базы."},
]


def config():
    return {"bot": get_settings().BOT_USERNAME, "telegram_enabled": bool(get_settings().BOT_TOKEN)}


def health():
    try:
        with get_engine().connect() as connection:
            tables = set(inspect(connection).get_table_names())
            if not set(metadata.tables).issubset(tables) or "alembic_version" not in tables:
                return JSONResponse({"detail": "Database migrations required"}, status_code=503)
            revisions = set(
                connection.execute(text("select version_num from alembic_version")).scalars()
            )
            migration_config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
            heads = set(ScriptDirectory.from_config(migration_config).get_heads())
            if revisions != heads:
                return JSONResponse({"detail": "Database migrations required"}, status_code=503)
    except SQLAlchemyError:
        return JSONResponse({"detail": "Database unavailable"}, status_code=503)
    return {"status": "ok"}


async def limit_auth(request, call_next):
    if request.method == "POST" and request.url.path in {
        "/api/auth/register",
        "/api/auth/login",
        "/api/auth/telegram",
    }:
        from starlette.concurrency import run_in_threadpool

        from app.services.auth_limit_service import allow_auth_attempt

        address = request.client.host if request.client else "unknown"
        if not await run_in_threadpool(allow_auth_attempt, address, request.url.path):
            return JSONResponse(
                {"detail": errors.SLOW}, status_code=429, headers={"Retry-After": "60"}
            )
    return await call_next(request)


def create_app():
    application = FastAPI(title="Travel Friends", lifespan=lifespan, openapi_tags=OPENAPI_TAGS)
    for router, tag in (
            (auth.router, "Авторизация"),
            (users.router, "Профиль и онбординг"),
            (trips.router, "Поездки"),
            (chats.router, "Чаты"),
            (reviews.router, "Отзывы"),
            (payments.router, "Платежи"),
    ):
        for route in router.routes:
            if not route.tags:
                route.tags = [tag]
        application.include_router(router)
    application.middleware("http")(limit_auth)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=list(get_settings().CORS_ORIGINS),
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Content-Type", "Authorization", "X-Init-Data"],
    )

    application.get("/api/config", tags=["Система"])(config)
    application.get("/health", tags=["Система"])(health)
    return application


app = create_app()
