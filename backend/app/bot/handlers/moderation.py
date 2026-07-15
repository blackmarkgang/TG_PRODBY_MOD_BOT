from aiogram import Router
from aiogram.types import Message
from sqlalchemy import select

from app.db.models import ForumTopic, TopicWhitelist, User
from app.db.session import SessionLocal

router = Router()


@router.message()
async def moderate_forum_topic(message: Message) -> None:
    if message.chat.type not in {"supergroup", "group"} or message.message_thread_id is None:
        return
    if message.from_user is None:
        return

    async with SessionLocal() as session:
        topic_result = await session.execute(
            select(ForumTopic).where(
                ForumTopic.chat_id == message.chat.id,
                ForumTopic.message_thread_id == message.message_thread_id,
                ForumTopic.is_protected.is_(True),
            )
        )
        topic = topic_result.scalar_one_or_none()
        if topic is None:
            return

        user_result = await session.execute(select(User).where(User.telegram_id == message.from_user.id))
        user = user_result.scalar_one_or_none()
        if user is not None:
            whitelist_result = await session.execute(
                select(TopicWhitelist).where(
                    TopicWhitelist.topic_id == topic.id,
                    TopicWhitelist.user_id == user.id,
                )
            )
            if whitelist_result.scalar_one_or_none() is not None:
                return

    await message.delete()
    try:
        await message.bot.send_message(
            message.from_user.id,
            "Публикация в этой теме доступна только одобренным авторам. "
            "Чтобы получить доступ, обратитесь к администрации.",
        )
    except Exception:
        pass
