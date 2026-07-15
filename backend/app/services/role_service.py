from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import CommunityRole, User, UserRole


async def set_user_roles(
    session: AsyncSession,
    user_id: int,
    role_codes: list[str],
) -> list[CommunityRole]:
    user = await session.get(User, user_id)
    if user is None:
        raise ValueError("Пользователь не найден")
    if user.is_banned and role_codes:
        raise ValueError("Нельзя назначить роли заблокированному пользователю")

    unique_codes = list(dict.fromkeys(role_codes))
    result = await session.execute(
        select(CommunityRole)
        .where(CommunityRole.code.in_(unique_codes))
        .order_by(CommunityRole.title)
    )
    roles = list(result.scalars().all())
    if len(roles) != len(unique_codes):
        found_codes = {role.code for role in roles}
        unknown_codes = sorted(set(unique_codes) - found_codes)
        raise ValueError(f"Неизвестные роли: {', '.join(unknown_codes)}")

    await session.execute(delete(UserRole).where(UserRole.user_id == user_id))
    for role in roles:
        session.add(UserRole(user_id=user_id, role_id=role.id))
    await session.flush()
    return roles


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
