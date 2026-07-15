import json

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import validate_telegram_init_data
from app.core.config import settings
from app.db.models import AdminUser
from app.db.session import get_session

FULL_ADMIN_ROLES = {"owner", "admin"}


async def get_current_admin(
    authorization: str | None = Header(default=None),
    x_dev_admin_id: int | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
) -> AdminUser:
    if settings.app_env == "local" and x_dev_admin_id is not None:
        return await find_active_admin(session, x_dev_admin_id)

    if not authorization or not authorization.startswith("tma "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Откройте панель через Telegram",
        )

    payload = validate_telegram_init_data(authorization.removeprefix("tma ").strip())
    user_raw = payload.get("user")
    if not user_raw:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Telegram не передал данные пользователя",
        )

    telegram_user = json.loads(user_raw)
    telegram_id = int(telegram_user["id"])
    admin = await find_active_admin(session, telegram_id)
    profile = {
        "username": telegram_user.get("username"),
        "first_name": telegram_user.get("first_name"),
        "last_name": telegram_user.get("last_name"),
    }
    if any(getattr(admin, field) != value for field, value in profile.items()):
        for field, value in profile.items():
            setattr(admin, field, value)
        await session.commit()
    return admin


async def find_active_admin(session: AsyncSession, telegram_id: int) -> AdminUser:
    result = await session.execute(
        select(AdminUser).where(AdminUser.telegram_id == telegram_id, AdminUser.is_active.is_(True))
    )
    admin = result.scalar_one_or_none()
    if admin is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="У вас нет доступа к панели",
        )
    return admin


async def get_current_full_admin(
    admin: AdminUser = Depends(get_current_admin),
) -> AdminUser:
    if admin.role not in FULL_ADMIN_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Недостаточно прав для этого раздела",
        )
    return admin
