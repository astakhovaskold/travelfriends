import asyncio

from aiogram import Bot, Dispatcher
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    MenuButtonWebApp,
    Message,
    WebAppInfo,
)

from app.config import get_settings
from app.services import moderation_service
from app.services.common import lang_of
from app.texts import render_text

_bot = None
dp = Dispatcher()


def get_bot():
    global _bot
    if not get_settings().BOT_TOKEN:
        return None
    if _bot is None:
        _bot = Bot(get_settings().BOT_TOKEN)
    return _bot


@dp.message(CommandStart())
async def start(m: Message, command: CommandObject):
    ru = lang_of(m.from_user.language_code) == "ru"
    arg = command.args or ""
    url = get_settings().WEBAPP_URL
    if arg.startswith("trip_") and arg[5:].isdigit():
        url = f"{get_settings().WEBAPP_URL}?trip={arg[5:]}"
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=render_text("button.open_app", "ru" if ru else "en"),
                    web_app=WebAppInfo(url=url),
                )
            ]
        ]
    )
    await m.answer(render_text("bot.welcome", "ru" if ru else "en"), reply_markup=kb)


def is_admin(m: Message):
    return bool(get_settings().ADMIN_ID) and m.from_user.id == get_settings().ADMIN_ID


@dp.message(Command("ban"))
async def cmd_ban(m: Message, command: CommandObject):
    if not is_admin(m):
        return
    if not (command.args or "").strip().isdigit():
        await m.answer(render_text("admin.ban_usage", "en"))
        return
    moderation_service.set_banned(int(command.args), True)
    await m.answer(render_text("admin.banned", "en", user_id=command.args))


@dp.message(Command("unban"))
async def cmd_unban(m: Message, command: CommandObject):
    if not is_admin(m):
        return
    if not (command.args or "").strip().isdigit():
        await m.answer(render_text("admin.unban_usage", "en"))
        return
    moderation_service.set_banned(int(command.args), False)
    await m.answer(render_text("admin.unbanned", "en", user_id=command.args))


@dp.message(Command("stats"))
async def cmd_stats(m: Message):
    if not is_admin(m):
        return
    counts = moderation_service.statistics()
    await m.answer(render_text("admin.stats", "en", **counts))


async def run():
    # Import for dispatcher registration when launched as a standalone worker.
    from app.integrations.telegram import payments  # noqa: F401
    from app.services.notification_service import prompt_loop

    bot = get_bot()
    if bot is None:
        raise RuntimeError("BOT_TOKEN is required for the Telegram worker")
    await bot.set_chat_menu_button(
        menu_button=MenuButtonWebApp(
            text=render_text("button.menu", "en"), web_app=WebAppInfo(url=get_settings().WEBAPP_URL)
        )
    )
    prompts = asyncio.create_task(prompt_loop())
    try:
        await dp.start_polling(bot)
    finally:
        prompts.cancel()
        await asyncio.gather(prompts, return_exceptions=True)
        await bot.session.close()
