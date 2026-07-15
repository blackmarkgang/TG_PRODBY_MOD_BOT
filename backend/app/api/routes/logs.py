from aiogram import Bot
from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_admin
from app.core.config import settings
from app.db.models import AdminUser, AuditLog, User
from app.db.session import get_session

router = APIRouter()


@router.get("")
async def list_logs(
    limit: int = Query(default=200, ge=1, le=500),
    _: AdminUser = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    result = await session.execute(
        select(AuditLog, AdminUser)
        .outerjoin(AdminUser, AdminUser.id == AuditLog.admin_id)
        .order_by(desc(AuditLog.created_at))
        .limit(limit)
    )
    rows = result.all()
    user_ids: set[int] = set()
    telegram_ids: set[int] = set()
    for log, admin in rows:
        payload = log.payload_json or {}
        if admin is not None:
            telegram_ids.add(admin.telegram_id)
        if isinstance(payload.get("user_id"), int):
            user_ids.add(payload["user_id"])
        if log.entity_type == "user" and log.entity_id is not None:
            user_ids.add(log.entity_id)
        if isinstance(payload.get("telegram_id"), int):
            telegram_ids.add(payload["telegram_id"])

    users_by_id: dict[int, User] = {}
    users_by_telegram_id: dict[int, User] = {}
    if user_ids or telegram_ids:
        users_result = await session.execute(
            select(User).where(
                or_(User.id.in_(user_ids), User.telegram_id.in_(telegram_ids))
            )
        )
        for user in users_result.scalars().all():
            users_by_id[user.id] = user
            users_by_telegram_id[user.telegram_id] = user

    return [
        {
            "id": log.id,
            "action": log.action,
            "entity_type": log.entity_type,
            "entity_id": log.entity_id,
            "payload": log.payload_json,
            "admin_telegram_id": admin.telegram_id if admin is not None else None,
            "actor": serialize_actor(log, admin, users_by_id, users_by_telegram_id),
            "created_at": log.created_at,
        }
        for log, admin in rows
    ]


def serialize_actor(
    log: AuditLog,
    admin: AdminUser | None,
    users_by_id: dict[int, User],
    users_by_telegram_id: dict[int, User],
) -> dict:
    payload = log.payload_json or {}
    if admin is not None:
        fallback = users_by_telegram_id.get(admin.telegram_id)
        return {
            "type": "admin",
            "telegram_id": admin.telegram_id,
            "username": admin.username or (fallback.username if fallback else None),
            "first_name": admin.first_name or (fallback.first_name if fallback else None),
            "last_name": admin.last_name or (fallback.last_name if fallback else None),
        }

    user_id = payload.get("user_id")
    if not isinstance(user_id, int) and log.entity_type == "user":
        user_id = log.entity_id
    telegram_id = payload.get("telegram_id")
    user = users_by_id.get(user_id) if isinstance(user_id, int) else None
    if user is None and isinstance(telegram_id, int):
        user = users_by_telegram_id.get(telegram_id)
    if user is not None or isinstance(telegram_id, int):
        return {
            "type": "user",
            "telegram_id": user.telegram_id if user is not None else telegram_id,
            "username": user.username if user is not None else payload.get("username"),
            "first_name": user.first_name if user is not None else payload.get("first_name"),
            "last_name": user.last_name if user is not None else payload.get("last_name"),
        }

    return {
        "type": "bot",
        "telegram_id": None,
        "username": None,
        "first_name": None,
        "last_name": None,
    }


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
