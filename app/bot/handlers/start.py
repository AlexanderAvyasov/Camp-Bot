from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message

from app.bot.keyboards import admin_main_menu, staff_main_menu
from app.bot.texts import ONBOARDING
from app.db.models import ROLE_LABELS, Staff, StaffRole

router = Router(name="start")

# Track first visits to show onboarding only once
_onboarded: set[int] = set()


@router.message(CommandStart())
async def cmd_start(message: Message, staff: Staff | None = None):
    if staff is None:
        await message.answer(
            "❌ Вы не зарегистрированы в системе лагеря.\n"
            "Обратитесь к администратору для получения доступа."
        )
        return

    is_new = staff.telegram_id not in _onboarded
    if is_new:
        _onboarded.add(staff.telegram_id)
        onboarding_text = ONBOARDING.get(staff.role, "👋 Добро пожаловать!")
        await message.answer(onboarding_text)

    role_label = ROLE_LABELS.get(staff.role, staff.role)
    greeting = f"Привет, <b>{staff.full_name}</b>!\nВаша роль: {role_label}"

    if staff.role == StaffRole.admin:
        await message.answer(greeting, reply_markup=admin_main_menu(), parse_mode="HTML")
    else:
        await message.answer(greeting, reply_markup=staff_main_menu(role_label), parse_mode="HTML")
