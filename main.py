import os, json, hmac, hashlib, sqlite3, time, asyncio, datetime
from typing import Optional, List
from urllib.parse import parse_qsl
from contextlib import asynccontextmanager

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, Command, CommandObject
from aiogram.types import (Message, PreCheckoutQuery, LabeledPrice, WebAppInfo,
                           InlineKeyboardMarkup, InlineKeyboardButton, MenuButtonWebApp)

TOKEN = os.environ["BOT_TOKEN"]          # токен от @BotFather
WEBAPP_URL = os.environ["WEBAPP_URL"]    # адрес твоего сайта (https://...)
BOOST_STARS = int(os.getenv("BOOST_STARS", "50"))        # цена поднятия поездки в Stars
ADMIN_ID = int(os.getenv("ADMIN_ID", "0") or 0)          # твой Telegram id: жалобы и команды /ban /unban /stats
DB = os.getenv("DB_PATH", "data.db")                     # для постоянного хранения укажи путь на диске, например /data/data.db
MAX_ACTIVE = 5                                           # сколько активных поездок можно держать одновременно
TAGS = {"reliable", "fun", "respectful", "organized", "punctual", "late", "rude"}
KINDS = ("flight", "train", "road", "hike", "plan", "other")
VIBES = {"early", "nature", "night", "museums", "spontaneous", "planner", "food", "photo", "active", "chill"}
GENDERS = ("f", "m", "x")

PINGED = {}
FLOOD = {}
BOT_USER = ""

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
        create table if not exists messages(
            id integer primary key autoincrement, trip_id integer, user_id integer, text text, created integer);
        create table if not exists reports(msg_id integer, reporter integer, created integer);
        create table if not exists reviews(
            id integer primary key autoincrement, trip_id integer, from_id integer, to_id integer,
            stars integer, tags text default '', text text default '', created integer,
            unique(trip_id, from_id, to_id));
        create table if not exists blocks(user_id integer, blocked_id integer, primary key(user_id, blocked_id));
        create table if not exists kicked(trip_id integer, user_id integer, primary key(trip_id, user_id));
        create table if not exists reactions(
            msg_id integer, user_id integer, emoji text, primary key(msg_id, user_id, emoji));
        create table if not exists requests(
            trip_id integer, user_id integer, status text default 'pending', created integer,
            primary key(trip_id, user_id));
        """)
        for col in ("alter table users add column lang text default 'ru'",
                    "alter table users add column rules_ok integer default 0",
                    "alter table users add column birth text",
                    "alter table users add column registered integer default 0",
                    "alter table users add column banned integer default 0",
                    "alter table users add column minor integer default 0",
                    "alter table users add column gender text default ''",
                    "alter table users add column vibe text default ''",
                    "alter table trips add column audience text default 'all'",
                    "alter table trips add column min_age integer default 0",
                    "alter table trips add column max_age integer default 0",
                    "alter table trips add column approval integer default 0",
                    "alter table trips add column kind text default 'flight'",
                    "alter table trips add column country text default ''",
                    "alter table trips add column lat real",
                    "alter table trips add column lon real",
                    "alter table trips add column chat_open integer default 0",
                    "alter table trips add column closed integer default 0",
                    "alter table trips add column prompted integer default 0"):
            try:
                c.execute(col)
            except sqlite3.OperationalError:
                pass


def today():
    return datetime.date.today().isoformat()


def trip_end(r):
    e = r["date_to"] or r["date_from"]
    if e:
        return e
    return (datetime.date.fromtimestamp(r["created"]) + datetime.timedelta(days=30)).isoformat()


def is_ended(r):
    return trip_end(r) < today()


def age_of(birth):
    if not birth:
        return None
    try:
        b = datetime.date.fromisoformat(birth)
    except ValueError:
        return None
    t = datetime.date.today()
    return t.year - b.year - ((t.month, t.day) < (b.month, b.day))


def clean_vibe(items):
    return ",".join(v for v in dict.fromkeys(items or []) if v in VIBES)


def add_member(c, trip_id, uid):
    name = c.execute("select name from users where id=?", (uid,)).fetchone()["name"]
    c.execute("insert or ignore into joins values(?,?,?)", (trip_id, uid, int(time.time())))
    c.execute("update trips set chat_open=1 where id=?", (trip_id,))
    sysmsg(c, trip_id, f"join:{name}")
    return name


def lang_of(code):
    return "ru" if (code or "") in ("ru", "uk", "be", "kk") else "en"


def stats(c, uid):
    r = c.execute("select round(avg(stars),1) a, count(*) n from reviews where to_id=?", (uid,)).fetchone()
    done = 0
    for t in c.execute("""select t.*, (select count(*) from joins j where j.trip_id=t.id) as m
                          from trips t where t.user_id=?""", (uid,)):
        if t["m"] > 0 and is_ended(t):
            done += 1
    for t in c.execute("select t.* from joins j join trips t on t.id=j.trip_id where j.user_id=?", (uid,)):
        if is_ended(t):
            done += 1
    fr = c.execute("""select count(distinct o) from (
        select j2.user_id o from joins j join joins j2 on j2.trip_id=j.trip_id and j2.user_id!=j.user_id where j.user_id=?
        union select t.user_id from joins j join trips t on t.id=j.trip_id where j.user_id=? and t.user_id!=?
        union select j.user_id from trips t join joins j on j.trip_id=t.id where t.user_id=? and j.user_id!=?)""",
                   (uid, uid, uid, uid, uid)).fetchone()[0]
    return {"avg": r["a"], "cnt": r["n"], "trips": done, "friends": fr}


def people(c, trip_id):
    return c.execute("""select u.id, u.lang, u.name from users u
                        where u.id=(select user_id from trips where id=?)
                        union select u.id, u.lang, u.name from joins j join users u on u.id=j.user_id
                        where j.trip_id=?""", (trip_id, trip_id)).fetchall()


def blocked_pair(c, a, b):
    return c.execute("""select 1 from blocks where (user_id=? and blocked_id=?)
                        or (user_id=? and blocked_id=?)""", (a, b, b, a)).fetchone()


def sysmsg(c, trip_id, text):
    c.execute("insert into messages(trip_id,user_id,text,created) values(?,0,?,?)",
              (trip_id, text, int(time.time())))


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
        c.execute("""insert into users(id,name,username,lang) values(?,?,?,?)
                     on conflict(id) do update set name=excluded.name, username=excluded.username, lang=excluded.lang""",
                  (u["id"], u.get("first_name", ""), u.get("username"), lang_of(u.get("language_code"))))
        r = c.execute("select banned, minor from users where id=?", (u["id"],)).fetchone()
    if r["banned"]:
        raise HTTPException(403, "banned")
    if r["minor"]:
        raise HTTPException(403, "minor")
    return u


def need_ready(u):
    with db() as c:
        r = c.execute("select rules_ok, registered from users where id=?", (u["id"],)).fetchone()
    if not r["rules_ok"]:
        raise HTTPException(403, "rules")
    if not r["registered"]:
        raise HTTPException(403, "register")


def open_kb(trip_id, ru, kind="chat"):
    url = f"{WEBAPP_URL}?{kind}={trip_id}"
    text = {"chat": ("Открыть чат", "Open chat"), "rate": ("Оценить попутчиков", "Rate your buddies"),
            "trip": ("Открыть поездку", "Open trip"), "req": ("Посмотреть заявки", "View requests")}[kind]
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(
        text=text[0] if ru else text[1], web_app=WebAppInfo(url=url))]])


async def safe_send(uid, text, kb=None):
    try:
        await bot.send_message(uid, text, reply_markup=kb)
    except Exception:
        pass


# ---------- бот ----------
@dp.message(CommandStart())
async def start(m: Message, command: CommandObject):
    ru = lang_of(m.from_user.language_code) == "ru"
    arg = command.args or ""
    url = WEBAPP_URL
    if arg.startswith("trip_") and arg[5:].isdigit():
        url = f"{WEBAPP_URL}?trip={arg[5:]}"
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(
        text="Открыть Travel Friends" if ru else "Open Travel Friends", web_app=WebAppInfo(url=url))]])
    await m.answer("Находи попутчиков и публикуй свои поездки." if ru
                   else "Find travel buddies and post your trips.", reply_markup=kb)


def is_admin(m: Message):
    return bool(ADMIN_ID) and m.from_user.id == ADMIN_ID


@dp.message(Command("ban"))
async def cmd_ban(m: Message, command: CommandObject):
    if not is_admin(m):
        return
    if not (command.args or "").strip().isdigit():
        await m.answer("/ban <user id>")
        return
    with db() as c:
        c.execute("update users set banned=1 where id=?", (int(command.args),))
    await m.answer("Banned " + command.args)


@dp.message(Command("unban"))
async def cmd_unban(m: Message, command: CommandObject):
    if not is_admin(m):
        return
    if not (command.args or "").strip().isdigit():
        await m.answer("/unban <user id>")
        return
    with db() as c:
        c.execute("update users set banned=0 where id=?", (int(command.args),))
    await m.answer("Unbanned " + command.args)


@dp.message(Command("stats"))
async def cmd_stats(m: Message):
    if not is_admin(m):
        return
    with db() as c:
        q = lambda s: c.execute(s).fetchone()[0]
        await m.answer(f"Users: {q('select count(*) from users where registered=1')}\n"
                       f"Trips: {q('select count(*) from trips')}\n"
                       f"Joins: {q('select count(*) from joins')}\n"
                       f"Messages: {q('select count(*) from messages where user_id>0')}\n"
                       f"Reviews: {q('select count(*) from reviews')}\n"
                       f"Reports: {q('select count(*) from reports')}")


@dp.pre_checkout_query()
async def pre_checkout(q: PreCheckoutQuery):
    await q.answer(ok=True)


@dp.message(F.successful_payment)
async def paid(m: Message):
    trip_id = int(m.successful_payment.invoice_payload.split(":")[1])
    with db() as c:
        c.execute("update trips set boosted_until=? where id=? and user_id=?",
                  (int(time.time()) + 7 * 86400, trip_id, m.from_user.id))
    await m.answer("Готово: поездка неделю будет вверху табло." if lang_of(m.from_user.language_code) == "ru"
                   else "Done: your trip stays at the top of the board for a week.")


# ---------- после поездки просим оставить отзывы ----------
async def send_prompts():
    out = []
    with db() as c:
        rows = c.execute("""select t.*, (select count(*) from joins j where j.trip_id=t.id) as m
                            from trips t where t.prompted=0""").fetchall()
        for t in rows:
            if t["m"] > 0 and is_ended(t):
                out.append((t, people(c, t["id"])))
                c.execute("update trips set prompted=1 where id=?", (t["id"],))
    for t, ppl in out:
        for p in ppl:
            ru = p["lang"] == "ru"
            await safe_send(p["id"], (f"Поездка «{t['dest']}» завершилась. Оцени попутчиков: это помогает другим."
                                      if ru else f"Your trip “{t['dest']}” is over. Rate your buddies: it helps others."),
                            open_kb(t["id"], ru, "rate"))


async def prompt_loop():
    while True:
        try:
            await send_prompts()
        except Exception:
            pass
        await asyncio.sleep(3600)


# ---------- приложение ----------
@asynccontextmanager
async def lifespan(app):
    global BOT_USER
    init_db()
    try:
        BOT_USER = (await bot.get_me()).username or ""
    except Exception:
        pass
    await bot.set_chat_menu_button(menu_button=MenuButtonWebApp(
        text="Открыть", web_app=WebAppInfo(url=WEBAPP_URL)))
    tasks = [asyncio.create_task(dp.start_polling(bot)), asyncio.create_task(prompt_loop())]
    yield
    for t in tasks:
        t.cancel()


app = FastAPI(lifespan=lifespan)


@app.get("/")
def index():
    return FileResponse("index.html")


@app.get("/api/config")
def config():
    return {"bot": BOT_USER}


class Trip(BaseModel):
    kind: str = "flight"
    country: str = ""
    lat: Optional[float] = None
    lon: Optional[float] = None
    dest: str
    date_from: str = ""
    date_to: str = ""
    audience: str = "all"
    min_age: int = 0
    max_age: int = 0
    approval: int = 0
    people: int = 1
    budget: str = ""
    note: str = ""


class Profile(BaseModel):
    city: str = ""
    about: str = ""
    vibe: List[str] = []


class Reg(BaseModel):
    birth: str
    gender: str = ""
    city: str = ""
    about: str = ""
    vibe: List[str] = []


class Msg(BaseModel):
    text: str


class Review(BaseModel):
    trip_id: int
    to_id: int
    stars: int
    tags: List[str] = []
    text: str = ""


class BlockReq(BaseModel):
    user_id: int
    on: bool = True


class KickReq(BaseModel):
    user_id: int


@app.get("/api/me")
def me(x_init_data: str = Header("")):
    u = auth(x_init_data)
    with db() as c:
        d = dict(c.execute("select * from users where id=?", (u["id"],)).fetchone())
        d.update(stats(c, u["id"]))
    d["age"] = age_of(d.pop("birth", None))
    d.pop("username", None)
    return d


@app.post("/api/rules")
def accept_rules(x_init_data: str = Header("")):
    u = auth(x_init_data)
    with db() as c:
        c.execute("update users set rules_ok=1 where id=?", (u["id"],))
    return {"ok": True}


@app.post("/api/register")
def register(r: Reg, x_init_data: str = Header("")):
    u = auth(x_init_data)
    with db() as c:
        row = c.execute("select rules_ok from users where id=?", (u["id"],)).fetchone()
    if not row["rules_ok"]:
        raise HTTPException(403, "rules")
    try:
        b = datetime.date.fromisoformat(r.birth)
    except ValueError:
        raise HTTPException(400, "baddate")
    age = age_of(r.birth)
    if b > datetime.date.today() or age is None or age > 100:
        raise HTTPException(400, "baddate")
    if age < 18:
        with db() as c:  # дату рождения несовершеннолетнего не сохраняем, только запрет
            c.execute("update users set minor=1 where id=?", (u["id"],))
        raise HTTPException(403, "minor")
    if r.gender not in GENDERS:
        raise HTTPException(400, "badreq")
    with db() as c:
        c.execute("update users set birth=?, gender=?, vibe=?, city=?, about=?, registered=1 where id=?",
                  (r.birth, r.gender, clean_vibe(r.vibe), r.city.strip()[:60], r.about.strip()[:500], u["id"]))
    return {"ok": True}


@app.post("/api/profile")
def save_profile(p: Profile, x_init_data: str = Header("")):
    u = auth(x_init_data)
    need_ready(u)
    with db() as c:
        c.execute("update users set city=?, about=?, vibe=? where id=?",
                  (p.city.strip()[:60], p.about.strip()[:500], clean_vibe(p.vibe), u["id"]))
    return {"ok": True}


TRIP_SEL = """select t.*, u.name, u.city, u.about, u.vibe as a_vibe, t.user_id as author_id,
    (select status from requests q where q.trip_id=t.id and q.user_id=:me) as req,
    (select count(*) from requests q2 where q2.trip_id=t.id and q2.status='pending') as pending,
    cast((julianday('now')-julianday(u.birth))/365.25 as int) as age,
    (select round(avg(stars),1) from reviews r where r.to_id=t.user_id) as a_avg,
    (select count(*) from reviews r where r.to_id=t.user_id) as a_cnt,
    (select count(*) from joins j2 where j2.trip_id=t.id) as members,
    (select count(*) from joins j where j.trip_id=t.id and j.user_id=:me) as joined,
    (t.boosted_until > :now) as boosted
    from trips t join users u on u.id=t.user_id """


def shape(r, uid):
    d = dict(r)
    d["mine"] = r["user_id"] == uid
    d["ended"] = is_ended(r)
    if not d["mine"]:
        d["pending"] = 0
    return d


@app.get("/api/trips")
def trips(x_init_data: str = Header("")):
    u = auth(x_init_data)
    need_ready(u)
    with db() as c:
        rows = c.execute(TRIP_SEL + """where t.closed=0 and u.banned=0
            and coalesce(nullif(t.date_to,''), nullif(t.date_from,''), date(t.created,'unixepoch','+30 days')) >= :today
            and t.user_id not in (select blocked_id from blocks where user_id=:me)
            and t.user_id not in (select user_id from blocks where blocked_id=:me)
            order by boosted desc, t.id desc limit 200""",
                         {"me": u["id"], "now": int(time.time()), "today": today()}).fetchall()
    return [shape(r, u["id"]) for r in rows]


@app.get("/api/trips/{trip_id}")
def one_trip(trip_id: int, x_init_data: str = Header("")):
    u = auth(x_init_data)
    need_ready(u)
    with db() as c:
        r = c.execute(TRIP_SEL + "where t.id=:id and u.banned=0",
                      {"me": u["id"], "now": int(time.time()), "id": trip_id}).fetchone()
        if not r:
            raise HTTPException(404, "notfound")
        d = shape(r, u["id"])
        if is_ended(r) and (d["mine"] or d["joined"]):
            d["to_rate"] = unrated(c, trip_id, u["id"])
    return d


def unrated(c, trip_id, uid):
    ids = {p["id"] for p in people(c, trip_id)}
    done = {r["to_id"] for r in c.execute("select to_id from reviews where trip_id=? and from_id=?", (trip_id, uid))}
    return len([i for i in ids if i != uid and i not in done])


@app.get("/api/my")
def my(x_init_data: str = Header("")):
    u = auth(x_init_data)
    need_ready(u)
    prm = {"me": u["id"], "now": int(time.time())}
    with db() as c:
        mine = c.execute(TRIP_SEL + "where t.user_id=:me order by t.id desc", prm).fetchall()
        joined = c.execute(TRIP_SEL + """join joins jj on jj.trip_id=t.id
                                         where jj.user_id=:me order by jj.created desc""", prm).fetchall()
        out = {"mine": [], "joined": []}
        for key, rows in (("mine", mine), ("joined", joined)):
            for r in rows:
                d = shape(r, u["id"])
                d["requests"] = d["members"]
                d["to_rate"] = unrated(c, r["id"], u["id"]) if d["ended"] and d["members"] > 0 else 0
                out[key].append(d)
    return out


@app.post("/api/trips")
def create_trip(t: Trip, x_init_data: str = Header("")):
    u = auth(x_init_data)
    need_ready(u)
    if not t.dest.strip():
        raise HTTPException(400, "nodest")
    if t.audience not in ("all", "f", "m"):
        raise HTTPException(400, "badreq")
    if t.kind == "plan" and not t.date_from:
        raise HTTPException(400, "baddate")
    mn, mx = max(0, min(t.min_age, 99)), max(0, min(t.max_age, 99))
    if mn and mx and mx < mn:
        raise HTTPException(400, "badreq")
    if (t.date_to and t.date_to < today()) or (t.date_from and t.date_to and t.date_to < t.date_from):
        raise HTTPException(400, "baddate")
    with db() as c:
        n = c.execute("""select count(*) from trips t where t.user_id=? and t.closed=0 and
            coalesce(nullif(t.date_to,''), nullif(t.date_from,''), date(t.created,'unixepoch','+30 days')) >= ?""",
                      (u["id"], today())).fetchone()[0]
        if n >= MAX_ACTIVE:
            raise HTTPException(400, "limit")
        c.execute("""insert into trips(user_id,dest,date_from,date_to,people,budget,note,created,kind,country,lat,lon,
                     audience,min_age,max_age,approval) values(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                  (u["id"], t.dest.strip()[:80], t.date_from, t.date_to,
                   max(1, min(t.people, 20)), t.budget.strip()[:40], t.note.strip()[:500], int(time.time()),
                   t.kind if t.kind in KINDS else "other", t.country[:60], t.lat, t.lon,
                   t.audience, mn, mx, 1 if t.approval else 0))
    return {"ok": True}


def chat_access(c, trip_id, uid):
    trip = c.execute("select * from trips where id=?", (trip_id,)).fetchone()
    if not trip:
        raise HTTPException(404, "notfound")
    is_member = trip["user_id"] == uid or c.execute(
        "select 1 from joins where trip_id=? and user_id=?", (trip_id, uid)).fetchone()
    if not is_member:
        raise HTTPException(403, "notmember")
    return trip


@app.post("/api/trips/{trip_id}/join")
async def join(trip_id: int, x_init_data: str = Header("")):
    u = auth(x_init_data)
    need_ready(u)
    pending = False
    with db() as c:
        trip = c.execute("""select t.*, a.banned as ab, a.lang as alang from trips t
                            join users a on a.id=t.user_id where t.id=?""", (trip_id,)).fetchone()
        if not trip or trip["ab"]:
            raise HTTPException(404, "notfound")
        if trip["user_id"] == u["id"]:
            raise HTTPException(400, "own")
        n = c.execute("select count(*) from joins where trip_id=?", (trip_id,)).fetchone()[0]
        if c.execute("select 1 from joins where trip_id=? and user_id=?", (trip_id, u["id"])).fetchone():
            return {"ok": True, "full": n >= trip["people"]}
        if trip["closed"]:
            raise HTTPException(400, "tripclosed")
        if is_ended(trip):
            raise HTTPException(400, "tripended")
        if blocked_pair(c, u["id"], trip["user_id"]):
            raise HTTPException(403, "blocked")
        if c.execute("select 1 from kicked where trip_id=? and user_id=?", (trip_id, u["id"])).fetchone():
            raise HTTPException(403, "kicked")
        me_ = c.execute("select name, gender, birth from users where id=?", (u["id"],)).fetchone()
        if trip["audience"] in ("f", "m") and me_["gender"] != trip["audience"]:
            raise HTTPException(403, "audience")
        age = age_of(me_["birth"])
        if age is not None and ((trip["min_age"] and age < trip["min_age"]) or (trip["max_age"] and age > trip["max_age"])):
            raise HTTPException(403, "agerange")
        if n >= trip["people"]:
            raise HTTPException(400, "full")
        name = me_["name"]
        if trip["approval"]:
            old = c.execute("select status from requests where trip_id=? and user_id=?", (trip_id, u["id"])).fetchone()
            if old and old["status"] == "declined":
                raise HTTPException(403, "declined")
            if old:
                return {"ok": True, "pending": True}
            c.execute("insert into requests(trip_id,user_id,status,created) values(?,?,'pending',?)",
                      (trip_id, u["id"], int(time.time())))
            pending = True
        else:
            add_member(c, trip_id, u["id"])
    ru = trip["alang"] == "ru"
    who = name or ("Кто-то" if ru else "Someone")
    if pending:
        await safe_send(trip["user_id"],
                        (f"{who} хочет поехать с тобой: {trip['dest']}. Посмотри заявку." if ru
                         else f"{who} wants to join your trip: {trip['dest']}. Review the request."),
                        open_kb(trip_id, ru, "req"))
        return {"ok": True, "pending": True}
    n += 1
    await safe_send(trip["user_id"],
                    (f"{who} едет с тобой: {trip['dest']} ({n}/{trip['people']})" if ru
                     else f"{who} joined your trip: {trip['dest']} ({n}/{trip['people']})"),
                    open_kb(trip_id, ru))
    return {"ok": True, "full": n >= trip["people"]}


@app.get("/api/trips/{trip_id}/requests")
def list_requests(trip_id: int, x_init_data: str = Header("")):
    u = auth(x_init_data)
    with db() as c:
        if not c.execute("select 1 from trips where id=? and user_id=?", (trip_id, u["id"])).fetchone():
            raise HTTPException(404, "notfound")
        rows = c.execute("""select u.id, u.name, u.vibe,
            cast((julianday('now')-julianday(u.birth))/365.25 as int) as age,
            (select round(avg(stars),1) from reviews r where r.to_id=u.id) as a_avg,
            (select count(*) from reviews r where r.to_id=u.id) as a_cnt
            from requests q join users u on u.id=q.user_id
            where q.trip_id=? and q.status='pending' order by q.created""", (trip_id,)).fetchall()
    return [dict(r) for r in rows]


@app.post("/api/trips/{trip_id}/requests/{uid}/{act}")
async def answer_request(trip_id: int, uid: int, act: str, x_init_data: str = Header("")):
    u = auth(x_init_data)
    if act not in ("accept", "decline"):
        raise HTTPException(400, "badreq")
    with db() as c:
        trip = c.execute("select * from trips where id=? and user_id=?", (trip_id, u["id"])).fetchone()
        if not trip:
            raise HTTPException(404, "notfound")
        req = c.execute("select 1 from requests where trip_id=? and user_id=? and status='pending'",
                        (trip_id, uid)).fetchone()
        if not req:
            raise HTTPException(404, "notfound")
        lang = c.execute("select lang from users where id=?", (uid,)).fetchone()["lang"]
        if act == "accept":
            n = c.execute("select count(*) from joins where trip_id=?", (trip_id,)).fetchone()[0]
            if n >= trip["people"]:
                raise HTTPException(400, "full")
            add_member(c, trip_id, uid)
            c.execute("update requests set status='accepted' where trip_id=? and user_id=?", (trip_id, uid))
        else:
            c.execute("update requests set status='declined' where trip_id=? and user_id=?", (trip_id, uid))
    ru = lang == "ru"
    if act == "accept":
        await safe_send(uid, f"Тебя приняли в поездку «{trip['dest']}»! Чат открыт." if ru
                        else f"You are in! “{trip['dest']}” — the chat is open.", open_kb(trip_id, ru))
    else:
        await safe_send(uid, f"Автор не смог взять тебя в поездку «{trip['dest']}». Найди другую, их много." if ru
                        else f"The author couldn’t take you on “{trip['dest']}”. Many other trips are waiting.")
    return {"ok": True}


@app.post("/api/trips/{trip_id}/leave")
def leave(trip_id: int, x_init_data: str = Header("")):
    u = auth(x_init_data)
    with db() as c:
        trip = chat_access(c, trip_id, u["id"])
        if trip["user_id"] == u["id"]:
            raise HTTPException(400, "own")
        name = c.execute("select name from users where id=?", (u["id"],)).fetchone()["name"]
        c.execute("delete from joins where trip_id=? and user_id=?", (trip_id, u["id"]))
        sysmsg(c, trip_id, f"leave:{name}")
    return {"ok": True}


@app.post("/api/trips/{trip_id}/kick")
async def kick(trip_id: int, k: KickReq, x_init_data: str = Header("")):
    u = auth(x_init_data)
    with db() as c:
        trip = c.execute("select * from trips where id=? and user_id=?", (trip_id, u["id"])).fetchone()
        if not trip:
            raise HTTPException(404, "notfound")
        t = c.execute("""select u.name, u.lang from joins j join users u on u.id=j.user_id
                         where j.trip_id=? and j.user_id=?""", (trip_id, k.user_id)).fetchone()
        if not t:
            raise HTTPException(404, "notfound")
        c.execute("delete from joins where trip_id=? and user_id=?", (trip_id, k.user_id))
        c.execute("insert or ignore into kicked values(?,?)", (trip_id, k.user_id))
        sysmsg(c, trip_id, f"kick:{t['name']}")
    ru = t["lang"] == "ru"
    await safe_send(k.user_id, f"Автор исключил тебя из группы «{trip['dest']}»." if ru
                    else f"The author removed you from the “{trip['dest']}” group.")
    return {"ok": True}


@app.post("/api/trips/{trip_id}/close")
def close_trip(trip_id: int, x_init_data: str = Header("")):
    u = auth(x_init_data)
    with db() as c:
        trip = c.execute("select * from trips where id=? and user_id=?", (trip_id, u["id"])).fetchone()
        if not trip:
            raise HTTPException(404, "notfound")
        c.execute("update trips set closed=1 where id=?", (trip_id,))
        if trip["chat_open"]:
            sysmsg(c, trip_id, "closed:")
    return {"ok": True}


def members_info(c, trip, uid):
    rows = c.execute("""select u.id, u.name,
        cast((julianday('now')-julianday(u.birth))/365.25 as int) as age,
        (select round(avg(stars),1) from reviews r where r.to_id=u.id) as a_avg,
        (select count(*) from reviews r where r.to_id=u.id) as a_cnt,
        (select count(*) from reviews r where r.trip_id=:t and r.from_id=:me and r.to_id=u.id) as rated
        from users u where u.id=:a or u.id in (select user_id from joins where trip_id=:t)
        order by (u.id=:a) desc""", {"t": trip["id"], "me": uid, "a": trip["user_id"]}).fetchall()
    return [{**dict(r), "is_author": r["id"] == trip["user_id"]} for r in rows]


@app.get("/api/trips/{trip_id}/people")
def trip_people(trip_id: int, x_init_data: str = Header("")):
    u = auth(x_init_data)
    with db() as c:
        trip = chat_access(c, trip_id, u["id"])
        return {"dest": trip["dest"], "me": u["id"], "author_id": trip["user_id"],
                "ended": is_ended(trip), "closed": bool(trip["closed"]), "members": members_info(c, trip, u["id"])}


@app.get("/api/trips/{trip_id}/chat")
def get_chat(trip_id: int, since: int = 0, x_init_data: str = Header("")):
    u = auth(x_init_data)
    with db() as c:
        trip = chat_access(c, trip_id, u["id"])
        if not trip["chat_open"]:
            raise HTTPException(400, "closed")
        base = """select m.id, m.user_id, m.text, m.created, coalesce(u.name,'') as name
                  from messages m left join users u on u.id = m.user_id
                  where m.trip_id=:t and m.id>:s
                  and (m.user_id=0 or m.user_id not in (select blocked_id from blocks where user_id=:me))"""
        prm = {"t": trip_id, "s": since, "me": u["id"]}
        if since == 0:
            msgs = list(reversed(c.execute(base + " order by m.id desc limit 200", prm).fetchall()))
        else:
            msgs = c.execute(base + " order by m.id limit 200", prm).fetchall()
        info = members_info(c, trip, u["id"])
        rx = {}
        for r in c.execute("""select r.msg_id, r.emoji, count(*) n, max(r.user_id=?) mine
                              from reactions r join messages m on m.id=r.msg_id where m.trip_id=?
                              group by r.msg_id, r.emoji""", (u["id"], trip_id)):
            rx.setdefault(r["msg_id"], {})[r["emoji"]] = [r["n"], r["mine"]]
    return {"dest": trip["dest"], "me": u["id"], "author_id": trip["user_id"], "ended": is_ended(trip),
            "closed": bool(trip["closed"]), "members": info, "messages": [dict(r) for r in msgs], "reactions": rx}


@app.post("/api/trips/{trip_id}/messages")
async def post_message(trip_id: int, m: Msg, x_init_data: str = Header("")):
    u = auth(x_init_data)
    need_ready(u)
    text = m.text.strip()[:1000]
    if not text:
        raise HTTPException(400, "empty")
    now = time.time()
    recent = [t for t in FLOOD.get(u["id"], []) if now - t < 30]
    if len(recent) >= 15:
        raise HTTPException(429, "slow")
    FLOOD[u["id"]] = recent + [now]
    with db() as c:
        trip = chat_access(c, trip_id, u["id"])
        if not trip["chat_open"]:
            raise HTTPException(400, "closed")
        c.execute("insert into messages(trip_id,user_id,text,created) values(?,?,?,?)",
                  (trip_id, u["id"], text, int(time.time())))
        others = people(c, trip_id)
    for r in others:
        key = (trip_id, r["id"])
        if r["id"] != u["id"] and now - PINGED.get(key, 0) > 600:
            PINGED[key] = now
            ru = r["lang"] == "ru"
            await safe_send(r["id"], (f"Новое сообщение в чате «{trip['dest']}»" if ru
                                      else f"New message in the “{trip['dest']}” chat"), open_kb(trip_id, ru))
    return {"ok": True}


class React(BaseModel):
    emoji: str


EMOJIS = ("👍", "❤️", "😂", "🔥", "😮")


@app.post("/api/messages/{msg_id}/react")
def react(msg_id: int, r: React, x_init_data: str = Header("")):
    u = auth(x_init_data)
    need_ready(u)
    if r.emoji not in EMOJIS:
        raise HTTPException(400, "badreq")
    with db() as c:
        msg = c.execute("select trip_id, user_id from messages where id=?", (msg_id,)).fetchone()
        if not msg or msg["user_id"] == 0:
            raise HTTPException(404, "notfound")
        chat_access(c, msg["trip_id"], u["id"])
        if c.execute("select 1 from reactions where msg_id=? and user_id=? and emoji=?", (msg_id, u["id"], r.emoji)).fetchone():
            c.execute("delete from reactions where msg_id=? and user_id=? and emoji=?", (msg_id, u["id"], r.emoji))
        else:
            c.execute("insert into reactions values(?,?,?)", (msg_id, u["id"], r.emoji))
    return {"ok": True}


@app.post("/api/messages/{msg_id}/report")
async def report(msg_id: int, x_init_data: str = Header("")):
    u = auth(x_init_data)
    with db() as c:
        msg = c.execute("""select m.*, u.name from messages m join users u on u.id=m.user_id
                           where m.id=?""", (msg_id,)).fetchone()
        if not msg:
            raise HTTPException(404, "notfound")
        chat_access(c, msg["trip_id"], u["id"])
        c.execute("insert into reports values(?,?,?)", (msg_id, u["id"], int(time.time())))
    if ADMIN_ID:
        await safe_send(ADMIN_ID, f"Report: trip {msg['trip_id']}, user {msg['user_id']} ({msg['name']}): "
                                  f"{msg['text']}\n/ban {msg['user_id']}")
    return {"ok": True}


# ---------- профили, рейтинг, блокировки ----------
@app.get("/api/users/{user_id}")
def profile(user_id: int, x_init_data: str = Header("")):
    u = auth(x_init_data)
    need_ready(u)
    with db() as c:
        p = c.execute("select * from users where id=? and registered=1 and banned=0", (user_id,)).fetchone()
        if not p:
            raise HTTPException(404, "notfound")
        st = stats(c, user_id)
        revs = c.execute("""select r.stars, r.tags, r.text, r.created, u.name, t.dest
                            from reviews r join users u on u.id=r.from_id join trips t on t.id=r.trip_id
                            where r.to_id=? order by r.id desc limit 20""", (user_id,)).fetchall()
        tags = {}
        for r in c.execute("select tags from reviews where to_id=?", (user_id,)):
            for tg in filter(None, r["tags"].split(",")):
                tags[tg] = tags.get(tg, 0) + 1
        blocked = bool(c.execute("select 1 from blocks where user_id=? and blocked_id=?", (u["id"], user_id)).fetchone())
    return {"id": user_id, "name": p["name"], "age": age_of(p["birth"]), "city": p["city"], "about": p["about"],
            "vibe": [v for v in (p["vibe"] or "").split(",") if v],
            **st, "tags": tags, "me": user_id == u["id"], "blocked": blocked,
            "reviews": [{**dict(r), "tags": [t for t in r["tags"].split(",") if t]} for r in revs]}


@app.post("/api/block")
def block(b: BlockReq, x_init_data: str = Header("")):
    u = auth(x_init_data)
    if b.user_id == u["id"]:
        raise HTTPException(400, "own")
    with db() as c:
        if b.on:
            c.execute("insert or ignore into blocks values(?,?)", (u["id"], b.user_id))
        else:
            c.execute("delete from blocks where user_id=? and blocked_id=?", (u["id"], b.user_id))
    return {"ok": True}


@app.post("/api/users/{user_id}/report")
async def report_user(user_id: int, x_init_data: str = Header("")):
    u = auth(x_init_data)
    with db() as c:
        p = c.execute("select name from users where id=?", (user_id,)).fetchone()
    if not p:
        raise HTTPException(404, "notfound")
    if ADMIN_ID:
        await safe_send(ADMIN_ID, f"Profile report: user {user_id} ({p['name']}) by {u['id']}\n/ban {user_id}")
    return {"ok": True}


@app.post("/api/reviews")
async def add_review(r: Review, x_init_data: str = Header("")):
    u = auth(x_init_data)
    need_ready(u)
    if not 1 <= r.stars <= 5 or r.to_id == u["id"]:
        raise HTTPException(400, "badreq")
    tags = ",".join(t for t in dict.fromkeys(r.tags) if t in TAGS)
    with db() as c:
        trip = chat_access(c, r.trip_id, u["id"])
        if not is_ended(trip):
            raise HTTPException(400, "notended")
        if r.to_id not in {p["id"] for p in people(c, r.trip_id)}:
            raise HTTPException(400, "badreq")
        if c.execute("select 1 from reviews where trip_id=? and from_id=? and to_id=?",
                     (r.trip_id, u["id"], r.to_id)).fetchone():
            raise HTTPException(400, "dup")
        c.execute("insert into reviews(trip_id,from_id,to_id,stars,tags,text,created) values(?,?,?,?,?,?,?)",
                  (r.trip_id, u["id"], r.to_id, r.stars, tags, r.text.strip()[:300], int(time.time())))
        lang = c.execute("select lang from users where id=?", (r.to_id,)).fetchone()["lang"]
    await safe_send(r.to_id, f"⭐ Тебе оставили отзыв: {'★' * r.stars}" if lang == "ru"
                    else f"⭐ You got a new review: {'★' * r.stars}")
    return {"ok": True}


@app.post("/api/trips/{trip_id}/boost")
async def boost(trip_id: int, x_init_data: str = Header("")):
    u = auth(x_init_data)
    need_ready(u)
    with db() as c:
        trip = c.execute("select * from trips where id=? and user_id=?", (trip_id, u["id"])).fetchone()
    if not trip:
        raise HTTPException(404, "notfound")
    link = await bot.create_invoice_link(
        title="Поднять поездку / Boost trip", description=f"{trip['dest']}: 7 days on top / 7 дней вверху",
        payload=f"boost:{trip_id}", currency="XTR",
        prices=[LabeledPrice(label="7 days / 7 дней", amount=BOOST_STARS)])
    return {"link": link}
