import logging

from aiogram import Router
from aiogram.enums import ChatMemberStatus
from aiogram.types import ChatMemberUpdated

from app.services.participant_tracking import is_configured_group, track_telegram_users

router = Router()
logger = logging.getLogger(__name__)


def is_active_chat_member(member) -> bool:
    return member.status in {
        ChatMemberStatus.CREATOR,
        ChatMemberStatus.ADMINISTRATOR,
        ChatMemberStatus.MEMBER,
    } or (
        member.status == ChatMemberStatus.RESTRICTED
        and bool(getattr(member, "is_member", False))
    )


@router.chat_member()
async def track_chat_member(update: ChatMemberUpdated) -> None:
    if not is_configured_group(update.chat.id, update.chat.type):
        return
    member = update.new_chat_member
    try:
        await track_telegram_users(
            [member.user],
            is_group_member=is_active_chat_member(member),
        )
    except Exception:
        logger.exception("Failed to track Telegram chat member update")
