import asyncio
import logging
from datetime import datetime, timezone

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError, TelegramRetryAfter
from aiogram.types import LinkPreviewOptions
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    Broadcast,
    BroadcastRecipient,
    CommunityRole,
    User,
    UserRole,
)
from app.db.session import SessionLocal


logger = logging.getLogger(__name__)
BROADCAST_AUDIENCES = {"all", "members", "non_members"}
BROADCAST_SEND_INTERVAL_SECONDS = 0.05


async def get_broadcast_recipients(
    session: AsyncSession,
    audience: str,
    role_codes: list[str],
) -> list[User]:
    if audience not in BROADCAST_AUDIENCES:
        raise ValueError("Неизвестная аудитория рассылки")

    unique_role_codes = list(dict.fromkeys(role_codes))
    if unique_role_codes:
        roles_result = await session.execute(
            select(CommunityRole.code).where(
                CommunityRole.code.in_(unique_role_codes)
            )
        )
        found_codes = set(roles_result.scalars().all())
        missing_codes = sorted(set(unique_role_codes) - found_codes)
        if missing_codes:
            raise ValueError(f"Неизвестные роли: {', '.join(missing_codes)}")

    query = select(User).where(
        User.has_used_bot.is_(True),
        User.is_banned.is_(False),
    )
    if audience == "members":
        query = query.where(User.is_group_member.is_(True))
    elif audience == "non_members":
        query = query.where(User.is_group_member.is_(False))

    if unique_role_codes:
        query = (
            query.join(UserRole, UserRole.user_id == User.id)
            .join(CommunityRole, CommunityRole.id == UserRole.role_id)
            .where(CommunityRole.code.in_(unique_role_codes))
            .distinct()
        )

    result = await session.execute(query.order_by(User.id))
    return list(result.scalars().all())


async def run_broadcast_worker(bot: Bot) -> None:
    await recover_interrupted_broadcasts()
    while True:
        broadcast_id: int | None = None
        try:
            broadcast_id = await claim_due_broadcast()
            if broadcast_id is None:
                await asyncio.sleep(2)
                continue
            await deliver_broadcast(bot, broadcast_id)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Broadcast worker iteration failed")
            if broadcast_id is not None:
                try:
                    await reschedule_interrupted_broadcast(broadcast_id)
                except Exception:
                    logger.exception(
                        "Failed to reschedule broadcast %s",
                        broadcast_id,
                    )
            await asyncio.sleep(5)


async def recover_interrupted_broadcasts() -> None:
    async with SessionLocal() as session:
        await session.execute(
            update(Broadcast)
            .where(Broadcast.status == "processing")
            .values(status="scheduled", started_at=None)
        )
        await session.commit()


async def claim_due_broadcast() -> int | None:
    async with SessionLocal() as session:
        result = await session.execute(
            select(Broadcast)
            .where(
                Broadcast.status == "scheduled",
                Broadcast.scheduled_at <= datetime.now(timezone.utc),
            )
            .order_by(Broadcast.scheduled_at, Broadcast.id)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        broadcast = result.scalar_one_or_none()
        if broadcast is None:
            return None
        broadcast.status = "processing"
        broadcast.started_at = datetime.now(timezone.utc)
        await session.commit()
        return broadcast.id


async def reschedule_interrupted_broadcast(broadcast_id: int) -> None:
    async with SessionLocal() as session:
        await session.execute(
            update(Broadcast)
            .where(
                Broadcast.id == broadcast_id,
                Broadcast.status == "processing",
            )
            .values(status="scheduled", started_at=None)
        )
        await session.commit()


async def deliver_broadcast(bot: Bot, broadcast_id: int) -> None:
    async with SessionLocal() as session:
        broadcast = await session.get(Broadcast, broadcast_id)
        if broadcast is None or broadcast.status != "processing":
            return

        while True:
            recipients_result = await session.execute(
                select(BroadcastRecipient)
                .where(
                    BroadcastRecipient.broadcast_id == broadcast.id,
                    BroadcastRecipient.status == "pending",
                )
                .order_by(BroadcastRecipient.id)
                .limit(100)
            )
            recipients = list(recipients_result.scalars().all())
            if not recipients:
                break

            for recipient in recipients:
                try:
                    await send_broadcast_message(bot, broadcast, recipient.telegram_id)
                except TelegramAPIError as exc:
                    recipient.status = "failed"
                    recipient.error = str(exc)[:1000]
                    broadcast.failed_count += 1
                except Exception as exc:
                    logger.exception(
                        "Unexpected broadcast delivery failure for user %s",
                        recipient.telegram_id,
                    )
                    recipient.status = "failed"
                    recipient.error = str(exc)[:1000]
                    broadcast.failed_count += 1
                else:
                    recipient.status = "sent"
                    recipient.sent_at = datetime.now(timezone.utc)
                    broadcast.sent_count += 1
                await session.commit()
                await asyncio.sleep(BROADCAST_SEND_INTERVAL_SECONDS)

        broadcast.status = "completed"
        broadcast.completed_at = datetime.now(timezone.utc)
        await session.commit()


async def send_broadcast_message(
    bot: Bot,
    broadcast: Broadcast,
    telegram_id: int,
) -> None:
    try:
        await bot.send_message(
            telegram_id,
            broadcast.message,
            link_preview_options=LinkPreviewOptions(
                is_disabled=broadcast.disable_link_preview
            ),
        )
    except TelegramRetryAfter as exc:
        await asyncio.sleep(exc.retry_after)
        await bot.send_message(
            telegram_id,
            broadcast.message,
            link_preview_options=LinkPreviewOptions(
                is_disabled=broadcast.disable_link_preview
            ),
        )
