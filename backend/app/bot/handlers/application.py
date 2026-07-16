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
from app.services.bot_text_service import render_bot_text

router = Router()

URL_PATTERN = re.compile(r"https?://[^\s]+", re.IGNORECASE)
MAX_ATTACHMENTS = 10


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
                    await render_bot_text("access_banned"),
                    reply_markup=ReplyKeyboardRemove(),
                )
                return
            if await is_group_member(message.bot, telegram_id):
                await answer_form(
                    message,
                    await render_bot_text("already_member"),
                    reply_markup=ReplyKeyboardRemove(),
                )
                return
            active_application = await get_active_application(session, telegram_id)
            if active_application is not None:
                await answer_form(
                    message,
                    await active_application_message(active_application),
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
    body = (
        escape(question["help_text"])
        if question.get("help_text")
        else await render_bot_text("question_default_help")
    )
    if question["answer_type"] == "number":
        body += f"\n\n{await render_bot_text('number_hint')}"
    await answer_form(
        message,
        await render_bot_text(
            "question_prompt",
            question=escape(question["text"]),
            help_text=body,
            step=index + 1,
            total=len(questions) + 1,
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
            await render_bot_text("text_answer_required"),
        )
        return
    if question["answer_type"] == "number" and not answer.isdigit():
        await answer_form(message, await render_bot_text("number_answer_required"))
        return
    if question["code"] == "age" and question["answer_type"] == "number" and not 1 <= int(answer) <= 120:
        await answer_form(
            message,
            await render_bot_text("age_invalid"),
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
        await render_bot_text(
            "portfolio_prompt",
            step=len(questions) + 1,
            total=len(questions) + 1,
            max_attachments=MAX_ATTACHMENTS,
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
            await render_bot_text("attachment_limit", max_attachments=MAX_ATTACHMENTS),
            reply_markup=portfolio_keyboard(has_attachments=True),
        )
        return

    items = extract_file_items(message)
    if not items:
        await answer_form(
            message,
            await render_bot_text("attachment_unrecognized"),
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
                    await render_bot_text("attachment_check_failed"),
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
            await render_bot_text("attachment_too_large"),
            reply_markup=portfolio_keyboard(has_attachments=bool(files)),
        )
        return

    available = MAX_ATTACHMENTS - len(files)
    files.extend(items[:available])
    await state.update_data(files=files)
    await answer_form(
        message,
        await render_bot_text(
            "attachment_added",
            count=len(files),
            max_attachments=MAX_ATTACHMENTS,
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
            await render_bot_text("user_unknown"),
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
                await render_bot_text("submit_banned"),
                reply_markup=ReplyKeyboardRemove(),
            )
            return
        except AttachmentTooLargeError:
            await answer_form(
                message,
                await render_bot_text("submit_attachment_too_large"),
                reply_markup=portfolio_keyboard(has_attachments=bool(data.get("files"))),
            )
            return
        except ActiveApplicationError as exc:
            await state.clear()
            await answer_form(
                message,
                await active_application_message(exc.application),
                reply_markup=ReplyKeyboardRemove(),
            )
            return

    await state.clear()
    await answer_form(
        message,
        await render_bot_text("application_submitted", application_id=application.id),
        reply_markup=ReplyKeyboardRemove(),
    )
