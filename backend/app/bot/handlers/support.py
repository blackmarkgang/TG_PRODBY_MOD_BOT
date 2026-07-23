from datetime import datetime, timezone
from html import escape

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    WebAppInfo,
)
from sqlalchemy import desc, select
from sqlalchemy.orm import selectinload

from app.bot.states import SupportForm
from app.core.config import settings
from app.db.models import AdminUser, AuditLog, SupportMessage, SupportTicket
from app.db.session import SessionLocal
from app.services.application_service import get_or_create_user
from app.services.bot_text_service import render_bot_text

router = Router()


def support_reply_keyboard(ticket_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✍️ Ответить",
                    callback_data=f"support_reply:{ticket_id}",
                )
            ]
        ]
    )


async def find_active_ticket(session, user_id: int) -> SupportTicket | None:
    result = await session.execute(
        select(SupportTicket)
        .where(
            SupportTicket.user_id == user_id,
            SupportTicket.status.in_(("open", "in_progress")),
        )
        .order_by(desc(SupportTicket.created_at))
        .limit(1)
    )
    return result.scalar_one_or_none()


async def notify_staff_new_ticket(bot, ticket: SupportTicket, text: str) -> None:
    async with SessionLocal() as session:
        result = await session.execute(
            select(AdminUser).where(AdminUser.is_active.is_(True))
        )
        staff = result.scalars().all()
    name = (
        f"@{ticket.user.username}"
        if ticket.user.username
        else " ".join(filter(None, (ticket.user.first_name, ticket.user.last_name)))
        or f"ID {ticket.user.telegram_id}"
    )
    notification = (
        f"🛟 <b>Новое обращение №{ticket.id}</b>\n\n"
        f"<b>Пользователь:</b> {escape(name)}\n"
        f"<b>Сообщение:</b> {escape(text)}"
    )
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Открыть поддержку",
                    web_app=WebAppInfo(url=settings.public_webapp_url),
                )
            ]
        ]
    )
    for admin in staff:
        try:
            await bot.send_message(
                admin.telegram_id,
                notification,
                parse_mode="HTML",
                reply_markup=keyboard,
            )
        except Exception:
            continue


@router.message(Command("support"))
async def start_support(message: Message, state: FSMContext) -> None:
    if message.chat.type != "private" or message.from_user is None:
        return
    await state.clear()
    async with SessionLocal() as session:
        user = await get_or_create_user(session, message.from_user)
        ticket = await find_active_ticket(session, user.id)
        await session.commit()
    if ticket is not None:
        await message.answer(
            await render_bot_text("support_ticket_exists", ticket_id=ticket.id),
            parse_mode="HTML",
            reply_markup=support_reply_keyboard(ticket.id),
        )
        return
    await state.set_state(SupportForm.description)
    await message.answer(await render_bot_text("support_prompt"), parse_mode="HTML")


@router.message(SupportForm.description)
async def create_support_ticket(message: Message, state: FSMContext) -> None:
    if message.from_user is None or not message.text or len(message.text.strip()) < 3:
        await message.answer("Опишите проблему текстом, минимум в трёх символах.")
        return
    text = message.text.strip()[:4000]
    async with SessionLocal() as session:
        user = await get_or_create_user(session, message.from_user)
        existing = await find_active_ticket(session, user.id)
        if existing is not None:
            await session.commit()
            await state.clear()
            await message.answer(
                await render_bot_text("support_ticket_exists", ticket_id=existing.id),
                parse_mode="HTML",
                reply_markup=support_reply_keyboard(existing.id),
            )
            return
        ticket = SupportTicket(user_id=user.id, status="open")
        session.add(ticket)
        await session.flush()
        session.add(
            SupportMessage(
                ticket_id=ticket.id,
                sender_type="user",
                text=text,
            )
        )
        session.add(
            AuditLog(
                action="support_ticket_created",
                entity_type="support_ticket",
                entity_id=ticket.id,
                payload_json={
                    "user_id": user.id,
                    "telegram_id": user.telegram_id,
                },
            )
        )
        await session.commit()
        await session.refresh(ticket, attribute_names=["user"])
    await state.clear()
    await message.answer(
        await render_bot_text("support_ticket_created", ticket_id=ticket.id),
        parse_mode="HTML",
        reply_markup=support_reply_keyboard(ticket.id),
    )
    await notify_staff_new_ticket(message.bot, ticket, text)


@router.callback_query(F.data.startswith("support_reply:"))
async def begin_support_reply(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.from_user is None:
        return
    ticket_id = int(callback.data.rsplit(":", 1)[1])
    async with SessionLocal() as session:
        result = await session.execute(
            select(SupportTicket)
            .join(SupportTicket.user)
            .where(
                SupportTicket.id == ticket_id,
                SupportTicket.status.in_(("open", "in_progress")),
            )
            .options(selectinload(SupportTicket.user))
        )
        ticket = result.scalar_one_or_none()
    if ticket is None or ticket.user.telegram_id != callback.from_user.id:
        await callback.answer(
            await render_bot_text("support_ticket_unavailable"),
            show_alert=True,
        )
        return
    await state.set_state(SupportForm.reply)
    await state.update_data(support_ticket_id=ticket_id)
    if callback.message:
        await callback.message.answer(
            await render_bot_text("support_reply_prompt", ticket_id=ticket_id),
            parse_mode="HTML",
        )
    await callback.answer()


@router.message(SupportForm.reply)
async def add_support_reply(message: Message, state: FSMContext) -> None:
    if message.from_user is None or not message.text or len(message.text.strip()) < 1:
        await message.answer("Отправьте ответ текстовым сообщением.")
        return
    data = await state.get_data()
    ticket_id = int(data["support_ticket_id"])
    text = message.text.strip()[:4000]
    assigned_telegram_id: int | None = None
    async with SessionLocal() as session:
        result = await session.execute(
            select(SupportTicket)
            .join(SupportTicket.user)
            .options(
                selectinload(SupportTicket.user),
                selectinload(SupportTicket.assigned_admin),
            )
            .where(
                SupportTicket.id == ticket_id,
                SupportTicket.status.in_(("open", "in_progress")),
            )
        )
        ticket = result.scalar_one_or_none()
        if ticket is None or ticket.user.telegram_id != message.from_user.id:
            await state.clear()
            await message.answer(
                await render_bot_text("support_ticket_unavailable"),
                parse_mode="HTML",
            )
            return
        session.add(
            SupportMessage(
                ticket_id=ticket.id,
                sender_type="user",
                text=text,
            )
        )
        ticket.updated_at = datetime.now(timezone.utc)
        if ticket.assigned_admin:
            assigned_telegram_id = ticket.assigned_admin.telegram_id
        session.add(
            AuditLog(
                action="support_user_replied",
                entity_type="support_ticket",
                entity_id=ticket.id,
                payload_json={
                    "user_id": ticket.user_id,
                    "telegram_id": ticket.user.telegram_id,
                },
            )
        )
        await session.commit()
    await state.clear()
    await message.answer(
        await render_bot_text("support_reply_received", ticket_id=ticket_id),
        parse_mode="HTML",
        reply_markup=support_reply_keyboard(ticket_id),
    )
    if assigned_telegram_id:
        try:
            await message.bot.send_message(
                assigned_telegram_id,
                f"💬 Новый ответ пользователя в обращении №{ticket_id}.",
            )
        except Exception:
            pass
