import asyncio
import logging
from contextlib import suppress

from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand

from app.bot.handlers import application, membership, moderation, start, support
from app.core.config import settings
from app.db.session import SessionLocal
from app.services.bootstrap import seed_defaults
from app.services.broadcast_service import run_broadcast_worker
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
    await bot.set_my_commands(
        [
            BotCommand(command="start", description="Главное меню"),
            BotCommand(command="support", description="Обратиться в поддержку"),
            BotCommand(command="admin", description="Панель управления"),
        ]
    )
    if settings.telegram_group_id:
        try:
            administrators = await bot.get_chat_administrators(int(settings.telegram_group_id))
            await track_telegram_users(
                [member.user for member in administrators],
                is_group_member=True,
            )
        except Exception:
            logger.exception("Failed to sync Telegram group administrators")
    dp = Dispatcher()
    dp.message.outer_middleware(GroupParticipantTrackingMiddleware())
    dp.include_router(start.router)
    dp.include_router(support.router)
    dp.include_router(application.router)
    dp.include_router(membership.router)
    dp.include_router(moderation.router)
    broadcast_worker = asyncio.create_task(run_broadcast_worker(bot))
    try:
        await dp.start_polling(bot)
    finally:
        broadcast_worker.cancel()
        with suppress(asyncio.CancelledError):
            await broadcast_worker


if __name__ == "__main__":
    asyncio.run(main())
