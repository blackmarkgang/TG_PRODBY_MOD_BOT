import logging

from aiogram import Router
from aiogram.types import ChatMemberUpdated

from app.services.participant_tracking import is_configured_group, track_telegram_users

router = Router()
logger = logging.getLogger(__name__)


@router.chat_member()
async def track_chat_member(update: ChatMemberUpdated) -> None:
    if not is_configured_group(update.chat.id, update.chat.type):
        return
    try:
        await track_telegram_users([update.new_chat_member.user])
    except Exception:
        logger.exception("Failed to track Telegram chat member update")
