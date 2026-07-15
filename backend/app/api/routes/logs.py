from aiogram import Bot
from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_admin
from app.core.config import settings
from app.db.models import AdminUser, AuditLog
from app.db.session import get_session

router = APIRouter()


@router.get("")
async def list_logs(
    limit: int = Query(default=200, ge=1, le=500),
    _: AdminUser = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    result = await session.execute(
        select(AuditLog, AdminUser.telegram_id)
        .outerjoin(AdminUser, AdminUser.id == AuditLog.admin_id)
        .order_by(desc(AuditLog.created_at))
        .limit(limit)
    )
    return [
        {
            "id": log.id,
            "action": log.action,
            "entity_type": log.entity_type,
            "entity_id": log.entity_id,
            "payload": log.payload_json,
            "admin_telegram_id": admin_telegram_id,
            "created_at": log.created_at,
        }
        for log, admin_telegram_id in result.all()
    ]


@router.get("/status")
async def bot_status(_: AdminUser = Depends(get_current_admin)) -> dict:
    bot = Bot(settings.bot_token)
    try:
        me = await bot.get_me()
        return {
            "telegram_api": True,
            "bot_id": me.id,
            "username": me.username,
            "mode": "polling",
        }
    except Exception:
        return {"telegram_api": False, "bot_id": None, "username": None, "mode": "polling"}
    finally:
        await bot.session.close()
