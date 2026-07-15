from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message, WebAppInfo
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.bot.keyboards import start_keyboard
from app.core.config import settings

router = Router()

WELCOME_TEXT = """<b>🎵 Добро пожаловать в Prod.by!</b>

Это закрытое сообщество, объединяющее специалистов музыкальной индустрии и смежных творческих направлений.

🎧 Здесь мы собираем не только артистов, продюсеров, битмейкеров и звукорежиссеров, но и дизайнеров, операторов, монтажеров, организаторов и всех, кто участвует в создании и продвижении музыкальных проектов.

📝 Для вступления необходимо пройти небольшую анкету. После проверки администрацией вы получите уведомление о результате рассмотрения заявки.

Нажмите <b>«Подать заявку»</b>, чтобы начать 👇"""


@router.message(CommandStart())
async def start(message: Message) -> None:
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
