from datetime import datetime, timedelta, timezone
from html import escape

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.core.config import settings
from app.db.models import Application
from app.services.bot_text_service import render_bot_text


async def create_application_invite(bot: Bot, application_id: int) -> str | None:
    if not settings.telegram_group_id:
        return None
    invite = await bot.create_chat_invite_link(
        chat_id=settings.telegram_group_id,
        name=f"Заявка №{application_id}",
        expire_date=datetime.now(timezone.utc) + timedelta(days=7),
        member_limit=1,
    )
    return invite.invite_link


def application_invite_keyboard(invite_url: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🚪 Вступить в Prod.by", url=invite_url)]
        ]
    )


async def notify_application_decision(
    application: Application,
    role_title: str | None = None,
) -> dict[str, bool | str | None]:
    bot = Bot(settings.bot_token)
    invite_url: str | None = None
    invite_created = False
    notification_sent = False
    warning: str | None = None

    try:
        if application.status == "approved":
            if settings.telegram_group_id:
                try:
                    invite_url = await create_application_invite(bot, application.id)
                    invite_created = True
                except TelegramAPIError:
                    warning = "Решение сохранено, но бот не смог создать ссылку на вход. Проверьте права бота в группе."
            else:
                warning = "Решение сохранено, но TELEGRAM_GROUP_ID не настроен."

            parts = [await render_bot_text("application_approved")]
            if role_title:
                parts.append(await render_bot_text("assigned_roles", roles=escape(role_title)))
            if application.admin_comment:
                parts.append(
                    await render_bot_text(
                        "admin_comment",
                        comment=escape(application.admin_comment),
                    )
                )
            if invite_url:
                parts.append(await render_bot_text("invite_ready"))
                keyboard = application_invite_keyboard(invite_url)
            else:
                parts.append(await render_bot_text("invite_unavailable"))
                keyboard = None
            text = "\n\n".join(parts)
        else:
            parts = [await render_bot_text("application_rejected")]
            if application.admin_comment:
                parts.append(
                    await render_bot_text(
                        "admin_comment",
                        comment=escape(application.admin_comment),
                    )
                )
            text = "\n\n".join(parts)
            keyboard = None

        try:
            await bot.send_message(
                chat_id=application.user.telegram_id,
                text=text,
                reply_markup=keyboard,
                parse_mode="HTML",
            )
            notification_sent = True
        except TelegramAPIError:
            delivery_warning = "Бот не смог отправить пользователю уведомление."
            warning = f"{warning} {delivery_warning}" if warning else delivery_warning
    finally:
        await bot.session.close()

    return {
        "notification_sent": notification_sent,
        "invite_created": invite_created,
        "warning": warning,
    }
