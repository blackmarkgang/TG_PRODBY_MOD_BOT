import json

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import validate_telegram_init_data
from app.db.models import AdminUser
from app.db.session import get_session


async def get_current_admin(
    authorization: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
) -> AdminUser:
    if not authorization or not authorization.startswith("tma "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing Telegram Mini App auth")

    payload = validate_telegram_init_data(authorization.removeprefix("tma ").strip())
    user_raw = payload.get("user")
    if not user_raw:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing Telegram user")

    telegram_user = json.loads(user_raw)
    telegram_id = int(telegram_user["id"])
    result = await session.execute(
        select(AdminUser).where(AdminUser.telegram_id == telegram_id, AdminUser.is_active.is_(True))
    )
    admin = result.scalar_one_or_none()
    if admin is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not an admin")
    return admin

