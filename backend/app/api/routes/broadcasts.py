from datetime import datetime, timezone

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from aiogram.types import LinkPreviewOptions
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_full_admin
from app.core.config import settings
from app.db.models import AdminUser, AuditLog, Broadcast, BroadcastRecipient
from app.db.session import get_session
from app.services.broadcast_service import (
    BROADCAST_AUDIENCES,
    get_broadcast_recipients,
)


router = APIRouter()


class AudiencePayload(BaseModel):
    audience: str = "all"
    role_codes: list[str] = Field(default_factory=list, max_length=50)

    @field_validator("audience")
    @classmethod
    def validate_audience(cls, value: str) -> str:
        if value not in BROADCAST_AUDIENCES:
            raise ValueError("Неизвестная аудитория")
        return value


class BroadcastPayload(AudiencePayload):
    message: str = Field(min_length=1, max_length=4096)
    scheduled_at: datetime | None = None
    disable_link_preview: bool = True

    @field_validator("message")
    @classmethod
    def validate_message(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Введите текст сообщения")
        return value

    @field_validator("scheduled_at")
    @classmethod
    def validate_scheduled_at(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.tzinfo is None:
            raise ValueError("Укажите часовой пояс времени отправки")
        return value


class BroadcastTestPayload(BaseModel):
    message: str = Field(min_length=1, max_length=4096)
    disable_link_preview: bool = True

    @field_validator("message")
    @classmethod
    def validate_message(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Введите текст сообщения")
        return value


@router.post("/audience-count")
async def audience_count(
    payload: AudiencePayload,
    _: AdminUser = Depends(get_current_full_admin),
    session: AsyncSession = Depends(get_session),
) -> dict[str, int]:
    try:
        recipients = await get_broadcast_recipients(
            session,
            payload.audience,
            payload.role_codes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"count": len(recipients)}


@router.get("")
async def list_broadcasts(
    _: AdminUser = Depends(get_current_full_admin),
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    result = await session.execute(
        select(Broadcast)
        .options(selectinload(Broadcast.created_by))
        .order_by(desc(Broadcast.created_at))
        .limit(100)
    )
    return [serialize_broadcast(item) for item in result.scalars().all()]


@router.post("", status_code=201)
async def create_broadcast(
    payload: BroadcastPayload,
    admin: AdminUser = Depends(get_current_full_admin),
    session: AsyncSession = Depends(get_session),
) -> dict:
    try:
        users = await get_broadcast_recipients(
            session,
            payload.audience,
            payload.role_codes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not users:
        raise HTTPException(status_code=400, detail="В выбранной аудитории нет получателей")

    now = datetime.now(timezone.utc)
    scheduled_at = payload.scheduled_at or now
    if scheduled_at < now:
        scheduled_at = now
    broadcast = Broadcast(
        created_by_admin_id=admin.id,
        status="scheduled",
        message=payload.message,
        audience=payload.audience,
        role_codes_json=list(dict.fromkeys(payload.role_codes)),
        disable_link_preview=payload.disable_link_preview,
        scheduled_at=scheduled_at,
        target_count=len(users),
    )
    session.add(broadcast)
    await session.flush()
    session.add_all(
        [
            BroadcastRecipient(
                broadcast_id=broadcast.id,
                user_id=user.id,
                telegram_id=user.telegram_id,
            )
            for user in users
        ]
    )
    session.add(
        AuditLog(
            admin_id=admin.id,
            action="create_broadcast",
            entity_type="broadcast",
            entity_id=broadcast.id,
            payload_json={
                "audience": broadcast.audience,
                "role_codes": broadcast.role_codes_json,
                "target_count": broadcast.target_count,
                "scheduled_at": broadcast.scheduled_at.isoformat(),
            },
        )
    )
    await session.commit()
    await session.refresh(broadcast)
    broadcast.created_by = admin
    return serialize_broadcast(broadcast)


@router.post("/test")
async def send_test_broadcast(
    payload: BroadcastTestPayload,
    admin: AdminUser = Depends(get_current_full_admin),
) -> dict[str, bool]:
    bot = Bot(settings.bot_token)
    try:
        await bot.send_message(
            admin.telegram_id,
            payload.message,
            link_preview_options=LinkPreviewOptions(
                is_disabled=payload.disable_link_preview
            ),
        )
    except TelegramAPIError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Telegram не доставил тест: {exc}",
        ) from exc
    finally:
        await bot.session.close()
    return {"sent": True}


@router.post("/{broadcast_id}/cancel")
async def cancel_broadcast(
    broadcast_id: int,
    admin: AdminUser = Depends(get_current_full_admin),
    session: AsyncSession = Depends(get_session),
) -> dict:
    result = await session.execute(
        select(Broadcast)
        .options(selectinload(Broadcast.created_by))
        .where(Broadcast.id == broadcast_id)
    )
    broadcast = result.scalar_one_or_none()
    if broadcast is None:
        raise HTTPException(status_code=404, detail="Рассылка не найдена")
    if broadcast.status != "scheduled":
        raise HTTPException(
            status_code=409,
            detail="Можно отменить только запланированную рассылку",
        )

    broadcast.status = "canceled"
    broadcast.completed_at = datetime.now(timezone.utc)
    session.add(
        AuditLog(
            admin_id=admin.id,
            action="cancel_broadcast",
            entity_type="broadcast",
            entity_id=broadcast.id,
            payload_json={"target_count": broadcast.target_count},
        )
    )
    await session.commit()
    return serialize_broadcast(broadcast)


def serialize_broadcast(broadcast: Broadcast) -> dict:
    creator = broadcast.created_by
    return {
        "id": broadcast.id,
        "status": broadcast.status,
        "message": broadcast.message,
        "audience": broadcast.audience,
        "role_codes": broadcast.role_codes_json,
        "disable_link_preview": broadcast.disable_link_preview,
        "scheduled_at": broadcast.scheduled_at,
        "target_count": broadcast.target_count,
        "sent_count": broadcast.sent_count,
        "failed_count": broadcast.failed_count,
        "created_at": broadcast.created_at,
        "started_at": broadcast.started_at,
        "completed_at": broadcast.completed_at,
        "created_by": {
            "id": creator.id,
            "telegram_id": creator.telegram_id,
            "username": creator.username,
            "first_name": creator.first_name,
            "last_name": creator.last_name,
        },
    }
