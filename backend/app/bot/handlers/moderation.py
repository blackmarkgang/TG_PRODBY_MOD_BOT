import asyncio
import html
import logging
import time
from datetime import datetime, timedelta, timezone

from aiogram import Bot, Router
from aiogram.types import ChatPermissions, Message
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.core.config import settings
from app.db.models import (
    AdminUser,
    AuditLog,
    ForumTopic,
    TopicRolePermission,
    TopicWhitelist,
    User,
    UserRole,
)
from app.db.session import SessionLocal
from app.services.bot_text_service import render_bot_text

router = Router()
logger = logging.getLogger(__name__)
moderation_cooldowns: dict[tuple[int, int], float] = {}


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


def claim_moderation_action(chat_id: int, user_id: int) -> bool:
    now = time.monotonic()
    key = (chat_id, user_id)
    if moderation_cooldowns.get(key, 0) > now:
        return False
    moderation_cooldowns[key] = now + 5
    if len(moderation_cooldowns) > 1_000:
        expired = [item for item, expires_at in moderation_cooldowns.items() if expires_at <= now]
        for item in expired:
            moderation_cooldowns.pop(item, None)
    return True


async def apply_role_timeout(message: Message) -> bool:
    try:
        await message.bot.restrict_chat_member(
            chat_id=message.chat.id,
            user_id=message.from_user.id,
            permissions=ChatPermissions(
                can_send_messages=False,
                can_send_audios=False,
                can_send_documents=False,
                can_send_photos=False,
                can_send_videos=False,
                can_send_video_notes=False,
                can_send_voice_notes=False,
                can_send_polls=False,
                can_send_other_messages=False,
                can_add_web_page_previews=False,
            ),
            until_date=datetime.now(timezone.utc)
            + timedelta(seconds=settings.moderation_timeout_seconds),
            use_independent_chat_permissions=True,
        )
        return True
    except Exception:
        logger.exception("Failed to apply a timeout for topic permission violation")
        return False


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
        admin_result = await session.execute(
            select(AdminUser.id).where(
                AdminUser.telegram_id == message.from_user.id,
                AdminUser.is_active.is_(True),
            )
        )
        if admin_result.scalar_one_or_none() is not None:
            return

        user_result = await session.execute(select(User).where(User.telegram_id == message.from_user.id))
        user = user_result.scalar_one_or_none()
        if user is None or not user.is_banned:
            permissions_result = await session.execute(
                select(TopicRolePermission.role_id).where(TopicRolePermission.topic_id == topic.id)
            )
            allowed_role_ids = set(permissions_result.scalars().all())
            if not allowed_role_ids:
                return

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

        should_act = claim_moderation_action(message.chat.id, message.from_user.id)
        if should_act:
            session.add(
                AuditLog(
                    action="moderation_denied",
                    entity_type="user",
                    entity_id=user.id if user is not None else None,
                    payload_json={
                        "telegram_id": message.from_user.id,
                        "username": message.from_user.username,
                        "first_name": message.from_user.first_name,
                        "last_name": message.from_user.last_name,
                        "chat_id": message.chat.id,
                        "topic_id": topic.id,
                        "topic_title": topic.title,
                        "reason": "banned" if user is not None and user.is_banned else "missing_role",
                        "timeout_seconds": settings.moderation_timeout_seconds,
                    },
                )
            )
            await session.commit()

    try:
        await message.delete()
    except Exception:
        logger.exception("Failed to delete a message without topic permission")

    if not should_act:
        return

    timeout_applied = False
    if user is None or not user.is_banned:
        timeout_applied = await apply_role_timeout(message)

    display_name = html.escape(message.from_user.full_name)
    mention = f'<a href="tg://user?id={message.from_user.id}">{display_name}</a>'
    if user is not None and user.is_banned:
        warning_text = await render_bot_text("moderation_banned", mention=mention)
    else:
        timeout = ""
        if timeout_applied:
            timeout = " " + await render_bot_text(
                "moderation_timeout",
                seconds=settings.moderation_timeout_seconds,
            )
        warning_text = await render_bot_text(
            "moderation_missing_role",
            mention=mention,
            timeout=timeout,
        )
    try:
        warning = await message.bot.send_message(
            chat_id=message.chat.id,
            message_thread_id=message.message_thread_id,
            text=warning_text,
            parse_mode="HTML",
        )
        asyncio.create_task(delete_warning_later(message.bot, message.chat.id, warning.message_id))
    except Exception:
        logger.exception("Failed to send a topic permission warning")
