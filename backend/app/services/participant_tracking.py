import logging
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject, User as TelegramUser
from sqlalchemy.dialects.postgresql import insert

from app.core.config import settings
from app.db.models import User
from app.db.session import SessionLocal

logger = logging.getLogger(__name__)


def is_configured_group(chat_id: int, chat_type: str) -> bool:
    if chat_type not in {"group", "supergroup"}:
        return False
    return not settings.telegram_group_id or chat_id == int(settings.telegram_group_id)


async def track_telegram_users(
    users: list[TelegramUser],
    *,
    is_group_member: bool | None = None,
    has_used_bot: bool | None = None,
) -> None:
    unique_users = {user.id: user for user in users if not user.is_bot}
    if not unique_users:
        return

    async with SessionLocal() as session:
        for telegram_user in unique_users.values():
            values: dict[str, Any] = {
                "telegram_id": telegram_user.id,
                "username": telegram_user.username,
                "first_name": telegram_user.first_name,
                "last_name": telegram_user.last_name,
            }
            update_values: dict[str, Any] = {
                "username": telegram_user.username,
                "first_name": telegram_user.first_name,
                "last_name": telegram_user.last_name,
            }
            if is_group_member is not None:
                values["is_group_member"] = is_group_member
                update_values["is_group_member"] = is_group_member
            if has_used_bot is not None:
                values["has_used_bot"] = has_used_bot
                update_values["has_used_bot"] = has_used_bot
            statement = insert(User).values(
                **values,
            )
            await session.execute(
                statement.on_conflict_do_update(
                    index_elements=["telegram_id"],
                    set_=update_values,
                )
            )
        await session.commit()


class GroupParticipantTrackingMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        if isinstance(event, Message):
            if event.chat.type == "private" and event.from_user is not None:
                try:
                    await track_telegram_users([event.from_user], has_used_bot=True)
                except Exception:
                    logger.exception("Failed to track Telegram bot user")
            elif is_configured_group(event.chat.id, event.chat.type):
                users = list(event.new_chat_members or [])
                if event.from_user is not None:
                    users.append(event.from_user)
                try:
                    await track_telegram_users(users, is_group_member=True)
                except Exception:
                    logger.exception("Failed to track Telegram group participants")
        return await handler(event, data)
