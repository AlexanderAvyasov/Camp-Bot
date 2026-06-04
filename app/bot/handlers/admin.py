from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.bot.keyboards import pagination_keyboard, role_menu
from app.bot.middleware import require_role
from app.bot.states import AddStaffFSM
from app.bot.texts import format_staff_item
from app.db.crud import (
    create_staff,
    deactivate_staff,
    get_all_staff_paginated,
    get_staff_by_telegram_id,
    log_action,
)
from app.db.models import ROLE_LABELS, Staff, StaffRole
from app.db.base import async_session_factory

router = Router(name="admin")

PAGE_SIZE = 5


# --- /staff_list ---

@router.message(Command("staff_list"))
async def cmd_staff_list(message: Message, staff: Staff | None = None):
    if staff is None or staff.role != StaffRole.admin:
        await message.answer("⛔ У вас нет прав для выполнения этой команды.")
        return
    await _send_staff_page(message, page=0)


@router.callback_query(F.data.startswith("staff_list:"))
async def cb_staff_list(callback: CallbackQuery, staff: Staff | None = None):
    if staff is None or staff.role != StaffRole.admin:
        await callback.answer("⛔ Нет прав", show_alert=True)
        return
    page = int(callback.data.split(":")[1])
    await _send_staff_page(callback.message, page=page, edit=True)
    await callback.answer()


async def _send_staff_page(message: Message, page: int, edit: bool = False):
    async with async_session_factory() as session:
        items, total = await get_all_staff_paginated(session, offset=page * PAGE_SIZE, limit=PAGE_SIZE)

    if not items:
        text = "📋 Список сотрудников пуст."
        markup = None
    else:
        total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
        lines = [f"📋 <b>Сотрудники</b> (стр. {page + 1}/{total_pages})\n"]
        for s in items:
            lines.append(format_staff_item(s))
        text = "\n\n".join(lines)
        markup = pagination_keyboard(page, total_pages)

    if edit:
        await message.edit_text(text, reply_markup=markup, parse_mode="HTML")
    else:
        await message.answer(text, reply_markup=markup, parse_mode="HTML")


# --- /add_staff FSM ---

@router.message(Command("add_staff"))
async def cmd_add_staff(message: Message, state: FSMContext, staff: Staff | None = None):
    if staff is None or staff.role != StaffRole.admin:
        await message.answer("⛔ У вас нет прав для выполнения этой команды.")
        return
    await message.answer(
        "➕ Добавление сотрудника\n\nВведите <b>Telegram ID</b> нового сотрудника:",
        parse_mode="HTML",
    )
    await state.set_state(AddStaffFSM.waiting_telegram_id)


@router.callback_query(F.data == "add_staff")
async def cb_add_staff(callback: CallbackQuery, state: FSMContext, staff: Staff | None = None):
    if staff is None or staff.role != StaffRole.admin:
        await callback.answer("⛔ Нет прав", show_alert=True)
        return
    await callback.message.answer(
        "➕ Добавление сотрудника\n\nВведите <b>Telegram ID</b> нового сотрудника:",
        parse_mode="HTML",
    )
    await state.set_state(AddStaffFSM.waiting_telegram_id)
    await callback.answer()


@router.message(AddStaffFSM.waiting_telegram_id)
async def fsm_get_telegram_id(message: Message, state: FSMContext):
    text = message.text.strip()
    if not text.isdigit():
        await message.answer("❌ Telegram ID должен быть числом. Попробуйте ещё раз:")
        return
    await state.update_data(telegram_id=int(text))
    await message.answer("Введите <b>полное имя</b> сотрудника (ФИО):", parse_mode="HTML")
    await state.set_state(AddStaffFSM.waiting_full_name)


@router.message(AddStaffFSM.waiting_full_name)
async def fsm_get_full_name(message: Message, state: FSMContext):
    full_name = message.text.strip()
    if len(full_name) < 2:
        await message.answer("❌ Имя слишком короткое. Введите полное имя:")
        return
    await state.update_data(full_name=full_name)
    await message.answer(
        "Выберите <b>роль</b> сотрудника:", reply_markup=role_menu(), parse_mode="HTML"
    )
    await state.set_state(AddStaffFSM.waiting_role)


@router.callback_query(AddStaffFSM.waiting_role, F.data.startswith("set_role:"))
async def fsm_get_role(callback: CallbackQuery, state: FSMContext, staff: Staff | None = None):
    role_value = callback.data.split(":")[1]
    try:
        role = StaffRole(role_value)
    except ValueError:
        await callback.answer("❌ Неверная роль", show_alert=True)
        return

    data = await state.get_data()
    telegram_id = data["telegram_id"]
    full_name = data["full_name"]

    async with async_session_factory() as session:
        existing = await get_staff_by_telegram_id(session, telegram_id)
        if existing:
            await callback.message.edit_text(
                f"⚠️ Сотрудник с Telegram ID <code>{telegram_id}</code> уже существует.",
                parse_mode="HTML",
            )
            await state.clear()
            await callback.answer()
            return

        new_staff = await create_staff(session, telegram_id, full_name, role)
        if staff:
            await log_action(session, staff.id, "add_staff", new_staff.id)

    role_label = ROLE_LABELS[role]
    await callback.message.edit_text(
        f"✅ Сотрудник добавлен!\n\n"
        f"👤 <b>{full_name}</b>\n"
        f"Роль: {role_label}\n"
        f"Telegram ID: <code>{telegram_id}</code>",
        parse_mode="HTML",
    )
    await state.clear()
    await callback.answer()


# --- /remove_staff ---

@router.message(Command("remove_staff"))
async def cmd_remove_staff(message: Message, staff: Staff | None = None):
    if staff is None or staff.role != StaffRole.admin:
        await message.answer("⛔ У вас нет прав для выполнения этой команды.")
        return

    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer(
            "❌ Укажите Telegram ID сотрудника.\n"
            "Формат: /remove_staff <telegram_id>"
        )
        return

    target_arg = args[1].strip()
    if not target_arg.isdigit():
        await message.answer("❌ Telegram ID должен быть числом.")
        return

    target_telegram_id = int(target_arg)

    async with async_session_factory() as session:
        target = await get_staff_by_telegram_id(session, target_telegram_id)
        if not target:
            await message.answer(f"❌ Сотрудник с ID <code>{target_telegram_id}</code> не найден.", parse_mode="HTML")
            return
        if not target.is_active:
            await message.answer(f"⚠️ Сотрудник <b>{target.full_name}</b> уже деактивирован.", parse_mode="HTML")
            return

        await deactivate_staff(session, target.id)
        if staff:
            await log_action(session, staff.id, "remove_staff", target.id)

    await message.answer(
        f"✅ Сотрудник <b>{target.full_name}</b> деактивирован.",
        parse_mode="HTML",
    )
