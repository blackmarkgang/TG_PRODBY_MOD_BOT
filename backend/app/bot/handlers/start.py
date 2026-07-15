from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message, WebAppInfo
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.bot.keyboards import start_keyboard
from app.core.config import settings
from app.db.session import SessionLocal
from app.services.application_service import is_user_banned
from app.services.community_access import (
    active_application_message,
    get_active_application,
    is_group_member,
)

router = Router()

WELCOME_TEXT = """<b>🎵 Добро пожаловать в Prod.by!</b>

Это закрытое сообщество, объединяющее специалистов музыкальной индустрии и смежных творческих направлений.

🎧 Здесь мы собираем не только артистов, продюсеров, битмейкеров и звукорежиссеров, но и дизайнеров, операторов, монтажеров, организаторов и всех, кто участвует в создании и продвижении музыкальных проектов.

📝 Для вступления необходимо пройти небольшую анкету. После проверки администрацией вы получите уведомление о результате рассмотрения заявки.

Нажмите <b>«Подать заявку»</b>, чтобы начать 👇"""


@router.message(CommandStart())
async def start(message: Message) -> None:
    if message.from_user is not None:
        telegram_id = message.from_user.id
        async with SessionLocal() as session:
            if await is_user_banned(session, telegram_id):
                await message.answer(
                    "⛔ <b>Доступ ограничен</b>\n\nВы не можете подать новую заявку в Prod.by.",
                    parse_mode="HTML",
                )
                return
            if await is_group_member(message.bot, telegram_id):
                await message.answer(
                    "✅ <b>Вы уже состоите в Prod.by</b>\n\nПовторная заявка не требуется — доступ к сообществу у вас уже есть.",
                    parse_mode="HTML",
                )
                return
            active_application = await get_active_application(session, telegram_id)
            if active_application is not None:
                await message.answer(
                    active_application_message(active_application),
                    parse_mode="HTML",
                )
                return

    await message.answer(
        WELCOME_TEXT,
        parse_mode="HTML",
        reply_markup=start_keyboard(),
    )


@router.message(lambda message: message.text == "/admin")
async def admin_panel(message: Message) -> None:
    if message.from_user and message.from_user.id in settings.admin_ids:
        builder = InlineKeyboardBuilder()
        builder.button(text="Открыть панель", web_app=WebAppInfo(url=settings.public_webapp_url))
        await message.answer("⚙️ <b>Панель администратора</b>", parse_mode="HTML", reply_markup=builder.as_markup())
        return

    await message.answer("⛔ <b>Доступ запрещен</b>", parse_mode="HTML")
