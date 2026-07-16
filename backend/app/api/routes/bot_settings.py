from io import BytesIO

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from aiogram.types import BufferedInputFile, InputProfilePhotoStatic
from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_full_admin
from app.core.config import settings
from app.db.models import AdminUser, AuditLog, BotTextSetting
from app.db.session import get_session
from app.services.bot_text_service import (
    BOT_TEXTS,
    BOT_TEXTS_BY_KEY,
    get_bot_text_overrides,
    validate_bot_text,
)

router = APIRouter()
MAX_AVATAR_SIZE = 5 * 1024 * 1024


class BotProfilePayload(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    short_description: str = Field(max_length=120)
    description: str = Field(max_length=512)


class BotTextPayload(BaseModel):
    text: str = Field(min_length=1, max_length=4096)


@router.get("")
async def get_bot_settings(
    _: AdminUser = Depends(get_current_full_admin),
    session: AsyncSession = Depends(get_session),
) -> dict:
    profile = await load_telegram_profile()
    overrides = await get_bot_text_overrides(session)
    return {
        "profile": profile,
        "messages": [serialize_text_setting(item, overrides.get(item.key)) for item in BOT_TEXTS],
    }


@router.put("/profile")
async def update_bot_profile(
    payload: BotProfilePayload,
    admin: AdminUser = Depends(get_current_full_admin),
    session: AsyncSession = Depends(get_session),
) -> dict:
    bot = Bot(settings.bot_token)
    try:
        await bot.set_my_name(name=payload.name)
        await bot.set_my_short_description(short_description=payload.short_description)
        await bot.set_my_description(description=payload.description)
    except TelegramAPIError as exc:
        raise HTTPException(status_code=502, detail="Telegram не применил настройки профиля") from exc
    finally:
        await bot.session.close()

    session.add(
        AuditLog(
            admin_id=admin.id,
            action="update_bot_profile",
            entity_type="bot",
            payload_json={"name": payload.name},
        )
    )
    await session.commit()
    return await load_telegram_profile()


@router.get("/avatar")
async def get_bot_avatar(
    _: AdminUser = Depends(get_current_full_admin),
) -> Response:
    bot = Bot(settings.bot_token)
    try:
        me = await bot.get_me()
        photos = await bot.get_user_profile_photos(user_id=me.id, limit=1)
        if not photos.photos:
            raise HTTPException(status_code=404, detail="У бота нет аватара")
        photo = photos.photos[0][-1]
        telegram_file = await bot.get_file(photo.file_id)
        if not telegram_file.file_path:
            raise HTTPException(status_code=502, detail="Telegram не вернул файл аватара")
        destination = BytesIO()
        await bot.download_file(telegram_file.file_path, destination=destination)
        return Response(content=destination.getvalue(), media_type="image/jpeg")
    except TelegramAPIError as exc:
        raise HTTPException(status_code=502, detail="Не удалось загрузить аватар из Telegram") from exc
    finally:
        await bot.session.close()


@router.put("/avatar")
async def update_bot_avatar(
    avatar: UploadFile = File(...),
    admin: AdminUser = Depends(get_current_full_admin),
    session: AsyncSession = Depends(get_session),
) -> dict[str, bool]:
    content = await avatar.read(MAX_AVATAR_SIZE + 1)
    if len(content) > MAX_AVATAR_SIZE:
        raise HTTPException(status_code=413, detail="Аватар не должен превышать 5 МБ")
    if len(content) < 3 or not content.startswith(b"\xff\xd8\xff"):
        raise HTTPException(status_code=422, detail="Telegram принимает статичный аватар только в формате JPG")

    bot = Bot(settings.bot_token)
    try:
        photo = InputProfilePhotoStatic(
            photo=BufferedInputFile(content, filename=avatar.filename or "avatar.jpg")
        )
        await bot.set_my_profile_photo(photo=photo)
    except TelegramAPIError as exc:
        raise HTTPException(status_code=502, detail="Telegram не применил новый аватар") from exc
    finally:
        await bot.session.close()

    session.add(
        AuditLog(admin_id=admin.id, action="update_bot_avatar", entity_type="bot")
    )
    await session.commit()
    return {"updated": True}


@router.delete("/avatar")
async def remove_bot_avatar(
    admin: AdminUser = Depends(get_current_full_admin),
    session: AsyncSession = Depends(get_session),
) -> dict[str, bool]:
    bot = Bot(settings.bot_token)
    try:
        await bot.remove_my_profile_photo()
    except TelegramAPIError as exc:
        raise HTTPException(status_code=502, detail="Telegram не удалил аватар") from exc
    finally:
        await bot.session.close()

    session.add(
        AuditLog(admin_id=admin.id, action="remove_bot_avatar", entity_type="bot")
    )
    await session.commit()
    return {"removed": True}


@router.put("/messages/{key}")
async def update_bot_message(
    key: str,
    payload: BotTextPayload,
    admin: AdminUser = Depends(get_current_full_admin),
    session: AsyncSession = Depends(get_session),
) -> dict:
    try:
        validate_bot_text(key, payload.text)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    setting = await session.get(BotTextSetting, key)
    if setting is None:
        setting = BotTextSetting(key=key, text=payload.text)
        session.add(setting)
    else:
        setting.text = payload.text

    session.add(
        AuditLog(
            admin_id=admin.id,
            action="update_bot_text",
            entity_type="bot_text",
            payload_json={"key": key},
        )
    )
    await session.commit()
    await session.refresh(setting)
    return serialize_text_setting(BOT_TEXTS_BY_KEY[key], setting)


@router.delete("/messages/{key}")
async def reset_bot_message(
    key: str,
    admin: AdminUser = Depends(get_current_full_admin),
    session: AsyncSession = Depends(get_session),
) -> dict:
    definition = BOT_TEXTS_BY_KEY.get(key)
    if definition is None:
        raise HTTPException(status_code=404, detail="Неизвестный текст бота")
    setting = await session.get(BotTextSetting, key)
    if setting is not None:
        await session.delete(setting)
    session.add(
        AuditLog(
            admin_id=admin.id,
            action="reset_bot_text",
            entity_type="bot_text",
            payload_json={"key": key},
        )
    )
    await session.commit()
    return serialize_text_setting(definition, None)


async def load_telegram_profile() -> dict:
    bot = Bot(settings.bot_token)
    try:
        me = await bot.get_me()
        name = await bot.get_my_name()
        short_description = await bot.get_my_short_description()
        description = await bot.get_my_description()
        photos = await bot.get_user_profile_photos(user_id=me.id, limit=1)
        avatar_id = photos.photos[0][-1].file_unique_id if photos.photos else None
        return {
            "id": me.id,
            "username": me.username,
            "name": name.name,
            "short_description": short_description.short_description,
            "description": description.description,
            "avatar_id": avatar_id,
        }
    except TelegramAPIError as exc:
        raise HTTPException(status_code=502, detail="Telegram не вернул профиль бота") from exc
    finally:
        await bot.session.close()


def serialize_text_setting(definition, setting: BotTextSetting | None) -> dict:
    return {
        "key": definition.key,
        "category": definition.category,
        "title": definition.title,
        "description": definition.description,
        "text": setting.text if setting is not None else definition.default,
        "default_text": definition.default,
        "variables": list(definition.variables),
        "is_custom": setting is not None,
        "updated_at": setting.updated_at if setting is not None else None,
    }
