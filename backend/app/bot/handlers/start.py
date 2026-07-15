from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message, WebAppInfo
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.bot.keyboards import start_keyboard
from app.core.config import settings

router = Router()


@router.message(CommandStart())
async def start(message: Message) -> None:
    await message.answer("Prod.by Bot", reply_markup=start_keyboard())


@router.message(lambda message: message.text == "/admin")
async def admin_panel(message: Message) -> None:
    if message.from_user and message.from_user.id in settings.admin_ids:
        builder = InlineKeyboardBuilder()
        builder.button(text="Open admin panel", web_app=WebAppInfo(url=settings.public_webapp_url))
        await message.answer("Admin panel", reply_markup=builder.as_markup())
        return

    await message.answer("Access denied.")

