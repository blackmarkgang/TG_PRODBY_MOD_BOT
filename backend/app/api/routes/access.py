from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_admin, get_current_full_admin
from app.db.models import AdminUser, AuditLog, User
from app.db.session import get_session

router = APIRouter()
MANAGED_ROLES = {"admin", "moderator"}


class StaffPayload(BaseModel):
    telegram_id: int = Field(gt=0)
    role: str

    @field_validator("role")
    @classmethod
    def validate_role(cls, value: str) -> str:
        if value not in MANAGED_ROLES:
            raise ValueError("Можно назначить роль admin или moderator")
        return value


class StaffRolePayload(BaseModel):
    role: str

    @field_validator("role")
    @classmethod
    def validate_role(cls, value: str) -> str:
        if value not in MANAGED_ROLES:
            raise ValueError("Можно назначить роль admin или moderator")
        return value


@router.get("/me")
async def current_admin(admin: AdminUser = Depends(get_current_admin)) -> dict:
    return serialize_admin(admin)


@router.get("/admins")
async def list_admins(
    _: AdminUser = Depends(get_current_full_admin),
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    result = await session.execute(
        select(AdminUser, User)
        .outerjoin(User, User.telegram_id == AdminUser.telegram_id)
        .where(AdminUser.is_active.is_(True))
        .order_by(AdminUser.role, AdminUser.telegram_id)
    )
    return [serialize_admin(admin, user) for admin, user in result.all()]


@router.post("/admins", status_code=201)
async def add_admin(
    payload: StaffPayload,
    current: AdminUser = Depends(get_current_full_admin),
    session: AsyncSession = Depends(get_session),
) -> dict:
    result = await session.execute(
        select(AdminUser).where(AdminUser.telegram_id == payload.telegram_id)
    )
    staff = result.scalar_one_or_none()
    action = "grant_staff_access"
    if staff is None:
        staff = AdminUser(telegram_id=payload.telegram_id, role=payload.role, is_active=True)
        session.add(staff)
        await session.flush()
    else:
        if staff.role == "owner":
            raise HTTPException(status_code=409, detail="Права владельца нельзя изменить")
        if staff.is_active:
            raise HTTPException(status_code=409, detail="У пользователя уже есть доступ к панели")
        staff.role = payload.role
        staff.is_active = True
        action = "restore_staff_access"

    await fill_profile_from_user(session, staff)
    session.add(
        AuditLog(
            admin_id=current.id,
            action=action,
            entity_type="admin_user",
            entity_id=staff.id,
            payload_json={"telegram_id": staff.telegram_id, "role": staff.role},
        )
    )
    await session.commit()
    return serialize_admin(staff)


@router.patch("/admins/{admin_id}")
async def update_admin_role(
    admin_id: int,
    payload: StaffRolePayload,
    current: AdminUser = Depends(get_current_full_admin),
    session: AsyncSession = Depends(get_session),
) -> dict:
    staff = await session.get(AdminUser, admin_id)
    if staff is None or not staff.is_active:
        raise HTTPException(status_code=404, detail="Сотрудник не найден")
    ensure_staff_can_be_changed(current, staff)
    staff.role = payload.role
    session.add(
        AuditLog(
            admin_id=current.id,
            action="update_staff_access",
            entity_type="admin_user",
            entity_id=staff.id,
            payload_json={"telegram_id": staff.telegram_id, "role": staff.role},
        )
    )
    await session.commit()
    return serialize_admin(staff)


@router.delete("/admins/{admin_id}", status_code=204)
async def revoke_admin_access(
    admin_id: int,
    current: AdminUser = Depends(get_current_full_admin),
    session: AsyncSession = Depends(get_session),
) -> Response:
    staff = await session.get(AdminUser, admin_id)
    if staff is None or not staff.is_active:
        raise HTTPException(status_code=404, detail="Сотрудник не найден")
    ensure_staff_can_be_changed(current, staff)
    staff.is_active = False
    session.add(
        AuditLog(
            admin_id=current.id,
            action="revoke_staff_access",
            entity_type="admin_user",
            entity_id=staff.id,
            payload_json={"telegram_id": staff.telegram_id, "role": staff.role},
        )
    )
    await session.commit()
    return Response(status_code=204)


def ensure_staff_can_be_changed(current: AdminUser, staff: AdminUser) -> None:
    if staff.id == current.id:
        raise HTTPException(status_code=409, detail="Нельзя изменить собственный доступ")
    if staff.role == "owner":
        raise HTTPException(status_code=409, detail="Права владельца нельзя изменить")


async def fill_profile_from_user(session: AsyncSession, admin: AdminUser) -> None:
    result = await session.execute(select(User).where(User.telegram_id == admin.telegram_id))
    user = result.scalar_one_or_none()
    if user is not None:
        admin.username = user.username
        admin.first_name = user.first_name
        admin.last_name = user.last_name


def serialize_admin(admin: AdminUser, fallback: User | None = None) -> dict:
    return {
        "id": admin.id,
        "telegram_id": admin.telegram_id,
        "role": admin.role,
        "username": admin.username or (fallback.username if fallback else None),
        "first_name": admin.first_name or (fallback.first_name if fallback else None),
        "last_name": admin.last_name or (fallback.last_name if fallback else None),
    }
