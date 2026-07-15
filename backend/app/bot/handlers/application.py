from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from app.bot.states import ApplicationForm
from app.db.session import SessionLocal
from app.services.application_service import create_pending_application

router = Router()


@router.message(lambda message: message.text == "Submit application")
async def start_application(message: Message, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(ApplicationForm.age)
    await message.answer("How old are you?")


@router.message(ApplicationForm.age)
async def receive_age(message: Message, state: FSMContext) -> None:
    if not message.text or not message.text.isdigit():
        await message.answer("Send your age as a number.")
        return
    await state.update_data(age=int(message.text))
    await state.set_state(ApplicationForm.music_role)
    await message.answer(
        "What do you do in music?\n"
        "Artist / Beatmaker / Producer / Sound engineer / Editor / Designer / Listener / Other"
    )


@router.message(ApplicationForm.music_role)
async def receive_music_role(message: Message, state: FSMContext) -> None:
    await state.update_data(music_role=message.text or "Other")
    await state.set_state(ApplicationForm.role_details)
    await message.answer("Send links/files to your best work, or tell us briefly about yourself.")


@router.message(ApplicationForm.role_details)
async def receive_role_details(message: Message, state: FSMContext) -> None:
    await state.update_data(role_details=message.text or message.caption or "file attached")
    await state.set_state(ApplicationForm.motivation)
    await message.answer("Why do you want to join Prod.by?")


@router.message(ApplicationForm.motivation)
async def receive_motivation(message: Message, state: FSMContext) -> None:
    await state.update_data(motivation=message.text or "")
    await state.set_state(ApplicationForm.expectations)
    await message.answer("What do you expect from participation?")


@router.message(ApplicationForm.expectations)
async def finish_application(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    data["expectations"] = message.text or ""

    async with SessionLocal() as session:
        application = await create_pending_application(
            session=session,
            tg_user=message.from_user,
            age=data["age"],
            music_role=data["music_role"],
            answers={
                "role_details": data.get("role_details"),
                "motivation": data.get("motivation"),
                "expectations": data.get("expectations"),
            },
        )

    await state.clear()
    await message.answer(f"Application #{application.id} submitted. We will notify you after review.")

