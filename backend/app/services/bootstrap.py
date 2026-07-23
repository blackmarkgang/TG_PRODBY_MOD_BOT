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
    ("creative_production", "Креативный продакшн"),
    ("other", "Другое"),
]

DEFAULT_DIRECTION_OPTIONS = [
    {"id": "listener", "label": "Слушатель", "next_question_code": "motivation"},
    {"id": "artist", "label": "Артист", "next_question_code": "expectations"},
    {"id": "beatmaker", "label": "Битмейкер", "next_question_code": "expectations"},
    {
        "id": "creative_prod",
        "label": "Креативный продакшн (видео, дизайн, монтаж)",
        "next_question_code": "expectations",
    },
]

DEFAULT_QUESTIONS = [
    ("age", "Сколько вам лет?", "Отправьте возраст одним числом.", "number", None, []),
    (
        "role_details",
        "Расскажите о себе",
        "Выберите основное направление.",
        "single_choice",
        None,
        DEFAULT_DIRECTION_OPTIONS,
    ),
    (
        "motivation",
        "Почему вы хотите попасть в Prod.by?",
        "Напишите коротко и своими словами.",
        "text",
        "__end__",
        [],
    ),
    (
        "expectations",
        "Что вы ожидаете от участия?",
        "Расскажите, что хотите получить от сообщества и чем готовы делиться.",
        "text",
        None,
        [],
    ),
    (
        "portfolio",
        "Добавьте примеры работ",
        None,
        "file",
        None,
        [],
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
        for index, (code, text, help_text, answer_type, next_code, options) in enumerate(
            DEFAULT_QUESTIONS,
            start=1,
        ):
            session.add(
                ApplicationQuestion(
                    code=code,
                    text=text,
                    help_text=help_text,
                    answer_type=answer_type,
                    options_json=options,
                    next_question_code=next_code,
                    sort_order=index,
                )
            )

    await session.commit()
