from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import CommunityRole, User, UserRole


async def set_user_role(session: AsyncSession, user_id: int, role_code: str) -> CommunityRole:
    user = await session.get(User, user_id)
    if user is None:
        raise ValueError("Пользователь не найден")

    result = await session.execute(select(CommunityRole).where(CommunityRole.code == role_code))
    role = result.scalar_one_or_none()
    if role is None:
        raise ValueError("Роль не найдена")

    await session.execute(delete(UserRole).where(UserRole.user_id == user_id))
    session.add(UserRole(user_id=user_id, role_id=role.id))
    await session.flush()
    return role


async def get_user_roles_map(
    session: AsyncSession,
    user_ids: list[int],
) -> dict[int, list[dict[str, str]]]:
    if not user_ids:
        return {}

    result = await session.execute(
        select(UserRole.user_id, CommunityRole.code, CommunityRole.title)
        .join(CommunityRole, CommunityRole.id == UserRole.role_id)
        .where(UserRole.user_id.in_(user_ids))
        .order_by(CommunityRole.title)
    )
    roles: dict[int, list[dict[str, str]]] = {}
    for user_id, code, title in result.all():
        roles.setdefault(user_id, []).append({"code": code, "title": title})
    return roles
