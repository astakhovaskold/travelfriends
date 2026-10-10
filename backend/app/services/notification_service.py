import asyncio
import logging

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo

from app.config import get_settings
from app.constants import PROMPT_INTERVAL
from app.db.session import db
from app.repositories.notifications import NotificationsRepository
from app.services.common import is_ended
from app.services.participation_service import people
from app.texts import render_text

PINGED = {}
FLOOD = {}


def open_kb(trip_id, ru, kind="chat"):
    url = f"{get_settings().WEBAPP_URL}?{kind}={trip_id}"
    text = render_text("button." + kind, "ru" if ru else "en")

    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=text, web_app=WebAppInfo(url=url))]]
    )


async def safe_send(user_id, text, kb=None):
    from app.integrations.telegram.bot import get_bot

    bot = get_bot()
    if bot is None:
        return

    with db() as transaction:
        identity = NotificationsRepository(transaction).telegram_identity(user_id)
    if identity is None:
        return
    try:
        await bot.send_message(int(identity), text, reply_markup=kb)
    except Exception:
        logging.getLogger(__name__).exception("Telegram notification failed for user %s", user_id)


async def send_prompts():
    prompts = []

    with db() as transaction:
        repository = NotificationsRepository(transaction)
        rows = repository.unprompted_trips()
        for trip in rows:
            if trip["m"] > 0 and is_ended(trip):
                prompts.append((trip, people(transaction, trip["id"])))
                repository.mark_prompted(trip["id"])
    for trip, participants in prompts:
        for participant in participants:
            ru = participant["lang"] == "ru"
            await safe_send(
                participant["id"],
                render_text("review.prompt", "ru" if ru else "en", dest=trip["dest"]),
                open_kb(trip["id"], ru, "rate"),
            )


async def prompt_loop():
    while True:
        try:
            await send_prompts()
        except Exception:
            logging.getLogger(__name__).exception("Review prompt loop failed")
        await asyncio.sleep(PROMPT_INTERVAL)


async def notify_admin(text):
    from app.integrations.telegram.bot import get_bot

    bot = get_bot()
    if bot is None or not get_settings().ADMIN_ID:
        return
    try:
        await bot.send_message(get_settings().ADMIN_ID, text)
    except Exception:
        logging.getLogger(__name__).exception("Admin notification failed")
