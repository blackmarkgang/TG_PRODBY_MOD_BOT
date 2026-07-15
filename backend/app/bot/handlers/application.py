import re

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove

from app.bot.keyboards import portfolio_keyboard
from app.bot.states import ApplicationForm
from app.db.session import SessionLocal
from app.services.application_service import UserBannedError, create_pending_application, is_user_banned

router = Router()

URL_PATTERN = re.compile(r"https?://[^\s]+", re.IGNORECASE)
MAX_ATTACHMENTS = 10
TOTAL_STEPS = 5


def form_message(emoji: str, title: str, body: str, step: int | None = None) -> str:
    parts = [f"{emoji} <b>{title}</b>"]
    if step is not None:
        parts.append(f"<i>Шаг {step} из {TOTAL_STEPS}</i>")
    parts.append(body)
    return "\n\n".join(parts)


async def answer_form(message: Message, text: str, **kwargs) -> None:
    await message.answer(text, parse_mode="HTML", **kwargs)


@router.message(F.text == "Подать заявку")
async def start_application(message: Message, state: FSMContext) -> None:
    await begin_application(message, state, message.from_user.id if message.from_user else None)


@router.callback_query(F.data == "start_application")
async def start_application_callback(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    if isinstance(callback.message, Message):
        await begin_application(callback.message, state, callback.from_user.id)


async def begin_application(message: Message, state: FSMContext, telegram_id: int | None) -> None:
    await state.clear()
    if telegram_id is not None:
        async with SessionLocal() as session:
            if await is_user_banned(session, telegram_id):
                await answer_form(
                    message,
                    form_message(
                        "⛔",
                        "Доступ ограничен",
                        "Вы не можете подать новую заявку в Prod.by.",
                    ),
                    reply_markup=ReplyKeyboardRemove(),
                )
                return

    await state.update_data(files=[])
    await state.set_state(ApplicationForm.age)
    await answer_form(
        message,
        form_message(
            "🎂",
            "Сколько вам лет?",
            "Отправьте возраст одним числом.",
            step=1,
        ),
        reply_markup=ReplyKeyboardRemove(),
    )


@router.message(ApplicationForm.age)
async def receive_age(message: Message, state: FSMContext) -> None:
    if not message.text or not message.text.isdigit():
        await answer_form(message, form_message("⚠️", "Нужен возраст числом", "Например: <b>24</b>."))
        return

    age = int(message.text)
    if not 1 <= age <= 120:
        await answer_form(message, form_message("⚠️", "Проверьте возраст", "Допустимое значение: от 1 до 120."))
        return

    await state.update_data(age=age)
    await state.set_state(ApplicationForm.role_details)
    await answer_form(
        message,
        form_message(
            "🎙",
            "Расскажите о себе",
            "Чем вы занимаетесь в музыке или смежных творческих направлениях? Чем можете быть полезны сообществу?",
            step=2,
        ),
    )


@router.message(ApplicationForm.role_details)
async def receive_role_details(message: Message, state: FSMContext) -> None:
    if not message.text:
        await answer_form(message, form_message("⚠️", "Нужен текстовый ответ", "Расскажите о себе в нескольких предложениях."))
        return

    await state.update_data(role_details=message.text)
    await state.set_state(ApplicationForm.motivation)
    await answer_form(
        message,
        form_message(
            "💬",
            "Почему вы хотите попасть в Prod.by?",
            "Напишите коротко и своими словами.",
            step=3,
        ),
    )


@router.message(ApplicationForm.motivation)
async def receive_motivation(message: Message, state: FSMContext) -> None:
    if not message.text:
        await answer_form(message, form_message("⚠️", "Нужен текстовый ответ", "Опишите вашу мотивацию в нескольких предложениях."))
        return

    await state.update_data(motivation=message.text)
    await state.set_state(ApplicationForm.expectations)
    await answer_form(
        message,
        form_message(
            "🎯",
            "Что вы ожидаете от участия?",
            "Расскажите, что хотите получить от сообщества и чем готовы делиться.",
            step=4,
        ),
    )


@router.message(ApplicationForm.expectations)
async def receive_expectations(message: Message, state: FSMContext) -> None:
    if not message.text:
        await answer_form(message, form_message("⚠️", "Нужен текстовый ответ", "Опишите ваши ожидания от участия."))
        return

    await state.update_data(expectations=message.text)
    await state.set_state(ApplicationForm.portfolio)
    await answer_form(
        message,
        form_message(
            "📎",
            "Добавьте примеры работ",
            "Прикрепите до 10 файлов или ссылок. Этот шаг необязательный: когда закончите, нажмите <b>«Готово»</b>.",
            step=5,
        ),
        reply_markup=portfolio_keyboard(),
    )


@router.message(ApplicationForm.portfolio, F.text.in_({"Готово", "✅ Готово"}))
async def finish_portfolio(message: Message, state: FSMContext) -> None:
    await submit_application(message, state)


@router.message(ApplicationForm.portfolio)
async def receive_portfolio_item(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    files = list(data.get("files", []))
    if len(files) >= MAX_ATTACHMENTS:
        await answer_form(
            message,
            form_message("📦", "Лимит достигнут", "Добавлено 10 вложений. Нажмите <b>«Готово»</b>."),
            reply_markup=portfolio_keyboard(),
        )
        return

    items = extract_file_items(message)
    if not items:
        await answer_form(
            message,
            form_message(
                "⚠️",
                "Не удалось распознать вложение",
                "Отправьте файл, аудио, видео, фото или ссылку. Для завершения нажмите <b>«Готово»</b>.",
            ),
            reply_markup=portfolio_keyboard(),
        )
        return

    available = MAX_ATTACHMENTS - len(files)
    files.extend(items[:available])
    await state.update_data(files=files)
    await answer_form(
        message,
        form_message(
            "✅",
            "Вложение добавлено",
            f"Сейчас в заявке: <b>{len(files)} из {MAX_ATTACHMENTS}</b>. Можно отправить еще или нажать <b>«Готово»</b>.",
        ),
        reply_markup=portfolio_keyboard(),
    )


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
        for key in ("role_details", "motivation", "expectations")
        if data.get(key)
    }

    if message.from_user is None:
        await answer_form(
            message,
            form_message("⚠️", "Не удалось определить пользователя", "Отправьте /start и попробуйте еще раз."),
        )
        return

    async with SessionLocal() as session:
        try:
            application = await create_pending_application(
                session=session,
                tg_user=message.from_user,
                age=data["age"],
                music_role=None,
                answers=answers,
                files=data.get("files", []),
            )
        except UserBannedError:
            await state.clear()
            await answer_form(
                message,
                form_message(
                    "⛔",
                    "Доступ ограничен",
                    "Вы не можете отправить заявку в Prod.by.",
                ),
                reply_markup=ReplyKeyboardRemove(),
            )
            return

    await state.clear()
    await answer_form(
        message,
        form_message(
            "🎉",
            f"Заявка №{application.id} отправлена",
            "Администрация рассмотрит ее и пришлет результат в этот чат.",
        ),
        reply_markup=ReplyKeyboardRemove(),
    )
