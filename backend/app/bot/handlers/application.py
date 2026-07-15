import re
from html import escape

from aiogram import F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove
from sqlalchemy import select

from app.bot.keyboards import portfolio_keyboard
from app.bot.states import ApplicationForm
from app.db.models import ApplicationQuestion
from app.db.session import SessionLocal
from app.services.application_service import (
    ActiveApplicationError,
    MAX_APPLICATION_FILE_SIZE,
    AttachmentTooLargeError,
    UserBannedError,
    create_pending_application,
    is_user_banned,
)
from app.services.community_access import (
    active_application_message,
    get_active_application,
    is_group_member,
)

router = Router()

URL_PATTERN = re.compile(r"https?://[^\s]+", re.IGNORECASE)
MAX_ATTACHMENTS = 10


def form_message(
    emoji: str,
    title: str,
    body: str,
    step: int | None = None,
    total_steps: int | None = None,
) -> str:
    parts = [f"{emoji} <b>{title}</b>"]
    if step is not None and total_steps is not None:
        parts.append(f"<i>Шаг {step} из {total_steps}</i>")
    parts.append(body)
    return "\n\n".join(parts)


async def answer_form(message: Message, text: str, **kwargs) -> None:
    await message.answer(text, parse_mode="HTML", **kwargs)


async def load_questions() -> list[dict]:
    async with SessionLocal() as session:
        result = await session.execute(
            select(ApplicationQuestion).order_by(ApplicationQuestion.sort_order)
        )
        return [
            {
                "code": question.code,
                "text": question.text,
                "help_text": question.help_text,
                "answer_type": question.answer_type,
            }
            for question in result.scalars().all()
        ]


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
            if await is_group_member(message.bot, telegram_id):
                await answer_form(
                    message,
                    form_message(
                        "✅",
                        "Вы уже состоите в Prod.by",
                        "Повторная заявка не требуется — доступ к сообществу у вас уже есть.",
                    ),
                    reply_markup=ReplyKeyboardRemove(),
                )
                return
            active_application = await get_active_application(session, telegram_id)
            if active_application is not None:
                await answer_form(
                    message,
                    active_application_message(active_application),
                    reply_markup=ReplyKeyboardRemove(),
                )
                return

    questions = await load_questions()
    await state.update_data(
        files=[],
        questions=questions,
        question_index=0,
        question_answers={},
    )
    if questions:
        await state.set_state(ApplicationForm.question)
        await show_question(message, state)
    else:
        await show_portfolio_step(message, state)


async def show_question(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    questions = data["questions"]
    index = data["question_index"]
    question = questions[index]
    body = escape(question.get("help_text") or "Отправьте ответ сообщением.")
    if question["answer_type"] == "number":
        body += "\n\n<i>Ответ должен быть числом.</i>"
    await answer_form(
        message,
        form_message(
            "💬",
            escape(question["text"]),
            body,
            step=index + 1,
            total_steps=len(questions) + 1,
        ),
        reply_markup=ReplyKeyboardRemove(),
    )


@router.message(ApplicationForm.question)
async def receive_question_answer(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    questions = data["questions"]
    index = data["question_index"]
    question = questions[index]
    answer = message.text.strip() if message.text else ""
    if not answer:
        await answer_form(
            message,
            form_message("⚠️", "Нужен текстовый ответ", "Отправьте ответ обычным сообщением."),
        )
        return
    if question["answer_type"] == "number" and not answer.isdigit():
        await answer_form(message, form_message("⚠️", "Нужно число", "Например: <b>24</b>."))
        return
    if question["code"] == "age" and question["answer_type"] == "number" and not 1 <= int(answer) <= 120:
        await answer_form(
            message,
            form_message("⚠️", "Проверьте возраст", "Допустимое значение: от 1 до 120."),
        )
        return

    answers = dict(data.get("question_answers", {}))
    answers[question["code"]] = answer
    next_index = index + 1
    await state.update_data(question_answers=answers, question_index=next_index)
    if next_index < len(questions):
        await show_question(message, state)
    else:
        await show_portfolio_step(message, state)


async def show_portfolio_step(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    questions = data.get("questions", [])
    await state.set_state(ApplicationForm.portfolio)
    await answer_form(
        message,
        form_message(
            "📎",
            "Добавьте примеры работ",
            "Прикрепите до 10 файлов или ссылок. Размер одного файла — не более <b>10 МБ</b>. "
            "Можно продолжить без вложений — нажмите <b>«Пропустить вложения»</b>.",
            step=len(questions) + 1,
            total_steps=len(questions) + 1,
        ),
        reply_markup=portfolio_keyboard(has_attachments=False),
    )


@router.message(
    ApplicationForm.portfolio,
    F.text.in_({"Готово", "✅ Готово", "Пропустить вложения", "⏭ Пропустить вложения"}),
)
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
            reply_markup=portfolio_keyboard(has_attachments=True),
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
            reply_markup=portfolio_keyboard(has_attachments=bool(files)),
        )
        return

    for item in items:
        if item.get("telegram_file_id") and item.get("file_size") is None:
            try:
                telegram_file = await message.bot.get_file(item["telegram_file_id"])
                item["file_size"] = telegram_file.file_size
            except TelegramAPIError:
                await answer_form(
                    message,
                    form_message(
                        "⚠️",
                        "Не удалось проверить размер файла",
                        "Попробуйте отправить файл еще раз или продолжите без него.",
                    ),
                    reply_markup=portfolio_keyboard(has_attachments=bool(files)),
                )
                return
    oversized_item = next(
        (
            item
            for item in items
            if item.get("file_size") is not None
            and item["file_size"] > MAX_APPLICATION_FILE_SIZE
        ),
        None,
    )
    if oversized_item is not None:
        await answer_form(
            message,
            form_message(
                "⚠️",
                "Файл слишком большой",
                "Размер одного файла не должен превышать <b>10 МБ</b>. Отправьте файл меньшего размера или продолжите без него.",
            ),
            reply_markup=portfolio_keyboard(has_attachments=bool(files)),
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
        reply_markup=portfolio_keyboard(has_attachments=True),
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
    answers = dict(data.get("question_answers", {}))
    questions = data.get("questions", [])
    answer_labels = {
        question["code"]: question["text"]
        for question in questions
        if question["code"] in answers
    }
    age_raw = answers.get("age")
    age = int(age_raw) if age_raw is not None and age_raw.isdigit() else None
    if age is not None:
        answers.pop("age", None)
        answer_labels.pop("age", None)

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
                age=age,
                music_role=None,
                answers=answers,
                answer_labels=answer_labels,
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
        except AttachmentTooLargeError:
            await answer_form(
                message,
                form_message("⚠️", "Файл слишком большой", "Удалите файл больше 10 МБ и попробуйте снова."),
                reply_markup=portfolio_keyboard(has_attachments=bool(data.get("files"))),
            )
            return
        except ActiveApplicationError as exc:
            await state.clear()
            await answer_form(
                message,
                active_application_message(exc.application),
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
