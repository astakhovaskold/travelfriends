from app import errors
from app.api import auth, chats, reviews, trips, users
from app.config import get_settings
from app.db.session import get_engine
from app.integrations.telegram import payments
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text


@asynccontextmanager
async def lifespan(app):
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
app = FastAPI(title="Travel Friends", lifespan=lifespan, openapi_tags=OPENAPI_TAGS)
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
    app.include_router(router)
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(get_settings().CORS_ORIGINS),
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Content-Type", "Authorization", "X-Init-Data"],
)


@app.get("/api/config", tags=["Система"])
def config():
    return {"bot": get_settings().BOT_USERNAME, "telegram_enabled": bool(get_settings().BOT_TOKEN)}


@app.get("/health", tags=["Система"])
def health():
    with get_engine().connect() as connection:
        connection.execute(text("select 1"))
    return {"status": "ok"}


@app.middleware("http")
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
