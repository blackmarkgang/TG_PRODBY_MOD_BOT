import re

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove

from app.bot.keyboards import ROLE_LABELS, portfolio_keyboard, roles_keyboard
from app.bot.states import ApplicationForm
from app.db.session import SessionLocal
from app.services.application_service import create_pending_application

router = Router()

CREATOR_ROLES = {"Артист", "Битмейкер / Продюсер"}
URL_PATTERN = re.compile(r"https?://[^\s]+", re.IGNORECASE)
MAX_ATTACHMENTS = 10


@router.message(F.text == "Подать заявку")
async def start_application(message: Message, state: FSMContext) -> None:
    await begin_application(message, state)


@router.callback_query(F.data == "start_application")
async def start_application_callback(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    if isinstance(callback.message, Message):
        await begin_application(callback.message, state)


async def begin_application(message: Message, state: FSMContext) -> None:
    await state.clear()
    await state.update_data(files=[])
    await state.set_state(ApplicationForm.age)
    await message.answer("Сколько вам лет?", reply_markup=ReplyKeyboardRemove())


@router.message(ApplicationForm.age)
async def receive_age(message: Message, state: FSMContext) -> None:
    if not message.text or not message.text.isdigit():
        await message.answer("Отправьте возраст числом.")
        return

    age = int(message.text)
    if not 1 <= age <= 120:
        await message.answer("Укажите корректный возраст от 1 до 120 лет.")
        return

    await state.update_data(age=age)
    await state.set_state(ApplicationForm.music_role)
    await message.answer("Чем вы занимаетесь в музыке?", reply_markup=roles_keyboard())


@router.message(ApplicationForm.music_role)
async def receive_music_role(message: Message, state: FSMContext) -> None:
    role = message.text or ""
    if role not in ROLE_LABELS:
        await message.answer("Выберите один из вариантов на клавиатуре.", reply_markup=roles_keyboard())
        return

    await state.update_data(music_role=role, portfolio_required=role in CREATOR_ROLES)

    if role in CREATOR_ROLES:
        await state.set_state(ApplicationForm.portfolio)
        prompt = (
            "Прикрепите несколько своих лучших треков, битов или ссылок на них. "
            "Можно отправить до 10 файлов/ссылок. Когда закончите, нажмите «Готово»."
        )
        await message.answer(prompt, reply_markup=portfolio_keyboard())
        return

    await state.set_state(ApplicationForm.role_details)
    if role == "Слушатель":
        await message.answer("Кого вы слушаете?", reply_markup=ReplyKeyboardRemove())
    else:
        await message.answer(
            "Коротко расскажите о себе и чем можете быть полезны сообществу.",
            reply_markup=ReplyKeyboardRemove(),
        )


@router.message(ApplicationForm.role_details)
async def receive_role_details(message: Message, state: FSMContext) -> None:
    if not message.text:
        await message.answer("Ответьте текстом.")
        return

    data = await state.get_data()
    if data["music_role"] == "Слушатель":
        await state.update_data(listener_artists=message.text)
        await state.set_state(ApplicationForm.listener_follows)
        await message.answer("За кем вы следите в музыкальной индустрии?")
        return

    await state.update_data(role_details=message.text)
    await ask_motivation(message, state)


@router.message(ApplicationForm.listener_follows)
async def receive_listener_follows(message: Message, state: FSMContext) -> None:
    if not message.text:
        await message.answer("Ответьте текстом.")
        return
    await state.update_data(listener_follows=message.text)
    await state.set_state(ApplicationForm.listener_likes)
    await message.answer("Что вам нравится в музыке?")


@router.message(ApplicationForm.listener_likes)
async def receive_listener_likes(message: Message, state: FSMContext) -> None:
    if not message.text:
        await message.answer("Ответьте текстом.")
        return
    await state.update_data(listener_likes=message.text)
    await ask_motivation(message, state)


async def ask_motivation(message: Message, state: FSMContext) -> None:
    await state.set_state(ApplicationForm.motivation)
    await message.answer("Почему вы хотите попасть в сообщество Prod.by?")


@router.message(ApplicationForm.motivation)
async def receive_motivation(message: Message, state: FSMContext) -> None:
    if not message.text:
        await message.answer("Ответьте текстом.")
        return
    await state.update_data(motivation=message.text)
    await state.set_state(ApplicationForm.expectations)
    await message.answer("Что вы ожидаете получить от участия?")


@router.message(ApplicationForm.expectations)
async def receive_expectations(message: Message, state: FSMContext) -> None:
    if not message.text:
        await message.answer("Ответьте текстом.")
        return
    await state.update_data(expectations=message.text)
    data = await state.get_data()
    if data["music_role"] in CREATOR_ROLES:
        await submit_application(message, state)
        return

    await state.set_state(ApplicationForm.portfolio)
    await message.answer(
        "При желании прикрепите файлы или ссылки на свои работы. "
        "Можно отправить до 10 файлов/ссылок. Для продолжения нажмите «Готово».",
        reply_markup=portfolio_keyboard(),
    )


@router.message(ApplicationForm.portfolio, F.text == "Готово")
async def finish_portfolio(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    if data.get("portfolio_required") and not data.get("files"):
        await message.answer("Для выбранной роли прикрепите хотя бы один файл или ссылку.")
        return

    if "motivation" not in data:
        await ask_motivation(message, state)
        return

    await submit_application(message, state)


@router.message(ApplicationForm.portfolio)
async def receive_portfolio_item(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    files = list(data.get("files", []))
    if len(files) >= MAX_ATTACHMENTS:
        await message.answer("Достигнут лимит: 10 файлов или ссылок. Нажмите «Готово».")
        return

    items = extract_file_items(message)
    if not items:
        await message.answer("Отправьте файл, аудио, видео или ссылку, либо нажмите «Готово».")
        return

    available = MAX_ATTACHMENTS - len(files)
    files.extend(items[:available])
    await state.update_data(files=files)
    await message.answer(f"Добавлено: {len(files)} из {MAX_ATTACHMENTS}.", reply_markup=portfolio_keyboard())


def extract_file_items(message: Message) -> list[dict]:
    caption = message.caption
    if message.audio:
        return [{
            "telegram_file_id": message.audio.file_id,
            "file_type": "audio",
            "file_name": message.audio.file_name or f"audio-{message.audio.file_unique_id}.mp3",
            "mime_type": message.audio.mime_type,
            "file_size": message.audio.file_size,
            "caption": caption,
        }]
    if message.document:
        return [{
            "telegram_file_id": message.document.file_id,
            "file_type": "document",
            "file_name": message.document.file_name or f"document-{message.document.file_unique_id}",
            "mime_type": message.document.mime_type,
            "file_size": message.document.file_size,
            "caption": caption,
        }]
    if message.video:
        return [{
            "telegram_file_id": message.video.file_id,
            "file_type": "video",
            "file_name": message.video.file_name or f"video-{message.video.file_unique_id}.mp4",
            "mime_type": message.video.mime_type,
            "file_size": message.video.file_size,
            "caption": caption,
        }]
    if message.voice:
        return [{
            "telegram_file_id": message.voice.file_id,
            "file_type": "voice",
            "file_name": f"voice-{message.voice.file_unique_id}.ogg",
            "mime_type": message.voice.mime_type,
            "file_size": message.voice.file_size,
            "caption": caption,
        }]
    if message.photo:
        photo = message.photo[-1]
        return [{
            "telegram_file_id": photo.file_id,
            "file_type": "photo",
            "file_name": f"photo-{photo.file_unique_id}.jpg",
            "mime_type": "image/jpeg",
            "file_size": photo.file_size,
            "caption": caption,
        }]
    if message.text:
        return [
            {
                "telegram_file_id": None,
                "file_type": "url",
                "file_name": None,
                "mime_type": None,
                "file_size": None,
                "url": url.rstrip(".,);]"),
                "caption": None,
            }
            for url in URL_PATTERN.findall(message.text)
        ]
    return []


async def submit_application(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    answers = {
        key: data[key]
        for key in (
            "role_details",
            "listener_artists",
            "listener_follows",
            "listener_likes",
            "motivation",
            "expectations",
        )
        if data.get(key)
    }

    if message.from_user is None:
        await message.answer("Не удалось определить пользователя. Попробуйте начать заново командой /start.")
        return

    async with SessionLocal() as session:
        application = await create_pending_application(
            session=session,
            tg_user=message.from_user,
            age=data["age"],
            music_role=data["music_role"],
            answers=answers,
            files=data.get("files", []),
        )

    await state.clear()
    await message.answer(
        f"Заявка №{application.id} отправлена. Мы сообщим вам о решении после рассмотрения.",
        reply_markup=ReplyKeyboardRemove(),
    )
