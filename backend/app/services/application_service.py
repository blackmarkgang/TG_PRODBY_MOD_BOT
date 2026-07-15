from aiogram.types import User as TelegramUser
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Application, ApplicationFile, AuditLog, User


class UserBannedError(ValueError):
    pass


async def is_user_banned(session: AsyncSession, telegram_id: int) -> bool:
    result = await session.execute(select(User.is_banned).where(User.telegram_id == telegram_id))
    return bool(result.scalar_one_or_none())


async def get_or_create_user(session: AsyncSession, tg_user: TelegramUser) -> User:
    result = await session.execute(select(User).where(User.telegram_id == tg_user.id))
    user = result.scalar_one_or_none()
    if user is not None:
        user.username = tg_user.username
        user.first_name = tg_user.first_name
        user.last_name = tg_user.last_name
        return user

    user = User(
        telegram_id=tg_user.id,
        username=tg_user.username,
        first_name=tg_user.first_name,
        last_name=tg_user.last_name,
    )
    session.add(user)
    await session.flush()
    return user


async def create_pending_application(
    session: AsyncSession,
    tg_user: TelegramUser,
    age: int,
    music_role: str | None,
    answers: dict,
    answer_labels: dict,
    files: list[dict],
) -> Application:
    user = await get_or_create_user(session, tg_user)
    if user.is_banned:
        raise UserBannedError("Доступ к подаче заявок заблокирован")
    application = Application(
        user_id=user.id,
        status="pending",
        age=age,
        music_role=music_role,
        answers_json=answers,
        answer_labels_json=answer_labels,
    )
    session.add(application)
    await session.flush()
    for file_data in files:
        session.add(ApplicationFile(application_id=application.id, **file_data))
    session.add(
        AuditLog(
            action="application_submitted",
            entity_type="application",
            entity_id=application.id,
            payload_json={
                "user_id": user.id,
                "telegram_id": user.telegram_id,
                "username": user.username,
            },
        )
    )
    await session.commit()
    await session.refresh(application)
    return application
