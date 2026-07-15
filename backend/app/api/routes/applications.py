from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_admin
from app.db.models import AdminUser, Application, AuditLog
from app.db.session import get_session

router = APIRouter()


class ReviewPayload(BaseModel):
    comment: str | None = None


@router.get("")
async def list_applications(
    status: str | None = None,
    _: AdminUser = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    query = select(Application).options(selectinload(Application.user)).order_by(desc(Application.created_at))
    if status:
        query = query.where(Application.status == status)

    result = await session.execute(query)
    applications = result.scalars().all()
    return [
        {
            "id": item.id,
            "status": item.status,
            "age": item.age,
            "music_role": item.music_role,
            "answers": item.answers_json,
            "created_at": item.created_at,
            "user": {
                "telegram_id": item.user.telegram_id,
                "username": item.user.username,
                "first_name": item.user.first_name,
                "last_name": item.user.last_name,
            },
        }
        for item in applications
    ]


@router.post("/{application_id}/approve")
async def approve_application(
    application_id: int,
    payload: ReviewPayload,
    admin: AdminUser = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    application = await session.get(Application, application_id)
    if application is None:
        raise HTTPException(status_code=404, detail="Application not found")

    application.status = "approved"
    application.admin_comment = payload.comment
    application.reviewed_by_admin_id = admin.id
    application.reviewed_at = datetime.now(timezone.utc)
    session.add(AuditLog(admin_id=admin.id, action="approve", entity_type="application", entity_id=application.id))
    await session.commit()
    return {"status": "approved"}


@router.post("/{application_id}/reject")
async def reject_application(
    application_id: int,
    payload: ReviewPayload,
    admin: AdminUser = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    application = await session.get(Application, application_id)
    if application is None:
        raise HTTPException(status_code=404, detail="Application not found")

    application.status = "rejected"
    application.admin_comment = payload.comment
    application.reviewed_by_admin_id = admin.id
    application.reviewed_at = datetime.now(timezone.utc)
    session.add(AuditLog(admin_id=admin.id, action="reject", entity_type="application", entity_id=application.id))
    await session.commit()
    return {"status": "rejected"}

