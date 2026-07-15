from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models import AdminUser, CommunityRole


DEFAULT_COMMUNITY_ROLES = [
    ("artist", "Artist"),
    ("producer", "Producer"),
    ("beatmaker", "Beatmaker"),
    ("listener", "Listener"),
    ("sound_engineer", "Sound engineer"),
    ("designer", "Designer"),
    ("editor", "Editor"),
]


async def seed_defaults(session: AsyncSession) -> None:
    for index, telegram_id in enumerate(settings.admin_ids):
        result = await session.execute(select(AdminUser).where(AdminUser.telegram_id == telegram_id))
        if result.scalar_one_or_none() is None:
            session.add(AdminUser(telegram_id=telegram_id, role="owner" if index == 0 else "admin"))

    for code, title in DEFAULT_COMMUNITY_ROLES:
        result = await session.execute(select(CommunityRole).where(CommunityRole.code == code))
        if result.scalar_one_or_none() is None:
            session.add(CommunityRole(code=code, title=title))

    await session.commit()

