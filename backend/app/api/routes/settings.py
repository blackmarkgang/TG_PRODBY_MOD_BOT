from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_admin
from app.core.config import settings
from app.db.models import AdminUser, AuditLog, CommunityRole, ForumTopic, TopicRolePermission
from app.db.session import get_session

router = APIRouter()


class TopicTitlePayload(BaseModel):
    title: str = Field(min_length=1, max_length=128)

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str) -> str:
        title = value.strip()
        if not title:
            raise ValueError("Название темы не может быть пустым")
        return title


class TopicCreatePayload(TopicTitlePayload):
    message_thread_id: int = Field(gt=0)


class TopicUpdatePayload(TopicTitlePayload):
    pass


class TopicRolesPayload(BaseModel):
    role_codes: list[str]


async def serialize_topics(session: AsyncSession) -> list[dict]:
    topics_result = await session.execute(select(ForumTopic).order_by(ForumTopic.title))
    topics = list(topics_result.scalars().all())
    permissions_result = await session.execute(
        select(TopicRolePermission.topic_id, CommunityRole.code, CommunityRole.title)
        .join(CommunityRole, CommunityRole.id == TopicRolePermission.role_id)
        .order_by(CommunityRole.title)
    )
    roles_by_topic: dict[int, list[dict[str, str]]] = {}
    for topic_id, code, title in permissions_result.all():
        roles_by_topic.setdefault(topic_id, []).append({"code": code, "title": title})

    return [
        {
            "id": topic.id,
            "chat_id": topic.chat_id,
            "message_thread_id": topic.message_thread_id,
            "title": topic.title,
            "is_protected": bool(roles_by_topic.get(topic.id)),
            "allowed_roles": roles_by_topic.get(topic.id, []),
        }
        for topic in topics
    ]


@router.get("/topics")
async def list_topics(
    _: AdminUser = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    return await serialize_topics(session)


@router.post("/topics", status_code=201)
async def create_topic(
    payload: TopicCreatePayload,
    admin: AdminUser = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
) -> dict:
    if not settings.telegram_group_id:
        raise HTTPException(status_code=409, detail="TELEGRAM_GROUP_ID не настроен")

    chat_id = int(settings.telegram_group_id)
    existing_result = await session.execute(
        select(ForumTopic).where(
            ForumTopic.chat_id == chat_id,
            ForumTopic.message_thread_id == payload.message_thread_id,
        )
    )
    topic = existing_result.scalar_one_or_none()
    if topic is None:
        topic = ForumTopic(
            chat_id=chat_id,
            message_thread_id=payload.message_thread_id,
            title=payload.title,
            is_protected=False,
        )
        session.add(topic)
        await session.flush()
        action = "create_topic"
    else:
        topic.title = payload.title
        action = "update_topic"

    session.add(
        AuditLog(
            admin_id=admin.id,
            action=action,
            entity_type="forum_topic",
            entity_id=topic.id,
            payload_json={"message_thread_id": payload.message_thread_id, "title": topic.title},
        )
    )
    await session.commit()
    topics = await serialize_topics(session)
    return next(item for item in topics if item["id"] == topic.id)


@router.patch("/topics/{topic_id}")
async def update_topic(
    topic_id: int,
    payload: TopicUpdatePayload,
    admin: AdminUser = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
) -> dict:
    topic = await session.get(ForumTopic, topic_id)
    if topic is None:
        raise HTTPException(status_code=404, detail="Тема не найдена")
    topic.title = payload.title
    session.add(
        AuditLog(
            admin_id=admin.id,
            action="rename_topic",
            entity_type="forum_topic",
            entity_id=topic.id,
            payload_json={"title": topic.title},
        )
    )
    await session.commit()
    topics = await serialize_topics(session)
    return next(item for item in topics if item["id"] == topic.id)


@router.put("/topics/{topic_id}/roles")
async def update_topic_roles(
    topic_id: int,
    payload: TopicRolesPayload,
    admin: AdminUser = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
) -> dict:
    topic = await session.get(ForumTopic, topic_id)
    if topic is None:
        raise HTTPException(status_code=404, detail="Тема не найдена")

    role_codes = list(dict.fromkeys(payload.role_codes))
    roles_result = await session.execute(select(CommunityRole).where(CommunityRole.code.in_(role_codes)))
    roles = list(roles_result.scalars().all())
    if len(roles) != len(role_codes):
        found_codes = {role.code for role in roles}
        unknown_codes = sorted(set(role_codes) - found_codes)
        raise HTTPException(status_code=400, detail=f"Неизвестные роли: {', '.join(unknown_codes)}")

    await session.execute(delete(TopicRolePermission).where(TopicRolePermission.topic_id == topic.id))
    for role in roles:
        session.add(TopicRolePermission(topic_id=topic.id, role_id=role.id))
    topic.is_protected = bool(roles)
    session.add(
        AuditLog(
            admin_id=admin.id,
            action="set_topic_roles",
            entity_type="forum_topic",
            entity_id=topic.id,
            payload_json={"role_codes": role_codes},
        )
    )
    await session.commit()
    topics = await serialize_topics(session)
    return next(item for item in topics if item["id"] == topic.id)
