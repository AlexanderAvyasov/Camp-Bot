from datetime import date

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.bot.keyboards import (
    cancel_kb,
    day_type_kb,
    schedule_add_more_kb,
    schedule_menu,
    session_item_kb,
    sessions_menu,
    skip_cancel_kb,
)
from app.bot.states import ScheduleAddFSM, SessionFSM
from app.db.base import async_session_factory
from app.db.crud import (
    activate_session,
    add_schedule_item,
    copy_schedule,
    create_session,
    get_active_session,
    get_all_sessions,
    get_schedule,
    get_session_by_id,
)
from app.db.models import DAY_TYPE_LABELS, DayType, Staff, StaffRole

router = Router(name="sessions")

_ADMIN_ROLES = {StaffRole.admin, StaffRole.senior_counselor}
_DATE_FMT = "%d.%m.%Y"


def _format_schedule(session_name: str, items: list) -> str:
    if not items:
        return f"📅 <b>Расписание: {session_name}</b>\n\nРасписание пусто."
    lines = [f"📅 <b>Расписание: {session_name}</b>\n"]
    current_type = None
    for item in sorted(items, key=lambda x: (x.day_type.value, x.time)):
        if item.day_type != current_type:
            current_type = item.day_type
            lines.append(f"\n<b>{DAY_TYPE_LABELS[item.day_type]}</b>")
        lines.append(f"  {item.time.strftime('%H:%M')} — {item.label}")
    return "\n".join(lines)


# ── Список смен ───────────────────────────────────────────────────────────────

@router.callback_query(F.data == "session_list")
async def cb_session_list(callback: CallbackQuery, staff: Staff | None = None):
    if staff is None or staff.role not in _ADMIN_ROLES:
        await callback.answer("⛔ Нет прав", show_alert=True)
        return
    async with async_session_factory() as session:
        sessions = await get_all_sessions(session)

    if not sessions:
        await callback.message.edit_text(
            "📋 <b>Смены</b>\n\nСмен пока нет.",
            reply_markup=sessions_menu(),
            parse_mode="HTML",
        )
        await callback.answer()
        return

    lines = ["📋 <b>Смены</b>\n"]
    for s in sessions:
        active_mark = " ✅ активная" if s.is_active else ""
        lines.append(
            f"• <b>{s.name}</b>{active_mark}\n"
            f"  {s.start_date.strftime(_DATE_FMT)} — {s.end_date.strftime(_DATE_FMT)}"
        )
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
    rows = []
    for s in sessions:
        rows.append([InlineKeyboardButton(
            text=f"{'✅ ' if s.is_active else ''}{s.name}",
            callback_data=f"session_view:{s.id}",
        )])
    rows.append([InlineKeyboardButton(text="➕ Новая смена", callback_data="session_new")])
    kb = InlineKeyboardMarkup(inline_keyboard=rows)

    await callback.message.edit_text("\n".join(lines), reply_markup=kb, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("session_view:"))
async def cb_session_view(callback: CallbackQuery, staff: Staff | None = None):
    if staff is None or staff.role not in _ADMIN_ROLES:
        await callback.answer("⛔ Нет прав", show_alert=True)
        return
    session_id = int(callback.data.split(":")[1])
    async with async_session_factory() as session:
        s = await get_session_by_id(session, session_id)
    if not s:
        await callback.answer("❌ Смена не найдена", show_alert=True)
        return

    active_mark = " ✅ <b>АКТИВНАЯ</b>" if s.is_active else ""
    text = (
        f"🏕 <b>{s.name}</b>{active_mark}\n"
        f"Начало: {s.start_date.strftime(_DATE_FMT)}\n"
        f"Конец: {s.end_date.strftime(_DATE_FMT)}"
    )
    await callback.message.edit_text(
        text,
        reply_markup=session_item_kb(s.id, s.is_active),
        parse_mode="HTML",
    )
    await callback.answer()


# ── Новая смена FSM ───────────────────────────────────────────────────────────

@router.callback_query(F.data == "session_new")
async def cb_session_new(callback: CallbackQuery, state: FSMContext, staff: Staff | None = None):
    if staff is None or staff.role not in _ADMIN_ROLES:
        await callback.answer("⛔ Нет прав", show_alert=True)
        return
    await callback.message.answer("🏕 <b>Новая смена</b>\n\nВведите название смены:", reply_markup=cancel_kb(), parse_mode="HTML")
    await state.set_state(SessionFSM.waiting_name)
    await callback.answer()


@router.message(SessionFSM.waiting_name)
async def fsm_session_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text.strip())
    await message.answer("Введите дату <b>начала</b> смены (ДД.ММ.ГГГГ):", reply_markup=cancel_kb(), parse_mode="HTML")
    await state.set_state(SessionFSM.waiting_start_date)


@router.message(SessionFSM.waiting_start_date)
async def fsm_session_start(message: Message, state: FSMContext):
    try:
        d = date(*reversed([int(x) for x in message.text.strip().split(".")]))
        await state.update_data(start_date=d)
        await message.answer("Введите дату <b>окончания</b> смены (ДД.ММ.ГГГГ):", reply_markup=cancel_kb(), parse_mode="HTML")
        await state.set_state(SessionFSM.waiting_end_date)
    except Exception:
        await message.answer("❌ Неверный формат. Введите дату в формате ДД.ММ.ГГГГ:")


@router.message(SessionFSM.waiting_end_date)
async def fsm_session_end(message: Message, state: FSMContext):
    try:
        d = date(*reversed([int(x) for x in message.text.strip().split(".")]))
    except Exception:
        await message.answer("❌ Неверный формат. Введите дату в формате ДД.ММ.ГГГГ:")
        return
    data = await state.get_data()
    if d < data["start_date"]:
        await message.answer("❌ Дата окончания не может быть раньше начала. Попробуйте снова:")
        return

    async with async_session_factory() as session:
        s = await create_session(session, data["name"], data["start_date"], d)

    await state.clear()
    await message.answer(
        f"✅ Смена <b>{s.name}</b> создана!\n"
        f"{s.start_date.strftime(_DATE_FMT)} — {d.strftime(_DATE_FMT)}",
        reply_markup=session_item_kb(s.id, s.is_active),
        parse_mode="HTML",
    )


# ── Активация смены ───────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("session_activate:"))
async def cb_session_activate(callback: CallbackQuery, staff: Staff | None = None):
    if staff is None or staff.role not in _ADMIN_ROLES:
        await callback.answer("⛔ Нет прав", show_alert=True)
        return
    session_id = int(callback.data.split(":")[1])
    async with async_session_factory() as session:
        s = await activate_session(session, session_id)
    if s:
        await callback.message.edit_text(
            f"✅ Смена <b>{s.name}</b> активирована.",
            reply_markup=session_item_kb(s.id, True),
            parse_mode="HTML",
        )
    await callback.answer()


# ── Расписание ────────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("schedule_view"))
async def cb_schedule_view(callback: CallbackQuery, staff: Staff | None = None):
    if staff is None:
        await callback.answer("⛔ Нет прав", show_alert=True)
        return
    parts = callback.data.split(":")
    session_id_arg = int(parts[1]) if len(parts) > 1 else None

    async with async_session_factory() as session:
        if session_id_arg:
            s = await get_session_by_id(session, session_id_arg)
        else:
            s = await get_active_session(session)
        if not s:
            await callback.answer("❌ Нет активной смены.", show_alert=True)
            return
        items = await get_schedule(session, s.id)

    text = _format_schedule(s.name, items)
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить в расписание", callback_data="schedule_add")],
    ])
    try:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except Exception:
        await callback.message.answer(text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.in_({"schedule_view", "schedule_done"}))
async def cb_schedule_view_shortcut(callback: CallbackQuery, staff: Staff | None = None):
    # Redirect plain "schedule_view" to schedule_view handler above
    callback.data = "schedule_view"
    await cb_schedule_view(callback, staff)


@router.callback_query(F.data == "schedule_add")
async def cb_schedule_add(callback: CallbackQuery, state: FSMContext, staff: Staff | None = None):
    if staff is None or staff.role not in _ADMIN_ROLES:
        await callback.answer("⛔ Нет прав", show_alert=True)
        return
    async with async_session_factory() as session:
        active = await get_active_session(session)
    if not active:
        await callback.answer("❌ Нет активной смены.", show_alert=True)
        return
    await state.update_data(session_id=active.id)
    await callback.message.answer(
        f"📅 Добавление в расписание смены <b>{active.name}</b>\n\nВыберите тип дня:",
        reply_markup=day_type_kb(),
        parse_mode="HTML",
    )
    await state.set_state(ScheduleAddFSM.waiting_day_type)
    await callback.answer()


@router.callback_query(ScheduleAddFSM.waiting_day_type, F.data.startswith("sched_day:"))
async def fsm_sched_day_type(callback: CallbackQuery, state: FSMContext):
    day_type = DayType(callback.data.split(":")[1])
    await state.update_data(day_type=day_type)
    await callback.message.edit_text(
        f"Тип дня: <b>{DAY_TYPE_LABELS[day_type]}</b>\n\nВведите <b>время</b> (ЧЧ:ММ):",
        reply_markup=cancel_kb(),
        parse_mode="HTML",
    )
    await state.set_state(ScheduleAddFSM.waiting_time)
    await callback.answer()


@router.message(ScheduleAddFSM.waiting_time)
async def fsm_sched_time(message: Message, state: FSMContext):
    from datetime import time as time_type
    try:
        h, m = message.text.strip().split(":")
        t = time_type(int(h), int(m))
        await state.update_data(time=t)
        await message.answer("Введите <b>название</b> мероприятия:", reply_markup=cancel_kb(), parse_mode="HTML")
        await state.set_state(ScheduleAddFSM.waiting_label)
    except Exception:
        await message.answer("❌ Неверный формат. Введите время в формате ЧЧ:ММ:")


@router.message(ScheduleAddFSM.waiting_label)
async def fsm_sched_label(message: Message, state: FSMContext):
    label = message.text.strip()
    data = await state.get_data()
    async with async_session_factory() as session:
        await add_schedule_item(session, data["session_id"], data["day_type"], data["time"], label)
    await state.clear()
    await message.answer(
        f"✅ Добавлено: <b>{data['time'].strftime('%H:%M')}</b> — {label}",
        reply_markup=schedule_add_more_kb(),
        parse_mode="HTML",
    )
