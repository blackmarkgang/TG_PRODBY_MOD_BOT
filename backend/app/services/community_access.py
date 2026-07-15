import logging

from aiogram import Bot
from aiogram.enums import ChatMemberStatus
from aiogram.exceptions import TelegramAPIError
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models import Application, User

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


def active_application_message(application: Application) -> str:
    if application.status == "pending":
        return (
            f"⏳ <b>Заявка №{application.id} уже на рассмотрении</b>\n\n"
            "Повторно заполнять анкету не нужно. Мы пришлем решение в этот чат."
        )
    return (
        f"✅ <b>Заявка №{application.id} уже одобрена</b>\n\n"
        "Используйте ссылку из сообщения об одобрении. Если она перестала действовать, обратитесь к администрации."
    )
