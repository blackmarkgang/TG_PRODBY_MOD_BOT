import asyncio
import logging

from aiogram import Bot, Dispatcher

from app.bot.handlers import application, moderation, start
from app.core.config import settings
from app.db.session import SessionLocal
from app.services.bootstrap import seed_defaults


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    if settings.bot_token == "replace_me":
        raise RuntimeError("Set BOT_TOKEN in .env")

    async with SessionLocal() as session:
        await seed_defaults(session)

    bot = Bot(token=settings.bot_token)
    dp = Dispatcher()
    dp.include_router(start.router)
    dp.include_router(application.router)
    dp.include_router(moderation.router)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())

