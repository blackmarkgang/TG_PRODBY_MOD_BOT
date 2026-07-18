from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models import AdminUser, ApplicationQuestion, CommunityRole


DEFAULT_COMMUNITY_ROLES = [
    ("artist", "Артист"),
    ("producer", "Продюсер"),
    ("beatmaker", "Битмейкер"),
    ("listener", "Слушатель"),
    ("sound_engineer", "Звукоинженер"),
    ("designer", "Дизайнер"),
    ("editor", "Монтажер"),
    ("operator", "Оператор"),
    ("organizer", "Организатор"),
    ("other", "Другое"),
]

DEFAULT_QUESTIONS = [
    ("age", "Сколько вам лет?", "Отправьте возраст одним числом.", "number"),
    (
        "role_details",
        "Расскажите о себе",
        "Чем вы занимаетесь в музыке или смежных направлениях? Чем полезны сообществу?",
        "text",
    ),
    ("motivation", "Почему вы хотите попасть в Prod.by?", "Напишите коротко и своими словами.", "text"),
    (
        "expectations",
        "Что вы ожидаете от участия?",
        "Расскажите, что хотите получить от сообщества и чем готовы делиться.",
        "text",
    ),
    (
        "portfolio",
        "Добавьте примеры работ",
        None,
        "file",
    ),
]


async def seed_defaults(session: AsyncSession) -> None:
    for index, telegram_id in enumerate(settings.admin_ids):
        result = await session.execute(select(AdminUser).where(AdminUser.telegram_id == telegram_id))
        if result.scalar_one_or_none() is None:
            session.add(AdminUser(telegram_id=telegram_id, role="owner" if index == 0 else "admin"))

    roles_result = await session.execute(select(CommunityRole.id).limit(1))
    if roles_result.scalar_one_or_none() is None:
        for code, title in DEFAULT_COMMUNITY_ROLES:
            session.add(CommunityRole(code=code, title=title))

    questions_result = await session.execute(select(ApplicationQuestion.id).limit(1))
    if questions_result.scalar_one_or_none() is None:
        for index, (code, text, help_text, answer_type) in enumerate(DEFAULT_QUESTIONS, start=1):
            session.add(
                ApplicationQuestion(
                    code=code,
                    text=text,
                    help_text=help_text,
                    answer_type=answer_type,
                    sort_order=index,
                )
            )

    await session.commit()
