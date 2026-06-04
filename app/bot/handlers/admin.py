from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from app.bot.keyboards import (
    pagination_keyboard,
    role_menu,
    schedule_menu,
    sessions_menu,
    staff_actions_menu,
    staff_list_empty_keyboard,
)
from app.bot.middleware import require_role
from app.bot.states import AddStaffFSM
from app.bot.texts import format_staff_item
from app.db.base import async_session_factory
from app.db.crud import (
    create_staff,
    deactivate_staff,
    get_all_staff_paginated,
    get_staff_by_telegram_id,
    log_action,
)
from app.db.models import ROLE_LABELS, Staff, StaffRole

router = Router(name="admin")

PAGE_SIZE = 5

_cancel_keyboard = InlineKeyboardMarkup(
    inline_keyboard=[[InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_fsm")]]
)


# --- Navigation callbacks ---

@router.callback_query(F.data == "cancel_fsm")
async def cb_cancel_fsm(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("❌ Действие отменено.")
    await callback.answer()


# --- Sections via inline from reply menu ---

@router.callback_query(F.data == "staff_section")
async def cb_staff_section(callback: CallbackQuery, staff: Staff | None = None):
    if staff is None or staff.role != StaffRole.admin:
        await callback.answer("⛔ Нет прав", show_alert=True)
        return
    await callback.message.edit_text("👥 Управление сотрудниками:", reply_markup=staff_actions_menu())
    await callback.answer()


@router.callback_query(F.data == "session_list")
async def cb_session_list(callback: CallbackQuery, staff: Staff | None = None):
    if staff is None or staff.role != StaffRole.admin:
        await callback.answer("⛔ Нет прав", show_alert=True)
        return
    from app.db.crud import get_all_sessions
    async with async_session_factory() as session:
        sessions = await get_all_sessions(session)
    if not sessions:
        await callback.message.edit_text(
            "📋 Смен пока нет.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="➕ Новая смена", callback_data="session_new")]
            ]),
        )
        await callback.answer()
        return
    lines = ["📋 <b>Смены:</b>\n"]
    for s in sessions:
        status = "🟢 активна" if s.is_active else "⚪"
        lines.append(f"<b>{s.name}</b> (ID: {s.id})\n  {s.start_date.strftime('%d.%m.%Y')} — {s.end_date.strftime('%d.%m.%Y')}  {status}")
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Новая смена", callback_data="session_new")]
    ])
    await callback.message.edit_text("\n\n".join(lines), reply_markup=kb, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "session_new")
async def cb_session_new(callback: CallbackQuery, state: FSMContext, staff: Staff | None = None):
    if staff is None or staff.role != StaffRole.admin:
        await callback.answer("⛔ Нет прав", show_alert=True)
        return
    from app.bot.states import SessionFSM
    await callback.message.edit_text(
        "🏕 Создание смены\n\nВведите <b>название</b> смены:",
        reply_markup=_cancel_keyboard, parse_mode="HTML",
    )
    await state.set_state(SessionFSM.waiting_name)
    await callback.answer()


@router.callback_query(F.data == "schedule_view")
async def cb_schedule_view(callback: CallbackQuery, staff: Staff | None = None):
    if staff is None:
        await callback.answer()
        return
    from app.db.crud import get_active_session, get_schedule
    async with async_session_factory() as session:
        active = await get_active_session(session)
        if not active:
            await callback.message.edit_text("❌ Нет активной смены.")
            await callback.answer()
            return
        items = await get_schedule(session, active.id)
    from app.bot.handlers.sessions import _format_schedule
    kb = None
    if staff.role == StaffRole.admin:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➕ Добавить мероприятие", callback_data="schedule_add")]
        ])
    await callback.message.edit_text(_format_schedule(active.name, items), reply_markup=kb, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "schedule_add")
async def cb_schedule_add(callback: CallbackQuery, state: FSMContext, staff: Staff | None = None):
    if staff is None or staff.role != StaffRole.admin:
        await callback.answer("⛔ Нет прав", show_alert=True)
        return
    from app.db.crud import get_active_session
    from app.bot.states import ScheduleAddFSM
    from app.bot.handlers.sessions import _day_type_kb
    async with async_session_factory() as session:
        active = await get_active_session(session)
    if not active:
        await callback.message.edit_text("❌ Нет активной смены.")
        await callback.answer()
        return
    await state.update_data(session_id=active.id)
    await callback.message.edit_text(
        f"📅 Добавление в расписание смены <b>{active.name}</b>\n\nВыберите тип дня:",
        reply_markup=_day_type_kb, parse_mode="HTML",
    )
    await state.set_state(ScheduleAddFSM.waiting_day_type)
    await callback.answer()


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
        markup = staff_list_empty_keyboard()
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
        reply_markup=_cancel_keyboard,
        parse_mode="HTML",
    )
    await state.set_state(AddStaffFSM.waiting_telegram_id)


@router.callback_query(F.data == "add_staff")
async def cb_add_staff(callback: CallbackQuery, state: FSMContext, staff: Staff | None = None):
    if staff is None or staff.role != StaffRole.admin:
        await callback.answer("⛔ Нет прав", show_alert=True)
        return
    await callback.message.edit_text(
        "➕ Добавление сотрудника\n\nВведите <b>Telegram ID</b> нового сотрудника:",
        reply_markup=_cancel_keyboard,
        parse_mode="HTML",
    )
    await state.set_state(AddStaffFSM.waiting_telegram_id)
    await callback.answer()


@router.message(AddStaffFSM.waiting_telegram_id)
async def fsm_get_telegram_id(message: Message, state: FSMContext):
    text = message.text.strip()
    if not text.isdigit():
        await message.answer("❌ Telegram ID должен быть числом. Попробуйте ещё раз:", reply_markup=_cancel_keyboard)
        return
    await state.update_data(telegram_id=int(text))
    await message.answer("Введите <b>полное имя</b> сотрудника (ФИО):", reply_markup=_cancel_keyboard, parse_mode="HTML")
    await state.set_state(AddStaffFSM.waiting_full_name)


@router.message(AddStaffFSM.waiting_full_name)
async def fsm_get_full_name(message: Message, state: FSMContext):
    full_name = message.text.strip()
    if len(full_name) < 2:
        await message.answer("❌ Имя слишком короткое. Введите полное имя:", reply_markup=_cancel_keyboard)
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
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➕ Добавить ещё", callback_data="add_staff")],
        ]),
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
