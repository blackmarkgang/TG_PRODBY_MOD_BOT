import logging

from aiogram import Bot
from aiogram.enums import ChatMemberStatus
from aiogram.exceptions import TelegramAPIError
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models import Application, User
from app.services.bot_text_service import render_bot_text

logger = logging.getLogger(__name__)


async def get_active_application(
    session: AsyncSession,
    telegram_id: int,
) -> Application | None:
    result = await session.execute(
        select(Application)
        .join(User, User.id == Application.user_id)
        .where(
            User.telegram_id == telegram_id,
            Application.status.in_({"pending", "approved"}),
        )
        .order_by(desc(Application.created_at), desc(Application.id))
        .limit(1)
    )
    return result.scalar_one_or_none()


async def can_user_reapply(session: AsyncSession, telegram_id: int) -> bool:
    result = await session.execute(
        select(User.can_reapply).where(User.telegram_id == telegram_id)
    )
    return bool(result.scalar_one_or_none())


async def is_group_member(bot: Bot, telegram_id: int) -> bool:
    if not settings.telegram_group_id:
        return False
    try:
        member = await bot.get_chat_member(int(settings.telegram_group_id), telegram_id)
    except TelegramAPIError:
        logger.warning("Could not check Telegram group membership for user %s", telegram_id)
        return False

    if member.status in {
        ChatMemberStatus.CREATOR,
        ChatMemberStatus.ADMINISTRATOR,
        ChatMemberStatus.MEMBER,
    }:
        return True
    return member.status == ChatMemberStatus.RESTRICTED and member.is_member


async def active_application_message(application: Application) -> str:
    if application.status == "pending":
        return await render_bot_text("active_application_pending", application_id=application.id)
    return await render_bot_text("active_application_approved", application_id=application.id)
