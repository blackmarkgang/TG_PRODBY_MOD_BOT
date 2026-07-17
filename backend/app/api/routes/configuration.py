from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_admin, get_current_full_admin
from app.db.models import (
    AdminUser,
    ApplicationQuestion,
    AuditLog,
    CommunityRole,
    TopicRolePermission,
    UserRole,
)
from app.db.session import get_session

router = APIRouter()


class RolePayload(BaseModel):
    title: str = Field(min_length=1, max_length=128)

    @field_validator("title")
    @classmethod
    def clean_title(cls, value: str) -> str:
        title = value.strip()
        if not title:
            raise ValueError("Название роли не может быть пустым")
        return title


END_QUESTION_CODE = "__end__"


class QuestionOptionPayload(BaseModel):
    id: str | None = Field(default=None, max_length=32)
    label: str = Field(min_length=1, max_length=64)
    next_question_code: str | None = Field(default=None, max_length=64)

    @field_validator("label")
    @classmethod
    def clean_label(cls, value: str) -> str:
        label = value.strip()
        if not label:
            raise ValueError("Вариант ответа не может быть пустым")
        return label

    @field_validator("id")
    @classmethod
    def validate_id(cls, value: str | None) -> str | None:
        if value is not None and (
            not value
            or not all(character.isascii() and (character.isalnum() or character in "_-") for character in value)
        ):
            raise ValueError("ID варианта содержит недопустимые символы")
        return value

    @field_validator("next_question_code")
    @classmethod
    def clean_option_next_question_code(cls, value: str | None) -> str | None:
        return (value.strip() or None) if value is not None else None


class QuestionPayload(BaseModel):
    text: str = Field(min_length=1, max_length=512)
    help_text: str | None = Field(default=None, max_length=2_000)
    answer_type: str = "text"
    options: list[QuestionOptionPayload] = Field(default_factory=list, max_length=20)
    next_question_code: str | None = Field(default=None, max_length=64)

    @field_validator("text")
    @classmethod
    def clean_text(cls, value: str) -> str:
        text = value.strip()
        if not text:
            raise ValueError("Текст вопроса не может быть пустым")
        return text

    @field_validator("help_text")
    @classmethod
    def clean_help_text(cls, value: str | None) -> str | None:
        return (value.strip() or None) if value is not None else None

    @field_validator("answer_type")
    @classmethod
    def validate_answer_type(cls, value: str) -> str:
        if value not in {"text", "number", "single_choice"}:
            raise ValueError("Поддерживаются типы text, number и single_choice")
        return value

    @field_validator("next_question_code")
    @classmethod
    def clean_next_question_code(cls, value: str | None) -> str | None:
        return (value.strip() or None) if value is not None else None


class QuestionOrderPayload(BaseModel):
    question_ids: list[int]


@router.get("/roles")
async def list_roles(
    _: AdminUser = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    result = await session.execute(select(CommunityRole).order_by(CommunityRole.title))
    return [{"id": role.id, "code": role.code, "title": role.title} for role in result.scalars().all()]


@router.post("/roles", status_code=201)
async def create_role(
    payload: RolePayload,
    admin: AdminUser = Depends(get_current_full_admin),
    session: AsyncSession = Depends(get_session),
) -> dict:
    role = CommunityRole(code=f"custom_{uuid4().hex[:10]}", title=payload.title)
    session.add(role)
    await session.flush()
    session.add(
        AuditLog(
            admin_id=admin.id,
            action="create_role",
            entity_type="community_role",
            entity_id=role.id,
            payload_json={"title": role.title, "code": role.code},
        )
    )
    await session.commit()
    return {"id": role.id, "code": role.code, "title": role.title}


@router.patch("/roles/{role_id}")
async def update_role(
    role_id: int,
    payload: RolePayload,
    admin: AdminUser = Depends(get_current_full_admin),
    session: AsyncSession = Depends(get_session),
) -> dict:
    role = await session.get(CommunityRole, role_id)
    if role is None:
        raise HTTPException(status_code=404, detail="Роль не найдена")
    role.title = payload.title
    session.add(
        AuditLog(
            admin_id=admin.id,
            action="update_role",
            entity_type="community_role",
            entity_id=role.id,
            payload_json={"title": role.title, "code": role.code},
        )
    )
    await session.commit()
    return {"id": role.id, "code": role.code, "title": role.title}


@router.delete("/roles/{role_id}", status_code=204)
async def delete_role(
    role_id: int,
    admin: AdminUser = Depends(get_current_full_admin),
    session: AsyncSession = Depends(get_session),
) -> Response:
    role = await session.get(CommunityRole, role_id)
    if role is None:
        raise HTTPException(status_code=404, detail="Роль не найдена")
    count = await session.scalar(select(func.count()).select_from(CommunityRole))
    if count is not None and count <= 1:
        raise HTTPException(status_code=409, detail="Нельзя удалить последнюю роль")

    await session.execute(delete(UserRole).where(UserRole.role_id == role.id))
    await session.execute(
        delete(TopicRolePermission).where(TopicRolePermission.role_id == role.id)
    )
    session.add(
        AuditLog(
            admin_id=admin.id,
            action="delete_role",
            entity_type="community_role",
            entity_id=role.id,
            payload_json={"title": role.title, "code": role.code},
        )
    )
    await session.delete(role)
    await session.commit()
    return Response(status_code=204)


@router.get("/questions")
async def list_questions(
    _: AdminUser = Depends(get_current_full_admin),
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    result = await session.execute(
        select(ApplicationQuestion).order_by(ApplicationQuestion.sort_order)
    )
    return [serialize_question(question) for question in result.scalars().all()]


@router.post("/questions", status_code=201)
async def create_question(
    payload: QuestionPayload,
    admin: AdminUser = Depends(get_current_full_admin),
    session: AsyncSession = Depends(get_session),
) -> dict:
    max_order = await session.scalar(select(func.max(ApplicationQuestion.sort_order))) or 0
    options = normalize_question_options(payload.options)
    if payload.answer_type == "single_choice" and not options:
        options = [
            {"id": uuid4().hex[:10], "label": "Вариант 1", "next_question_code": None},
            {"id": uuid4().hex[:10], "label": "Вариант 2", "next_question_code": None},
        ]
    question = ApplicationQuestion(
        code=f"custom_{uuid4().hex[:10]}",
        text=payload.text,
        help_text=payload.help_text,
        answer_type=payload.answer_type,
        options_json=options if payload.answer_type == "single_choice" else [],
        next_question_code=payload.next_question_code,
        sort_order=max_order + 1,
    )
    session.add(question)
    await session.flush()
    await validate_question_graph(session)
    session.add(
        AuditLog(
            admin_id=admin.id,
            action="create_question",
            entity_type="application_question",
            entity_id=question.id,
            payload_json=serialize_question(question),
        )
    )
    await session.commit()
    return serialize_question(question)


@router.patch("/questions/{question_id}")
async def update_question(
    question_id: int,
    payload: QuestionPayload,
    admin: AdminUser = Depends(get_current_full_admin),
    session: AsyncSession = Depends(get_session),
) -> dict:
    question = await session.get(ApplicationQuestion, question_id)
    if question is None:
        raise HTTPException(status_code=404, detail="Вопрос не найден")
    question.text = payload.text
    question.help_text = payload.help_text
    question.answer_type = payload.answer_type
    question.options_json = (
        normalize_question_options(payload.options)
        if payload.answer_type == "single_choice"
        else []
    )
    question.next_question_code = payload.next_question_code
    await session.flush()
    await validate_question_graph(session)
    session.add(
        AuditLog(
            admin_id=admin.id,
            action="update_question",
            entity_type="application_question",
            entity_id=question.id,
            payload_json=serialize_question(question),
        )
    )
    await session.commit()
    return serialize_question(question)


@router.put("/questions/order")
async def update_question_order(
    payload: QuestionOrderPayload,
    admin: AdminUser = Depends(get_current_full_admin),
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    result = await session.execute(select(ApplicationQuestion))
    questions = list(result.scalars().all())
    if set(payload.question_ids) != {question.id for question in questions}:
        raise HTTPException(status_code=400, detail="Передан неполный список вопросов")
    positions = {question_id: index for index, question_id in enumerate(payload.question_ids, start=1)}
    for question in questions:
        question.sort_order = positions[question.id]
    await session.flush()
    await validate_question_graph(session)
    session.add(
        AuditLog(
            admin_id=admin.id,
            action="reorder_questions",
            entity_type="application_question",
            payload_json={"question_ids": payload.question_ids},
        )
    )
    await session.commit()
    return await list_questions(admin, session)


@router.delete("/questions/{question_id}", status_code=204)
async def delete_question(
    question_id: int,
    admin: AdminUser = Depends(get_current_full_admin),
    session: AsyncSession = Depends(get_session),
) -> Response:
    question = await session.get(ApplicationQuestion, question_id)
    if question is None:
        raise HTTPException(status_code=404, detail="Вопрос не найден")
    count = await session.scalar(select(func.count()).select_from(ApplicationQuestion))
    if count is not None and count <= 1:
        raise HTTPException(status_code=409, detail="В анкете должен остаться хотя бы один вопрос")
    result = await session.execute(select(ApplicationQuestion))
    for other_question in result.scalars().all():
        if other_question.id == question.id:
            continue
        if other_question.next_question_code == question.code:
            other_question.next_question_code = None
        other_question.options_json = [
            {
                **option,
                "next_question_code": None
                if option.get("next_question_code") == question.code
                else option.get("next_question_code"),
            }
            for option in (other_question.options_json or [])
        ]
    session.add(
        AuditLog(
            admin_id=admin.id,
            action="delete_question",
            entity_type="application_question",
            entity_id=question.id,
            payload_json=serialize_question(question),
        )
    )
    await session.delete(question)
    await session.commit()
    return Response(status_code=204)


def serialize_question(question: ApplicationQuestion) -> dict:
    return {
        "id": question.id,
        "code": question.code,
        "text": question.text,
        "help_text": question.help_text,
        "answer_type": question.answer_type,
        "options": question.options_json or [],
        "next_question_code": question.next_question_code,
        "sort_order": question.sort_order,
    }


def normalize_question_options(options: list[QuestionOptionPayload]) -> list[dict]:
    normalized = [
        {
            "id": option.id or uuid4().hex[:10],
            "label": option.label,
            "next_question_code": option.next_question_code,
        }
        for option in options
    ]
    ids = [option["id"] for option in normalized]
    labels = [option["label"].casefold() for option in normalized]
    if len(ids) != len(set(ids)):
        raise HTTPException(status_code=422, detail="ID вариантов ответа должны быть уникальными")
    if len(labels) != len(set(labels)):
        raise HTTPException(status_code=422, detail="Варианты ответа не должны повторяться")
    return normalized


async def validate_question_graph(session: AsyncSession) -> None:
    result = await session.execute(
        select(ApplicationQuestion).order_by(ApplicationQuestion.sort_order)
    )
    questions = list(result.scalars().all())
    validate_question_graph_data(questions)


def validate_question_graph_data(questions: list[ApplicationQuestion]) -> None:
    codes = {question.code for question in questions}
    edges: dict[str, set[str]] = {question.code: set() for question in questions}

    for index, question in enumerate(questions):
        targets: list[str | None]
        if question.answer_type == "single_choice":
            if not question.options_json:
                raise HTTPException(
                    status_code=422,
                    detail=f"Добавьте варианты ответа для вопроса «{question.text}»",
                )
            targets = [
                option.get("next_question_code") or question.next_question_code
                for option in question.options_json
            ]
        else:
            targets = [question.next_question_code]
        for target in targets:
            if target is None:
                if index + 1 < len(questions):
                    edges[question.code].add(questions[index + 1].code)
                continue
            if target == END_QUESTION_CODE:
                continue
            if target not in codes:
                raise HTTPException(status_code=422, detail=f"Следующий вопрос «{target}» не найден")
            edges[question.code].add(target)

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(code: str) -> None:
        if code in visiting:
            raise HTTPException(status_code=422, detail="Ветвление содержит цикл")
        if code in visited:
            return
        visiting.add(code)
        for target in edges[code]:
            visit(target)
        visiting.remove(code)
        visited.add(code)

    for code in edges:
        visit(code)
