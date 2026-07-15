from aiogram.types import User as TelegramUser
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Application, ApplicationFile, AuditLog, User
from app.services.community_access import get_active_application


class UserBannedError(ValueError):
    pass


MAX_APPLICATION_FILE_SIZE = 10 * 1024 * 1024


class AttachmentTooLargeError(ValueError):
    pass


class ActiveApplicationError(ValueError):
    def __init__(self, application: Application):
        self.application = application
        super().__init__(f"У пользователя уже есть активная заявка №{application.id}")


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
    if any(
        file_data.get("file_size") is not None
        and file_data["file_size"] > MAX_APPLICATION_FILE_SIZE
        for file_data in files
    ):
        raise AttachmentTooLargeError("Размер одного файла не должен превышать 10 МБ")

    user = await get_or_create_user(session, tg_user)
    if user.is_banned:
        raise UserBannedError("Доступ к подаче заявок заблокирован")
    await session.execute(select(User.id).where(User.id == user.id).with_for_update())
    active_application = await get_active_application(session, user.telegram_id)
    if active_application is not None:
        raise ActiveApplicationError(active_application)
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
                "first_name": user.first_name,
                "last_name": user.last_name,
            },
        )
    )
    await session.commit()
    await session.refresh(application)
    return application
