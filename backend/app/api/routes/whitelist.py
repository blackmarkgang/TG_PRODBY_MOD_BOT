from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_full_admin
from app.db.models import AdminUser, ForumTopic
from app.db.session import get_session

router = APIRouter()


@router.get("/topics")
async def list_topics(
    _: AdminUser = Depends(get_current_full_admin),
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    result = await session.execute(select(ForumTopic).order_by(ForumTopic.title))
    return [
        {
            "id": topic.id,
            "chat_id": topic.chat_id,
            "message_thread_id": topic.message_thread_id,
            "title": topic.title,
            "is_protected": topic.is_protected,
        }
        for topic in result.scalars().all()
    ]
