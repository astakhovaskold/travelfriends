import os, json, hmac, hashlib, sqlite3, time, asyncio
from urllib.parse import parse_qsl
from contextlib import asynccontextmanager

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import (Message, PreCheckoutQuery, LabeledPrice, WebAppInfo,
                           InlineKeyboardMarkup, InlineKeyboardButton, MenuButtonWebApp)

TOKEN = os.environ["BOT_TOKEN"]          # токен от @BotFather
WEBAPP_URL = os.environ["WEBAPP_URL"]    # адрес твоего сайта (https://...)
BOOST_STARS = int(os.getenv("BOOST_STARS", "50"))  # цена поднятия поездки в Stars
DB = os.getenv("DB_PATH", "data.db")

bot = Bot(TOKEN)
dp = Dispatcher()


# ---------- база данных ----------
def db():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c


def init_db():
    with db() as c:
        c.executescript("""
        create table if not exists users(
            id integer primary key, name text, username text, city text default '', about text default '');
        create table if not exists trips(
            id integer primary key autoincrement, user_id integer, dest text, date_from text, date_to text,
            people integer, budget text, note text, boosted_until integer default 0, created integer);
        create table if not exists joins(
            trip_id integer, user_id integer, created integer, primary key(trip_id, user_id));
        """)


# ---------- проверка, что запрос пришёл из Телеграма ----------
def auth(init_data: str) -> dict:
    data = dict(parse_qsl(init_data, keep_blank_values=True))
    got = data.pop("hash", "")
    check = "\n".join(f"{k}={v}" for k, v in sorted(data.items()))
    secret = hmac.new(b"WebAppData", TOKEN.encode(), hashlib.sha256).digest()
    ok = hmac.compare_digest(hmac.new(secret, check.encode(), hashlib.sha256).hexdigest(), got)
    if not ok or time.time() - int(data.get("auth_date", 0)) > 86400:
        raise HTTPException(401, "Открой приложение через бота в Телеграме")
    u = json.loads(data["user"])
    with db() as c:
        c.execute("""insert into users(id,name,username) values(?,?,?)
                     on conflict(id) do update set name=excluded.name, username=excluded.username""",
                  (u["id"], u.get("first_name", ""), u.get("username")))
    return u


# ---------- бот ----------
@dp.message(CommandStart())
async def start(m: Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="Открыть Travel Friends", web_app=WebAppInfo(url=WEBAPP_URL))]])
    await m.answer("Находи попутчиков и публикуй свои поездки.", reply_markup=kb)


@dp.pre_checkout_query()
async def pre_checkout(q: PreCheckoutQuery):
    await q.answer(ok=True)


@dp.message(F.successful_payment)
async def paid(m: Message):
    trip_id = int(m.successful_payment.invoice_payload.split(":")[1])
    with db() as c:
        c.execute("update trips set boosted_until=? where id=? and user_id=?",
                  (int(time.time()) + 7 * 86400, trip_id, m.from_user.id))
    await m.answer("Готово: поездка неделю будет вверху ленты.")


# ---------- приложение ----------
@asynccontextmanager
async def lifespan(app):
    init_db()
    await bot.set_chat_menu_button(menu_button=MenuButtonWebApp(
        text="Открыть", web_app=WebAppInfo(url=WEBAPP_URL)))
    task = asyncio.create_task(dp.start_polling(bot))
    yield
    task.cancel()


app = FastAPI(lifespan=lifespan)


@app.get("/")
def index():
    return FileResponse("index.html")


class Trip(BaseModel):
    dest: str
    date_from: str
    date_to: str
    people: int = 1
    budget: str = ""
    note: str = ""


class Profile(BaseModel):
    city: str = ""
    about: str = ""


@app.get("/api/me")
def me(x_init_data: str = Header("")):
    u = auth(x_init_data)
    with db() as c:
        return dict(c.execute("select * from users where id=?", (u["id"],)).fetchone())


@app.post("/api/profile")
def save_profile(p: Profile, x_init_data: str = Header("")):
    u = auth(x_init_data)
    with db() as c:
        c.execute("update users set city=?, about=? where id=?", (p.city[:60], p.about[:500], u["id"]))
    return {"ok": True}


@app.get("/api/trips")
def trips(q: str = "", x_init_data: str = Header("")):
    u = auth(x_init_data)
    now = int(time.time())
    with db() as c:
        rows = c.execute("""
            select t.*, u.name, u.city, (t.boosted_until > ?) as boosted
            from trips t join users u on u.id = t.user_id
            where t.dest like ? order by boosted desc, t.id desc limit 50""",
                         (now, f"%{q}%")).fetchall()
    return [{**dict(r), "mine": r["user_id"] == u["id"]} for r in rows]


@app.post("/api/trips")
def create_trip(t: Trip, x_init_data: str = Header("")):
    u = auth(x_init_data)
    if not t.dest.strip():
        raise HTTPException(400, "Укажи, куда едешь")
    with db() as c:
        c.execute("""insert into trips(user_id,dest,date_from,date_to,people,budget,note,created)
                     values(?,?,?,?,?,?,?,?)""",
                  (u["id"], t.dest.strip()[:80], t.date_from, t.date_to,
                   max(1, min(t.people, 20)), t.budget[:40], t.note[:500], int(time.time())))
    return {"ok": True}


@app.post("/api/trips/{trip_id}/join")
async def join(trip_id: int, x_init_data: str = Header("")):
    u = auth(x_init_data)
    with db() as c:
        trip = c.execute("select * from trips where id=?", (trip_id,)).fetchone()
        if not trip:
            raise HTTPException(404, "Поездка не найдена")
        if trip["user_id"] == u["id"]:
            raise HTTPException(400, "Это твоя поездка")
        added = c.execute("insert or ignore into joins values(?,?,?)",
                          (trip_id, u["id"], int(time.time()))).rowcount
    if added:
        link = f"https://t.me/{u['username']}" if u.get("username") else f"tg://user?id={u['id']}"
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Написать", url=link)]])
        await bot.send_message(trip["user_id"],
                               f"{u.get('first_name', 'Кто-то')} хочет поехать с тобой: {trip['dest']}",
                               reply_markup=kb)
    return {"ok": True}


@app.post("/api/trips/{trip_id}/boost")
async def boost(trip_id: int, x_init_data: str = Header("")):
    u = auth(x_init_data)
    with db() as c:
        trip = c.execute("select * from trips where id=? and user_id=?", (trip_id, u["id"])).fetchone()
    if not trip:
        raise HTTPException(404, "Поездка не найдена")
    link = await bot.create_invoice_link(
        title="Поднять поездку", description=f"{trip['dest']}: неделя вверху ленты",
        payload=f"boost:{trip_id}", currency="XTR",
        prices=[LabeledPrice(label="Поднять на 7 дней", amount=BOOST_STARS)])
    return {"link": link}
