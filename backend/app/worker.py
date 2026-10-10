"""Telegram process entry point (imported bot module has exactly one dispatcher)."""
import asyncio
from app.integrations.telegram.bot import run

if __name__=='__main__':
    asyncio.run(run())
