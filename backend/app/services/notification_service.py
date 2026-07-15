from datetime import datetime, timedelta, timezone
from html import escape

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.core.config import settings
from app.db.models import Application


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
                    invite = await bot.create_chat_invite_link(
                        chat_id=settings.telegram_group_id,
                        name=f"Заявка №{application.id}",
                        expire_date=datetime.now(timezone.utc) + timedelta(days=7),
                        member_limit=1,
                    )
                    invite_url = invite.invite_link
                    invite_created = True
                except TelegramAPIError:
                    warning = "Решение сохранено, но бот не смог создать ссылку на вход. Проверьте права бота в группе."
            else:
                warning = "Решение сохранено, но TELEGRAM_GROUP_ID не настроен."

            text = "🎉 <b>Ваша заявка одобрена!</b>\n\nДобро пожаловать в сообщество Prod.by."
            if role_title:
                text += f"\n\n🎭 Ваша роль: <b>{escape(role_title)}</b>"
            if application.admin_comment:
                text += f"\n\n💬 <b>Комментарий администрации</b>\n{escape(application.admin_comment)}"
            if invite_url:
                text += "\n\n🔗 Ссылка действует <b>7 дней</b> и рассчитана на одно вступление."
                keyboard = InlineKeyboardMarkup(
                    inline_keyboard=[
                        [InlineKeyboardButton(text="🚪 Вступить в Prod.by", url=invite_url)]
                    ]
                )
            else:
                text += "\n\n⚠️ Ссылка на вход пока недоступна. Администрация должна проверить права бота."
                keyboard = None
        else:
            text = "📩 <b>Решение по заявке</b>\n\nВаша заявка в сообщество Prod.by отклонена."
            if application.admin_comment:
                text += f"\n\n💬 <b>Комментарий администрации</b>\n{escape(application.admin_comment)}"
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
