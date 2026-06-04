from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.bot.keyboards import (
    cancel_kb,
    confirm_kb,
    pagination_keyboard,
    role_menu,
    staff_actions_menu,
    staff_item_kb,
)
from app.bot.states import AddStaffFSM
from app.bot.texts import format_staff_item
from app.db.base import async_session_factory
from app.db.crud import (
    create_staff,
    deactivate_staff,
    get_all_staff_paginated,
    get_staff_by_id,
    get_staff_by_telegram_id,
    log_action,
    update_staff,
)
from app.db.models import ROLE_LABELS, Staff, StaffRole

router = Router(name="admin")

PAGE_SIZE = 5
_ADMIN_ROLES = {StaffRole.admin}


# ── cancel FSM ────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "cancel_fsm")
async def cb_cancel_fsm(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    try:
        await callback.message.edit_text("❌ Действие отменено.")
    except Exception:
        await callback.message.answer("❌ Действие отменено.")
    await callback.answer()


# ── Список сотрудников ────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("staff_list:"))
async def cb_staff_list(callback: CallbackQuery, staff: Staff | None = None):
    if staff is None or staff.role not in _ADMIN_ROLES:
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
        markup = staff_actions_menu()
    else:
        from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
        from aiogram.utils.keyboard import InlineKeyboardBuilder
        total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
        lines = [f"📋 <b>Сотрудники</b> (стр. {page + 1}/{total_pages})\n"]
        for s in items:
            lines.append(format_staff_item(s))
        text = "\n\n".join(lines)

        builder = InlineKeyboardBuilder()
        for s in items:
            builder.button(
                text=f"{'✅' if s.is_active else '❌'} {s.full_name}",
                callback_data=f"staff_item:{s.id}",
            )
        builder.adjust(1)
        nav = []
        if page > 0:
            nav.append(InlineKeyboardButton(text="◀️", callback_data=f"staff_list:{page - 1}"))
        if page < total_pages - 1:
            nav.append(InlineKeyboardButton(text="▶️", callback_data=f"staff_list:{page + 1}"))
        if nav:
            builder.row(*nav)
        builder.row(InlineKeyboardButton(text="➕ Добавить", callback_data="add_staff"))
        markup = builder.as_markup()

    if edit:
        try:
            await message.edit_text(text, reply_markup=markup, parse_mode="HTML")
        except Exception:
            await message.answer(text, reply_markup=markup, parse_mode="HTML")
    else:
        await message.answer(text, reply_markup=markup, parse_mode="HTML")


@router.callback_query(F.data.startswith("staff_item:"))
async def cb_staff_item(callback: CallbackQuery, staff: Staff | None = None):
    if staff is None or staff.role not in _ADMIN_ROLES:
        await callback.answer("⛔ Нет прав", show_alert=True)
        return
    staff_id = int(callback.data.split(":")[1])
    async with async_session_factory() as session:
        target = await get_staff_by_id(session, staff_id)
    if not target:
        await callback.answer("❌ Сотрудник не найден", show_alert=True)
        return
    text = format_staff_item(target)
    await callback.message.edit_text(text, reply_markup=staff_item_kb(staff_id), parse_mode="HTML")
    await callback.answer()


# ── Добавить сотрудника FSM ───────────────────────────────────────────────────

@router.callback_query(F.data == "add_staff")
async def cb_add_staff(callback: CallbackQuery, state: FSMContext, staff: Staff | None = None):
    if staff is None or staff.role not in _ADMIN_ROLES:
        await callback.answer("⛔ Нет прав", show_alert=True)
        return
    await callback.message.answer(
        "➕ <b>Добавление сотрудника</b>\n\nВведите <b>Telegram ID</b> нового сотрудника:",
        reply_markup=cancel_kb(), parse_mode="HTML",
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

    # F02: отправить онбординг новому сотруднику
    try:
        from app.bot.bot import get_bot
        await get_bot().send_message(
            telegram_id,
            f"👋 Вас добавили в систему лагеря!\n\n"
            f"Ваша роль: <b>{ROLE_LABELS[role]}</b>\n\n"
            f"Нажмите /start для начала работы.",
            parse_mode="HTML",
        )
    except Exception:
        pass

    await callback.message.edit_text(
        f"✅ Сотрудник добавлен!\n\n"
        f"👤 <b>{full_name}</b>\n"
        f"Роль: {ROLE_LABELS[role]}\n"
        f"Telegram ID: <code>{telegram_id}</code>",
        reply_markup=staff_item_kb(new_staff.id),
        parse_mode="HTML",
    )
    await state.clear()
    await callback.answer()


# ── Изменить роль ─────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("edit_role_prompt:"))
async def cb_edit_role_prompt(callback: CallbackQuery, staff: Staff | None = None):
    if staff is None or staff.role not in _ADMIN_ROLES:
        await callback.answer("⛔ Нет прав", show_alert=True)
        return
    staff_id = int(callback.data.split(":")[1])
    from app.bot.keyboards import staff_edit_role_keyboard
    await callback.message.edit_text(
        "Выберите новую роль:", reply_markup=staff_edit_role_keyboard(staff_id)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("edit_role:"))
async def cb_edit_role(callback: CallbackQuery, staff: Staff | None = None):
    if staff is None or staff.role not in _ADMIN_ROLES:
        await callback.answer("⛔ Нет прав", show_alert=True)
        return
    parts = callback.data.split(":")
    staff_id = int(parts[1])
    role = StaffRole(parts[2])
    async with async_session_factory() as session:
        target = await update_staff(session, staff_id, role=role)
    if target:
        await callback.message.edit_text(
            f"✅ Роль <b>{target.full_name}</b> изменена на <b>{ROLE_LABELS[role]}</b>.",
            reply_markup=staff_item_kb(staff_id),
            parse_mode="HTML",
        )
    await callback.answer()


# ── Деактивировать ────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("deactivate_staff:"))
async def cb_deactivate_prompt(callback: CallbackQuery, staff: Staff | None = None):
    if staff is None or staff.role not in _ADMIN_ROLES:
        await callback.answer("⛔ Нет прав", show_alert=True)
        return
    staff_id = int(callback.data.split(":")[1])
    async with async_session_factory() as session:
        target = await get_staff_by_id(session, staff_id)
    if not target:
        await callback.answer("❌ Не найден", show_alert=True)
        return
    await callback.message.edit_text(
        f"❗ Деактивировать <b>{target.full_name}</b>?",
        reply_markup=confirm_kb(f"deactivate_confirm:{staff_id}", f"staff_item:{staff_id}"),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("deactivate_confirm:"))
async def cb_deactivate_confirm(callback: CallbackQuery, staff: Staff | None = None):
    if staff is None or staff.role not in _ADMIN_ROLES:
        await callback.answer("⛔ Нет прав", show_alert=True)
        return
    staff_id = int(callback.data.split(":")[1])
    async with async_session_factory() as session:
        target = await deactivate_staff(session, staff_id)
    if target:
        await callback.message.edit_text(
            f"✅ Сотрудник <b>{target.full_name}</b> деактивирован.",
            parse_mode="HTML",
        )
    await callback.answer()
