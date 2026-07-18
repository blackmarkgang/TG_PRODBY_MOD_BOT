import asyncio
import logging

from aiogram import Bot, Dispatcher

from app.bot.handlers import application, membership, moderation, start
from app.core.config import settings
from app.db.session import SessionLocal
from app.services.bootstrap import seed_defaults
from app.services.participant_tracking import (
    GroupParticipantTrackingMiddleware,
    track_telegram_users,
)

logger = logging.getLogger(__name__)


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    if settings.bot_token == "replace_me":
        raise RuntimeError("Set BOT_TOKEN in .env")

    async with SessionLocal() as session:
        await seed_defaults(session)

    bot = Bot(token=settings.bot_token)
    if settings.telegram_group_id:
        try:
            administrators = await bot.get_chat_administrators(int(settings.telegram_group_id))
            await track_telegram_users([member.user for member in administrators])
        except Exception:
            logger.exception("Failed to sync Telegram group administrators")
    dp = Dispatcher()
    dp.message.outer_middleware(GroupParticipantTrackingMiddleware())
    dp.include_router(start.router)
    dp.include_router(application.router)
    dp.include_router(membership.router)
    dp.include_router(moderation.router)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
