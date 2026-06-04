from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

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

_cancel_keyboard = InlineKeyboardMarkup(
    inline_keyboard=[[InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_fsm")]]
)


# --- Navigation callbacks ---

@router.callback_query(F.data == "cancel_fsm")
async def cb_cancel_fsm(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("❌ Действие отменено.")
    await callback.answer()


@router.callback_query(F.data == "mytasks_btn")
async def cb_mytasks_btn(callback: CallbackQuery, staff: Staff | None = None):
    if staff is None:
        await callback.answer()
        return
    from app.db.crud import get_tasks_for_staff
    from app.db.models import STATUS_LABELS, PRIORITY_LABELS
    async with async_session_factory() as session:
        tasks = await get_tasks_for_staff(session, staff.id)
    if not tasks:
        await callback.message.edit_text("✅ У вас нет активных задач.")
        await callback.answer()
        return
    lines = [f"📋 <b>Ваши задачи</b> ({len(tasks)}):\n"]
    for t in tasks:
        dl = t.deadline.strftime("%d.%m.%Y %H:%M") if t.deadline else "—"
        lines.append(f"• <b>{t.title}</b> (ID: {t.id})\n  {STATUS_LABELS[t.status]} | до {dl}")
    await callback.message.edit_text(
        "\n\n".join(lines),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Обновить", callback_data="mytasks_btn")]
        ]),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data == "tasks_all_btn")
async def cb_tasks_all_btn(callback: CallbackQuery, staff: Staff | None = None):
    if staff is None or staff.role.value not in ("admin", "senior_counselor"):
        await callback.answer("⛔ Нет прав", show_alert=True)
        return
    from app.db.crud import get_all_tasks
    from app.db.models import STATUS_LABELS, PRIORITY_LABELS
    async with async_session_factory() as session:
        tasks, total = await get_all_tasks(session, limit=10)
    lines = [f"📋 <b>Все задачи</b> ({total}):\n"]
    for t in tasks:
        dl = t.deadline.strftime("%d.%m.%Y %H:%M") if t.deadline else "—"
        assignee = t.assignee.full_name if t.assignee else "—"
        lines.append(f"• <b>{t.title}</b> (ID: {t.id})\n  {STATUS_LABELS[t.status]} | {assignee} | до {dl}")
    await callback.message.edit_text("\n\n".join(lines), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "tasks_pending_btn")
async def cb_tasks_pending_btn(callback: CallbackQuery, staff: Staff | None = None):
    if staff is None or staff.role.value not in ("admin", "senior_counselor"):
        await callback.answer("⛔ Нет прав", show_alert=True)
        return
    from app.db.crud import get_overdue_tasks
    from app.db.models import STATUS_LABELS, PRIORITY_LABELS
    async with async_session_factory() as session:
        tasks = await get_overdue_tasks(session)
    if not tasks:
        await callback.message.edit_text("✅ Просроченных задач нет.")
        await callback.answer()
        return
    lines = [f"⚠️ <b>Просроченные задачи</b> ({len(tasks)}):\n"]
    for t in tasks:
        assignee = t.assignee.full_name if t.assignee else "—"
        lines.append(f"• <b>{t.title}</b> (ID: {t.id})\n  {assignee}")
    await callback.message.edit_text("\n\n".join(lines), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "templates_list_btn")
async def cb_templates_list_btn(callback: CallbackQuery, staff: Staff | None = None):
    if staff is None or staff.role.value not in ("admin", "senior_counselor"):
        await callback.answer("⛔ Нет прав", show_alert=True)
        return
    from app.db.crud import get_all_templates
    from app.db.models import PRIORITY_LABELS, ROLE_LABELS
    async with async_session_factory() as session:
        templates = await get_all_templates(session)
    if not templates:
        await callback.message.edit_text("📋 Шаблонов нет.")
        await callback.answer()
        return
    lines = ["📋 <b>Шаблоны задач:</b>\n"]
    for t in templates:
        role_str = ROLE_LABELS.get(t.group_role, "—") if t.group_role else "—"
        lines.append(f"<b>{t.title}</b> (ID: {t.id})\n  {PRIORITY_LABELS[t.priority]} | {role_str}")
    await callback.message.edit_text("\n\n".join(lines), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "find_replacement")
async def cb_find_replacement(callback: CallbackQuery, staff: Staff | None = None):
    if staff is None or staff.role != StaffRole.admin:
        await callback.answer("⛔ Нет прав", show_alert=True)
        return
    await callback.message.edit_text(
        "🔍 Поиск замены\n\nВыберите роль:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="👤 Вожатый", callback_data="free_staff:counselor")],
            [InlineKeyboardButton(text="⭐ Старший вожатый", callback_data="free_staff:senior_counselor")],
            [InlineKeyboardButton(text="🧑‍🏫 Воспитатель", callback_data="free_staff:educator")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_fsm")],
        ]),
    )
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

        # Кнопки для каждого сотрудника + пагинация
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
