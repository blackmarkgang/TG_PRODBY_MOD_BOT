from datetime import datetime, timezone
from html import escape

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_admin
from app.core.config import settings
from app.db.models import (
    AdminUser,
    AuditLog,
    SupportMessage,
    SupportTicket,
)
from app.db.session import get_session
from app.services.bot_text_service import render_bot_text

router = APIRouter()


class SupportReplyPayload(BaseModel):
    text: str = Field(min_length=1, max_length=4000)


def serialize_admin(admin: AdminUser | None) -> dict | None:
    if admin is None:
        return None
    return {
        "id": admin.id,
        "telegram_id": admin.telegram_id,
        "username": admin.username,
        "first_name": admin.first_name,
        "last_name": admin.last_name,
    }


def serialize_ticket(ticket: SupportTicket) -> dict:
    return {
        "id": ticket.id,
        "status": ticket.status,
        "created_at": ticket.created_at,
        "updated_at": ticket.updated_at,
        "closed_at": ticket.closed_at,
        "user": {
            "id": ticket.user.id,
            "telegram_id": ticket.user.telegram_id,
            "username": ticket.user.username,
            "first_name": ticket.user.first_name,
            "last_name": ticket.user.last_name,
        },
        "assigned_admin": serialize_admin(ticket.assigned_admin),
        "messages": [
            {
                "id": message.id,
                "sender_type": message.sender_type,
                "text": message.text,
                "created_at": message.created_at,
                "admin": serialize_admin(message.admin),
            }
            for message in ticket.messages
        ],
    }


async def get_ticket(
    session: AsyncSession,
    ticket_id: int,
    *,
    for_update: bool = False,
) -> SupportTicket:
    query = (
        select(SupportTicket)
        .where(SupportTicket.id == ticket_id)
        .options(
            selectinload(SupportTicket.user),
            selectinload(SupportTicket.assigned_admin),
            selectinload(SupportTicket.messages).selectinload(SupportMessage.admin),
        )
    )
    if for_update:
        query = query.with_for_update()
    result = await session.execute(query)
    ticket = result.scalar_one_or_none()
    if ticket is None:
        raise HTTPException(status_code=404, detail="Тикет не найден")
    return ticket


def require_assignee(ticket: SupportTicket, admin: AdminUser) -> None:
    if ticket.status == "closed":
        raise HTTPException(status_code=409, detail="Тикет уже закрыт")
    if ticket.assigned_admin_id != admin.id:
        raise HTTPException(
            status_code=409,
            detail="С тикетом может работать только назначенный сотрудник",
        )


@router.get("")
async def list_support_tickets(
    _: AdminUser = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    result = await session.execute(
        select(SupportTicket)
        .options(
            selectinload(SupportTicket.user),
            selectinload(SupportTicket.assigned_admin),
            selectinload(SupportTicket.messages).selectinload(SupportMessage.admin),
        )
        .order_by(
            (SupportTicket.status == "closed"),
            desc(SupportTicket.updated_at),
        )
    )
    return [serialize_ticket(ticket) for ticket in result.scalars().all()]


@router.post("/{ticket_id}/claim")
async def claim_support_ticket(
    ticket_id: int,
    admin: AdminUser = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
) -> dict:
    ticket = await get_ticket(session, ticket_id, for_update=True)
    if ticket.status == "closed":
        raise HTTPException(status_code=409, detail="Тикет уже закрыт")
    if ticket.assigned_admin_id not in {None, admin.id}:
        raise HTTPException(status_code=409, detail="Тикет уже взят другим сотрудником")
    ticket.assigned_admin_id = admin.id
    ticket.status = "in_progress"
    ticket.updated_at = datetime.now(timezone.utc)
    session.add(
        AuditLog(
            admin_id=admin.id,
            action="support_ticket_claimed",
            entity_type="support_ticket",
            entity_id=ticket.id,
        )
    )
    await session.commit()
    return serialize_ticket(await get_ticket(session, ticket.id))


@router.post("/{ticket_id}/reply")
async def reply_to_support_ticket(
    ticket_id: int,
    payload: SupportReplyPayload,
    admin: AdminUser = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
) -> dict:
    ticket = await get_ticket(session, ticket_id, for_update=True)
    require_assignee(ticket, admin)
    text = payload.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Ответ не может быть пустым")
    session.add(
        SupportMessage(
            ticket_id=ticket.id,
            sender_type="admin",
            admin_id=admin.id,
            text=text,
        )
    )
    ticket.updated_at = datetime.now(timezone.utc)
    session.add(
        AuditLog(
            admin_id=admin.id,
            action="support_admin_replied",
            entity_type="support_ticket",
            entity_id=ticket.id,
            payload_json={
                "user_id": ticket.user_id,
                "telegram_id": ticket.user.telegram_id,
            },
        )
    )
    await session.commit()

    delivered = False
    warning: str | None = None
    bot = Bot(settings.bot_token)
    try:
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="✍️ Ответить",
                        callback_data=f"support_reply:{ticket.id}",
                    )
                ]
            ]
        )
        await bot.send_message(
            ticket.user.telegram_id,
            await render_bot_text(
                "support_admin_reply",
                ticket_id=ticket.id,
                message=escape(text),
            ),
            parse_mode="HTML",
            reply_markup=keyboard,
        )
        delivered = True
    except TelegramAPIError:
        warning = "Ответ сохранён, но бот не смог доставить его пользователю."
    finally:
        await bot.session.close()
    return {
        "ticket": serialize_ticket(await get_ticket(session, ticket.id)),
        "delivered": delivered,
        "warning": warning,
    }


@router.post("/{ticket_id}/release")
async def release_support_ticket(
    ticket_id: int,
    admin: AdminUser = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
) -> dict:
    ticket = await get_ticket(session, ticket_id, for_update=True)
    require_assignee(ticket, admin)
    ticket.assigned_admin_id = None
    ticket.status = "open"
    ticket.updated_at = datetime.now(timezone.utc)
    session.add(
        AuditLog(
            admin_id=admin.id,
            action="support_ticket_released",
            entity_type="support_ticket",
            entity_id=ticket.id,
        )
    )
    await session.commit()
    return serialize_ticket(await get_ticket(session, ticket.id))


@router.post("/{ticket_id}/close")
async def close_support_ticket(
    ticket_id: int,
    admin: AdminUser = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
) -> dict:
    ticket = await get_ticket(session, ticket_id, for_update=True)
    require_assignee(ticket, admin)
    now = datetime.now(timezone.utc)
    ticket.status = "closed"
    ticket.closed_at = now
    ticket.updated_at = now
    session.add(
        AuditLog(
            admin_id=admin.id,
            action="support_ticket_closed",
            entity_type="support_ticket",
            entity_id=ticket.id,
            payload_json={
                "user_id": ticket.user_id,
                "telegram_id": ticket.user.telegram_id,
            },
        )
    )
    await session.commit()

    warning: str | None = None
    bot = Bot(settings.bot_token)
    try:
        await bot.send_message(
            ticket.user.telegram_id,
            await render_bot_text("support_ticket_closed", ticket_id=ticket.id),
            parse_mode="HTML",
        )
    except TelegramAPIError:
        warning = "Тикет закрыт, но бот не смог уведомить пользователя."
    finally:
        await bot.session.close()
    return {
        "ticket": serialize_ticket(await get_ticket(session, ticket.id)),
        "warning": warning,
    }
