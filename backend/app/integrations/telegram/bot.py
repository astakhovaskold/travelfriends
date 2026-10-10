import asyncio
from aiogram import Bot, Dispatcher
from aiogram.filters import CommandStart, Command, CommandObject
from aiogram.types import Message, WebAppInfo, InlineKeyboardMarkup, InlineKeyboardButton, MenuButtonWebApp
from app.config import BOT_TOKEN, WEBAPP_URL, ADMIN_ID
from app.db.session import db
from app.services.common import lang_of

_bot = None
dp = Dispatcher()

def get_bot():
    global _bot
    if not BOT_TOKEN:
        return None
    if _bot is None:
        _bot = Bot(BOT_TOKEN)
    return _bot

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



async def run():
    from app.integrations.telegram import payments  # registers handlers
    from app.services.notification_service import prompt_loop
    bot = get_bot()
    if bot is None:
        raise RuntimeError('BOT_TOKEN is required for the Telegram worker')
    await bot.set_chat_menu_button(menu_button=MenuButtonWebApp(text='Travel Friends', web_app=WebAppInfo(url=WEBAPP_URL)))
    prompts = asyncio.create_task(prompt_loop())
    try:
        await dp.start_polling(bot)
    finally:
        prompts.cancel()
        await asyncio.gather(prompts, return_exceptions=True)
        await bot.session.close()

