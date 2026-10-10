from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy import text
from app.config import FRONTEND_PATH, BOT_TOKEN, BOT_USERNAME
from app.db.session import get_engine
from app.api import auth, users, trips, chats, reviews
from app.integrations.telegram import payments

@asynccontextmanager
async def lifespan(app):
    # Migrations run explicitly before API startup. No network calls to Telegram.
    yield
    get_engine().dispose()

OPENAPI_TAGS = [
    {'name': 'Авторизация', 'description': 'Вход, аккаунты, сессии и привязка Telegram.'},
    {'name': 'Профиль и онбординг', 'description': 'Правила, регистрация профиля и пользователи.'},
    {'name': 'Поездки', 'description': 'Каталог, создание поездок и управление участием.'},
    {'name': 'Заявки', 'description': 'Заявки на участие и решения автора поездки.'},
    {'name': 'Чаты', 'description': 'Участники, сообщения и реакции.'},
    {'name': 'Отзывы', 'description': 'Отзывы после поездки.'},
    {'name': 'Модерация', 'description': 'Блокировки и жалобы на пользователей и сообщения.'},
    {'name': 'Платежи', 'description': 'Продвижение поездок через Telegram Stars.'},
    {'name': 'Система', 'description': 'Конфигурация клиента и проверка доступности базы.'},
]

app = FastAPI(title='Travel Friends', lifespan=lifespan, openapi_tags=OPENAPI_TAGS)
for router, tag in (
    (auth.router, 'Авторизация'),
    (users.router, 'Профиль и онбординг'),
    (trips.router, 'Поездки'),
    (chats.router, 'Чаты'),
    (reviews.router, 'Отзывы'),
    (payments.router, 'Платежи'),
):
    # Explicit operation tags take precedence over the router's default section.
    for route in router.routes:
        if not route.tags:
            route.tags = [tag]
    app.include_router(router)

@app.get('/', include_in_schema=False)
def index(): return FileResponse(FRONTEND_PATH)

@app.get('/api/config', tags=['Система'])
def config(): return {'bot': BOT_USERNAME, 'telegram_enabled': bool(BOT_TOKEN)}

@app.get('/health', tags=['Система'])
def health():
    with get_engine().connect() as connection: connection.execute(text('select 1'))
    return {'status':'ok'}

@app.middleware('http')
async def limit_auth(request, call_next):
    if request.method=='POST' and request.url.path in {'/api/auth/register','/api/auth/login','/api/auth/telegram'}:
        from starlette.concurrency import run_in_threadpool
        from app.services.auth_limit_service import allow_auth_attempt
        address = request.client.host if request.client else 'unknown'
        if not await run_in_threadpool(allow_auth_attempt,address,request.url.path):
            return JSONResponse({'detail':'slow'},status_code=429,headers={'Retry-After':'60'})
    return await call_next(request)
