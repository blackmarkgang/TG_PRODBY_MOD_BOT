import asyncio
import html
import logging

from aiogram import Bot, Router
from aiogram.types import Message
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.core.config import settings
from app.db.models import AdminUser, ForumTopic, TopicRolePermission, TopicWhitelist, User, UserRole
from app.db.session import SessionLocal

router = Router()
logger = logging.getLogger(__name__)


async def delete_warning_later(bot: Bot, chat_id: int, message_id: int) -> None:
    await asyncio.sleep(3)
    try:
        await bot.delete_message(chat_id, message_id)
    except Exception:
        logger.exception("Failed to delete topic permission warning")


def get_topic_title(message: Message) -> str | None:
    if message.forum_topic_created:
        return message.forum_topic_created.name
    if message.forum_topic_edited and message.forum_topic_edited.name:
        return message.forum_topic_edited.name
    return None


@router.message()
async def moderate_forum_topic(message: Message) -> None:
    if message.chat.type not in {"supergroup", "group"} or message.message_thread_id is None:
        return
    if settings.telegram_group_id and message.chat.id != int(settings.telegram_group_id):
        return
    if message.from_user is None or message.from_user.is_bot:
        return

    detected_title = get_topic_title(message)
    async with SessionLocal() as session:
        topic_result = await session.execute(
            select(ForumTopic).where(
                ForumTopic.chat_id == message.chat.id,
                ForumTopic.message_thread_id == message.message_thread_id,
            )
        )
        topic = topic_result.scalar_one_or_none()
        if topic is None:
            await session.execute(
                insert(ForumTopic)
                .values(
                    chat_id=message.chat.id,
                    message_thread_id=message.message_thread_id,
                    title=detected_title or f"Тема #{message.message_thread_id}",
                    is_protected=False,
                )
                .on_conflict_do_nothing(index_elements=["chat_id", "message_thread_id"])
            )
            await session.commit()
            topic_result = await session.execute(
                select(ForumTopic).where(
                    ForumTopic.chat_id == message.chat.id,
                    ForumTopic.message_thread_id == message.message_thread_id,
                )
            )
            topic = topic_result.scalar_one()
        elif detected_title and topic.title != detected_title:
            topic.title = detected_title
            await session.commit()

        # Service messages discover and rename topics, but are never moderated.
        if (
            message.forum_topic_created
            or message.forum_topic_edited
            or message.forum_topic_closed
            or message.forum_topic_reopened
        ):
            return
        if message.from_user.id in settings.admin_ids:
            return

        admin_result = await session.execute(
            select(AdminUser.id).where(
                AdminUser.telegram_id == message.from_user.id,
                AdminUser.is_active.is_(True),
            )
        )
        if admin_result.scalar_one_or_none() is not None:
            return

        permissions_result = await session.execute(
            select(TopicRolePermission.role_id).where(TopicRolePermission.topic_id == topic.id)
        )
        allowed_role_ids = set(permissions_result.scalars().all())
        if not allowed_role_ids:
            return

        user_result = await session.execute(select(User).where(User.telegram_id == message.from_user.id))
        user = user_result.scalar_one_or_none()
        if user is not None:
            whitelist_result = await session.execute(
                select(TopicWhitelist.id).where(
                    TopicWhitelist.topic_id == topic.id,
                    TopicWhitelist.user_id == user.id,
                )
            )
            if whitelist_result.scalar_one_or_none() is not None:
                return

            user_roles_result = await session.execute(
                select(UserRole.role_id).where(UserRole.user_id == user.id)
            )
            if allowed_role_ids.intersection(user_roles_result.scalars().all()):
                return

    try:
        await message.delete()
    except Exception:
        logger.exception("Failed to delete a message without topic permission")

    display_name = html.escape(message.from_user.full_name)
    mention = f'<a href="tg://user?id={message.from_user.id}">{display_name}</a>'
    try:
        warning = await message.bot.send_message(
            chat_id=message.chat.id,
            message_thread_id=message.message_thread_id,
            text=(
                "⛔ <b>Нет доступа к публикации</b>\n"
                f"{mention}, для этой темы нужна разрешенная роль."
            ),
            parse_mode="HTML",
        )
        asyncio.create_task(delete_warning_later(message.bot, message.chat.id, warning.message_id))
    except Exception:
        logger.exception("Failed to send a topic permission warning")
