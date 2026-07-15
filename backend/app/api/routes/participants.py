from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_admin
from app.db.models import AdminUser, Application, AuditLog, CommunityRole, User
from app.db.session import get_session
from app.services.role_service import get_user_roles_map, set_user_roles

router = APIRouter()


class RoleAssignmentPayload(BaseModel):
    role_codes: list[str]


@router.get("/roles")
async def list_roles(
    _: AdminUser = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
) -> list[dict[str, str]]:
    result = await session.execute(select(CommunityRole).order_by(CommunityRole.title))
    return [{"code": role.code, "title": role.title} for role in result.scalars().all()]


@router.get("")
async def list_participants(
    _: AdminUser = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    users_result = await session.execute(select(User).order_by(desc(User.created_at)))
    users = list(users_result.scalars().all())
    user_ids = [user.id for user in users]
    roles_map = await get_user_roles_map(session, user_ids)

    latest_applications: dict[int, Application] = {}
    if user_ids:
        applications_result = await session.execute(
            select(Application)
            .where(Application.user_id.in_(user_ids))
            .order_by(desc(Application.created_at))
        )
        for application in applications_result.scalars().all():
            latest_applications.setdefault(application.user_id, application)

    return [
        {
            "id": user.id,
            "telegram_id": user.telegram_id,
            "username": user.username,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "created_at": user.created_at,
            "is_banned": user.is_banned,
            "roles": roles_map.get(user.id, []),
            "latest_application_status": (
                latest_applications[user.id].status if user.id in latest_applications else None
            ),
        }
        for user in users
    ]


@router.put("/{user_id}/roles")
async def update_participant_roles(
    user_id: int,
    payload: RoleAssignmentPayload,
    admin: AdminUser = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
) -> dict[str, list[dict[str, str]]]:
    try:
        roles = await set_user_roles(session, user_id, payload.role_codes)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    session.add(
        AuditLog(
            admin_id=admin.id,
            action="assign_roles",
            entity_type="user",
            entity_id=user_id,
            payload_json={"role_codes": [role.code for role in roles]},
        )
    )
    await session.commit()
    return {"roles": [{"code": role.code, "title": role.title} for role in roles]}
