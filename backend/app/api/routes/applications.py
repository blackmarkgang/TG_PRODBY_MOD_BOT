import base64
import hashlib
import hmac
import time
from datetime import datetime, timezone
from html import escape
from urllib.parse import quote

import httpx
from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_admin
from app.core.config import settings
from app.db.models import (
    AdminUser,
    Application,
    ApplicationFile,
    AuditLog,
    TopicWhitelist,
    UserRole,
)
from app.db.session import get_session
from app.services.notification_service import notify_application_decision
from app.services.bot_text_service import render_bot_text
from app.services.role_service import get_user_roles_map, set_user_roles

router = APIRouter()

DIRECTION_ROLE_CODES = {
    "артист": "artist",
    "битмейкер": "beatmaker",
    "слушатель": "listener",
    "креативный продакшн (видео, дизайн, монтаж)": "creative_production",
}
PREVIEW_TOKEN_TTL_SECONDS = 3_600


class ReviewPayload(BaseModel):
    comment: str | None = None
    role_codes: list[str] = Field(default_factory=list)


def create_file_preview_token(
    application_id: int,
    file_id: int,
    *,
    expires_at: int | None = None,
) -> str:
    expiration = expires_at or int(time.time()) + PREVIEW_TOKEN_TTL_SECONDS
    payload = f"{application_id}:{file_id}:{expiration}".encode()
    signature = hmac.new(settings.bot_token.encode(), payload, hashlib.sha256).digest()
    encoded_signature = base64.urlsafe_b64encode(signature).decode().rstrip("=")
    return f"{expiration}.{encoded_signature}"


def verify_file_preview_token(
    token: str,
    application_id: int,
    file_id: int,
    *,
    now: int | None = None,
) -> bool:
    try:
        expiration_text, _ = token.split(".", maxsplit=1)
        expiration = int(expiration_text)
    except (TypeError, ValueError):
        return False
    if expiration < (now or int(time.time())):
        return False
    expected_token = create_file_preview_token(
        application_id,
        file_id,
        expires_at=expiration,
    )
    return hmac.compare_digest(token, expected_token)


async def get_application_file(
    session: AsyncSession,
    application_id: int,
    file_id: int,
) -> ApplicationFile:
    result = await session.execute(
        select(ApplicationFile).where(
            ApplicationFile.id == file_id,
            ApplicationFile.application_id == application_id,
        )
    )
    application_file = result.scalar_one_or_none()
    if application_file is None or not application_file.telegram_file_id:
        raise HTTPException(status_code=404, detail="Файл не найден")
    return application_file


async def stream_telegram_file(
    application_file: ApplicationFile,
    *,
    range_header: str | None = None,
    disposition: str,
) -> StreamingResponse:
    bot = Bot(settings.bot_token)
    try:
        telegram_file = await bot.get_file(application_file.telegram_file_id)
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Telegram не вернул файл") from exc
    finally:
        await bot.session.close()

    if not telegram_file.file_path:
        raise HTTPException(status_code=502, detail="Telegram не вернул путь к файлу")

    request_headers = {"Range": range_header} if range_header else {}
    client = httpx.AsyncClient(timeout=60)
    response = await client.send(
        client.build_request(
            "GET",
            f"https://api.telegram.org/file/bot{settings.bot_token}/{telegram_file.file_path}",
            headers=request_headers,
        ),
        stream=True,
    )
    if not response.is_success:
        await response.aclose()
        await client.aclose()
        raise HTTPException(status_code=502, detail="Не удалось скачать файл из Telegram")

    async def stream_file():
        try:
            async for chunk in response.aiter_bytes():
                yield chunk
        finally:
            await response.aclose()
            await client.aclose()

    file_name = application_file.file_name or f"attachment-{application_file.id}"
    headers = {
        "Accept-Ranges": response.headers.get("accept-ranges", "bytes"),
        "Cache-Control": "private, max-age=300",
        "Content-Disposition": f"{disposition}; filename*=UTF-8''{quote(file_name)}",
    }
    for header_name in ("content-length", "content-range", "etag", "last-modified"):
        if header_value := response.headers.get(header_name):
            headers[header_name.title()] = header_value
    return StreamingResponse(
        stream_file(),
        status_code=response.status_code,
        media_type=application_file.mime_type
        or response.headers.get("content-type")
        or "application/octet-stream",
        headers=headers,
    )


def get_application_role_code(application: Application) -> str | None:
    direction = str((application.answers_json or {}).get("role_details", "")).strip().casefold()
    if direction.startswith("креативный продакшн"):
        return "creative_production"
    return DIRECTION_ROLE_CODES.get(direction)


@router.get("")
async def list_applications(
    status: str | None = None,
    _: AdminUser = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    query = (
        select(Application)
        .options(selectinload(Application.user), selectinload(Application.files))
        .order_by(Application.created_at, Application.id)
    )
    if status:
        query = query.where(Application.status == status)

    result = await session.execute(query)
    applications = result.scalars().all()
    roles_map = await get_user_roles_map(session, [item.user_id for item in applications])
    return [
        {
            "id": item.id,
            "status": item.status,
            "age": item.age,
            "music_role": item.music_role,
            "answers": item.answers_json,
            "answer_labels": item.answer_labels_json,
            "created_at": item.created_at,
            "admin_comment": item.admin_comment,
            "reviewed_at": item.reviewed_at,
            "roles": roles_map.get(item.user_id, []),
            "files": [
                {
                    "id": file.id,
                    "file_type": file.file_type,
                    "file_name": file.file_name,
                    "mime_type": file.mime_type,
                    "file_size": file.file_size,
                    "url": file.url,
                    "caption": file.caption,
                }
                for file in item.files
            ],
            "user": {
                "telegram_id": item.user.telegram_id,
                "username": item.user.username,
                "first_name": item.user.first_name,
                "last_name": item.user.last_name,
                "is_banned": item.user.is_banned,
            },
        }
        for item in applications
    ]


@router.get("/{application_id}/files/{file_id}/download")
async def download_application_file(
    application_id: int,
    file_id: int,
    _: AdminUser = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
) -> StreamingResponse:
    application_file = await get_application_file(session, application_id, file_id)
    return await stream_telegram_file(
        application_file,
        disposition="attachment",
    )


@router.post("/{application_id}/files/{file_id}/preview-token")
async def issue_application_file_preview_token(
    application_id: int,
    file_id: int,
    _: AdminUser = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    await get_application_file(session, application_id, file_id)
    return {"token": create_file_preview_token(application_id, file_id)}


@router.get("/{application_id}/files/{file_id}/preview")
async def preview_application_file(
    application_id: int,
    file_id: int,
    token: str,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> StreamingResponse:
    if not verify_file_preview_token(token, application_id, file_id):
        raise HTTPException(status_code=403, detail="Ссылка предпросмотра недействительна")
    application_file = await get_application_file(session, application_id, file_id)
    return await stream_telegram_file(
        application_file,
        range_header=request.headers.get("range"),
        disposition="inline",
    )


@router.post("/{application_id}/approve")
async def approve_application(
    application_id: int,
    payload: ReviewPayload,
    admin: AdminUser = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
) -> dict[str, bool | str | None]:
    application = await get_application_with_user(session, application_id)
    if application is None:
        raise HTTPException(status_code=404, detail="Заявка не найдена")
    if application.status != "pending":
        raise HTTPException(status_code=409, detail="Заявка уже обработана")
    role_code = get_application_role_code(application)
    try:
        roles = await set_user_roles(
            session,
            application.user_id,
            [role_code] if role_code else [],
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    application.status = "approved"
    application.admin_comment = payload.comment
    application.reviewed_by_admin_id = admin.id
    application.reviewed_at = datetime.now(timezone.utc)
    session.add(
        AuditLog(
            admin_id=admin.id,
            action="approve",
            entity_type="application",
            entity_id=application.id,
            payload_json={
                "role_codes": [role.code for role in roles],
                "direction": (application.answers_json or {}).get("role_details"),
            },
        )
    )
    await session.commit()
    delivery = await notify_application_decision(
        application,
        role_title=", ".join(role.title for role in roles),
    )
    return {"status": "approved", **delivery}


@router.post("/{application_id}/annul")
async def annul_application(
    application_id: int,
    admin: AdminUser = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
) -> dict[str, bool | str | None]:
    application = await get_application_with_user(session, application_id)
    if application is None:
        raise HTTPException(status_code=404, detail="Заявка не найдена")
    if application.status != "approved":
        raise HTTPException(
            status_code=409,
            detail="Аннулировать можно только одобренную заявку",
        )

    application.status = "annulled"
    application.user.can_reapply = True
    await set_user_roles(session, application.user_id, [])
    session.add(
        AuditLog(
            admin_id=admin.id,
            action="annul_application",
            entity_type="application",
            entity_id=application.id,
            payload_json={
                "user_id": application.user_id,
                "telegram_id": application.user.telegram_id,
            },
        )
    )
    await session.commit()

    notification_sent = False
    warning: str | None = None
    bot = Bot(settings.bot_token)
    try:
        try:
            await bot.send_message(
                application.user.telegram_id,
                await render_bot_text("application_annulled"),
                parse_mode="HTML",
            )
            notification_sent = True
        except TelegramAPIError:
            warning = "Заявка аннулирована, но бот не смог уведомить пользователя."
    finally:
        await bot.session.close()

    return {
        "status": "annulled",
        "notification_sent": notification_sent,
        "warning": warning,
    }


@router.post("/{application_id}/reject")
async def reject_application(
    application_id: int,
    payload: ReviewPayload,
    admin: AdminUser = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
) -> dict[str, bool | str | None]:
    application = await get_application_with_user(session, application_id)
    if application is None:
        raise HTTPException(status_code=404, detail="Заявка не найдена")
    if application.status != "pending":
        raise HTTPException(status_code=409, detail="Заявка уже обработана")

    application.status = "rejected"
    application.admin_comment = payload.comment
    application.reviewed_by_admin_id = admin.id
    application.reviewed_at = datetime.now(timezone.utc)
    session.add(AuditLog(admin_id=admin.id, action="reject", entity_type="application", entity_id=application.id))
    await session.commit()
    delivery = await notify_application_decision(application)
    return {"status": "rejected", **delivery}


@router.post("/{application_id}/ban")
async def ban_application_user(
    application_id: int,
    payload: ReviewPayload,
    admin: AdminUser = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
) -> dict[str, bool | str | None]:
    application = await get_application_with_user(session, application_id)
    if application is None:
        raise HTTPException(status_code=404, detail="Заявка не найдена")
    if application.user.is_banned:
        raise HTTPException(status_code=409, detail="Пользователь уже заблокирован")

    target_admin_result = await session.execute(
        select(AdminUser.id).where(
            AdminUser.telegram_id == application.user.telegram_id,
            AdminUser.is_active.is_(True),
        )
    )
    if target_admin_result.scalar_one_or_none() is not None:
        raise HTTPException(status_code=409, detail="Нельзя заблокировать администратора")

    now = datetime.now(timezone.utc)
    application.user.is_banned = True
    application.user.banned_at = now
    application.status = "banned"
    application.admin_comment = payload.comment
    application.reviewed_by_admin_id = admin.id
    application.reviewed_at = now
    await session.execute(
        update(Application)
        .where(
            Application.user_id == application.user_id,
            Application.status == "pending",
        )
        .values(
            status="banned",
            admin_comment=payload.comment,
            reviewed_by_admin_id=admin.id,
            reviewed_at=now,
        )
    )
    await session.execute(delete(UserRole).where(UserRole.user_id == application.user_id))
    await session.execute(delete(TopicWhitelist).where(TopicWhitelist.user_id == application.user_id))
    session.add(
        AuditLog(
            admin_id=admin.id,
            action="ban_user",
            entity_type="user",
            entity_id=application.user_id,
            payload_json={"application_id": application.id, "comment": payload.comment},
        )
    )
    await session.commit()

    notification_sent = False
    group_ban_applied = False
    warning: str | None = None
    bot = Bot(settings.bot_token)
    try:
        text = await render_bot_text("user_banned")
        if payload.comment:
            text += "\n\n" + await render_bot_text(
                "admin_comment",
                comment=escape(payload.comment),
            )
        try:
            await bot.send_message(application.user.telegram_id, text, parse_mode="HTML")
            notification_sent = True
        except TelegramAPIError:
            warning = "Бот не смог отправить пользователю уведомление."

        if settings.telegram_group_id:
            try:
                await bot.ban_chat_member(settings.telegram_group_id, application.user.telegram_id)
                group_ban_applied = True
            except TelegramAPIError:
                group_warning = "Бот не смог заблокировать пользователя в группе."
                warning = f"{warning} {group_warning}" if warning else group_warning
    finally:
        await bot.session.close()

    return {
        "status": "banned",
        "notification_sent": notification_sent,
        "group_ban_applied": group_ban_applied,
        "warning": warning,
    }


@router.post("/{application_id}/notify")
async def resend_application_notification(
    application_id: int,
    admin: AdminUser = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
) -> dict[str, bool | str | None]:
    application = await get_application_with_user(session, application_id)
    if application is None:
        raise HTTPException(status_code=404, detail="Заявка не найдена")
    if application.status not in {"approved", "rejected"}:
        raise HTTPException(status_code=409, detail="По заявке еще нет решения")

    roles_map = await get_user_roles_map(session, [application.user_id])
    assigned_roles = roles_map.get(application.user_id, [])
    role_title = ", ".join(role["title"] for role in assigned_roles) or None
    delivery = await notify_application_decision(application, role_title=role_title)
    session.add(
        AuditLog(
            admin_id=admin.id,
            action="resend_notification",
            entity_type="application",
            entity_id=application.id,
            payload_json=delivery,
        )
    )
    await session.commit()
    return {"status": application.status, **delivery}


async def get_application_with_user(
    session: AsyncSession,
    application_id: int,
) -> Application | None:
    result = await session.execute(
        select(Application)
        .options(selectinload(Application.user))
        .where(Application.id == application_id)
    )
    return result.scalar_one_or_none()
