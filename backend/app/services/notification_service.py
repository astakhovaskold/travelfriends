import asyncio, logging
from app.config import WEBAPP_URL, ADMIN_ID
from app.db.session import db
from app.services.common import is_ended, people
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo

PINGED = {}
FLOOD = {}

def open_kb(trip_id, ru, kind="chat"):
    url = f"{WEBAPP_URL}?{kind}={trip_id}"
    text = {"chat": ("Открыть чат", "Open chat"), "rate": ("Оценить попутчиков", "Rate your buddies"),
            "trip": ("Открыть поездку", "Open trip"), "req": ("Посмотреть заявки", "View requests")}[kind]
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(
        text=text[0] if ru else text[1], web_app=WebAppInfo(url=url))]])


async def safe_send(uid, text, kb=None):
    from app.integrations.telegram.bot import get_bot
    from app.db.models import auth_identities
    from sqlalchemy import select
    bot = get_bot()
    if bot is None:
        return
    with db() as c:
        identity = c.connection.execute(select(auth_identities.c.subject).where(
            auth_identities.c.user_id == uid, auth_identities.c.provider == 'telegram')).scalar_one_or_none()
    if identity is None:
        return
    try:
        await bot.send_message(int(identity), text, reply_markup=kb)
    except Exception:
        logging.getLogger(__name__).exception('Telegram notification failed for user %s', uid)

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
            logging.getLogger(__name__).exception("Review prompt loop failed")
        await asyncio.sleep(3600)



async def notify_admin(text):
    from app.integrations.telegram.bot import get_bot
    bot = get_bot()
    if bot is None or not ADMIN_ID:
        return
    try:
        await bot.send_message(ADMIN_ID, text)
    except Exception:
        logging.getLogger(__name__).exception('Admin notification failed')
