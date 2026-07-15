from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models import AdminUser, CommunityRole


DEFAULT_COMMUNITY_ROLES = [
    ("artist", "Артист"),
    ("producer", "Продюсер"),
    ("beatmaker", "Битмейкер"),
    ("listener", "Слушатель"),
    ("sound_engineer", "Звукоинженер"),
    ("designer", "Дизайнер"),
    ("editor", "Монтажер"),
    ("operator", "Оператор"),
    ("organizer", "Организатор"),
    ("other", "Другое"),
]


async def seed_defaults(session: AsyncSession) -> None:
    for index, telegram_id in enumerate(settings.admin_ids):
        result = await session.execute(select(AdminUser).where(AdminUser.telegram_id == telegram_id))
        if result.scalar_one_or_none() is None:
            session.add(AdminUser(telegram_id=telegram_id, role="owner" if index == 0 else "admin"))

    for code, title in DEFAULT_COMMUNITY_ROLES:
        result = await session.execute(select(CommunityRole).where(CommunityRole.code == code))
        role = result.scalar_one_or_none()
        if role is None:
            session.add(CommunityRole(code=code, title=title))
        else:
            role.title = title

    await session.commit()
