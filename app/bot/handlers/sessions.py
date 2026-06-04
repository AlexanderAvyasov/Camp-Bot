from datetime import datetime

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
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

_DATE_FMT = "%d.%m.%Y"
_TIME_FMT = "%H:%M"

_cancel_kb = InlineKeyboardMarkup(
    inline_keyboard=[[InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_fsm")]]
)

_day_type_kb = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text="📅 Будний", callback_data="sched_day:weekday"),
            InlineKeyboardButton(text="🌅 Выходной", callback_data="sched_day:weekend"),
        ],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_fsm")],
    ]
)

_home_kb = InlineKeyboardMarkup(
    inline_keyboard=[[InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]]
)


def _require_admin(staff: Staff | None) -> bool:
    return staff is not None and staff.role == StaffRole.admin


# ── /session_new ──────────────────────────────────────────────────────────────

@router.message(Command("session_new"))
async def cmd_session_new(message: Message, state: FSMContext, staff: Staff | None = None):
    if not _require_admin(staff):
        await message.answer("⛔ У вас нет прав для выполнения этой команды.")
        return
    await message.answer("🏕 Создание смены\n\nВведите <b>название</b> смены:", reply_markup=_cancel_kb, parse_mode="HTML")
    await state.set_state(SessionFSM.waiting_name)


@router.message(SessionFSM.waiting_name)
async def fsm_session_name(message: Message, state: FSMContext):
    name = message.text.strip()
    if len(name) < 2:
        await message.answer("❌ Название слишком короткое. Введите ещё раз:", reply_markup=_cancel_kb)
        return
    await state.update_data(name=name)
    await message.answer(
        "Введите <b>дату начала</b> смены (формат: ДД.ММ.ГГГГ):",
        reply_markup=_cancel_kb, parse_mode="HTML",
    )
    await state.set_state(SessionFSM.waiting_start_date)


@router.message(SessionFSM.waiting_start_date)
async def fsm_session_start_date(message: Message, state: FSMContext):
    try:
        dt = datetime.strptime(message.text.strip(), _DATE_FMT).date()
    except ValueError:
        await message.answer("❌ Неверный формат. Введите дату в формате ДД.ММ.ГГГГ:", reply_markup=_cancel_kb)
        return
    await state.update_data(start_date=dt.isoformat())
    await message.answer(
        "Введите <b>дату окончания</b> смены (формат: ДД.ММ.ГГГГ):",
        reply_markup=_cancel_kb, parse_mode="HTML",
    )
    await state.set_state(SessionFSM.waiting_end_date)


@router.message(SessionFSM.waiting_end_date)
async def fsm_session_end_date(message: Message, state: FSMContext, staff: Staff | None = None):
    try:
        end_dt = datetime.strptime(message.text.strip(), _DATE_FMT).date()
    except ValueError:
        await message.answer("❌ Неверный формат. Введите дату в формате ДД.ММ.ГГГГ:", reply_markup=_cancel_kb)
        return

    data = await state.get_data()
    from datetime import date
    start_dt = date.fromisoformat(data["start_date"])

    if end_dt <= start_dt:
        await message.answer("❌ Дата окончания должна быть позже даты начала. Введите ещё раз:", reply_markup=_cancel_kb)
        return

    async with async_session_factory() as session:
        obj = await create_session(session, data["name"], start_dt, end_dt)
        new_id = obj.id
        name = obj.name

    await state.clear()
    await message.answer(
        f"✅ Смена создана!\n\n"
        f"📋 <b>{name}</b>\n"
        f"🗓 {start_dt.strftime(_DATE_FMT)} — {end_dt.strftime(_DATE_FMT)}\n"
        f"ID: <code>{new_id}</code>\n\n"
        f"Активировать смену? /session_activate {new_id}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"✅ Сделать активной", callback_data=f"session_activate:{new_id}")],
            [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")],
        ]),
        parse_mode="HTML",
    )


# ── /session_list ─────────────────────────────────────────────────────────────

@router.message(Command("session_list"))
async def cmd_session_list(message: Message, staff: Staff | None = None):
    if not _require_admin(staff):
        await message.answer("⛔ У вас нет прав для выполнения этой команды.")
        return
    async with async_session_factory() as session:
        sessions = await get_all_sessions(session)
    if not sessions:
        await message.answer("📋 Смен пока нет.", reply_markup=_home_kb)
        return
    lines = ["📋 <b>Смены:</b>\n"]
    for s in sessions:
        status = "🟢 активна" if s.is_active else "⚪ не активна"
        lines.append(
            f"<b>{s.name}</b> (ID: {s.id})\n"
            f"  {s.start_date.strftime(_DATE_FMT)} — {s.end_date.strftime(_DATE_FMT)}  {status}"
        )
    await message.answer("\n\n".join(lines), reply_markup=_home_kb, parse_mode="HTML")


# ── /session_activate ─────────────────────────────────────────────────────────

@router.message(Command("session_activate"))
async def cmd_session_activate(message: Message, staff: Staff | None = None):
    if not _require_admin(staff):
        await message.answer("⛔ У вас нет прав для выполнения этой команды.")
        return
    args = message.text.split(maxsplit=1)
    if len(args) < 2 or not args[1].strip().isdigit():
        await message.answer("❌ Укажите ID смены.\nФормат: /session_activate <id>")
        return
    session_id = int(args[1].strip())
    async with async_session_factory() as session:
        obj = await activate_session(session, session_id)
    if not obj:
        await message.answer(f"❌ Смена с ID {session_id} не найдена.")
        return
    await message.answer(
        f"✅ Смена <b>{obj.name}</b> теперь активна.",
        reply_markup=_home_kb, parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("session_activate:"))
async def cb_session_activate(callback: CallbackQuery, staff: Staff | None = None):
    if not _require_admin(staff):
        await callback.answer("⛔ Нет прав", show_alert=True)
        return
    session_id = int(callback.data.split(":")[1])
    async with async_session_factory() as session:
        obj = await activate_session(session, session_id)
    if not obj:
        await callback.answer("❌ Смена не найдена", show_alert=True)
        return
    await callback.message.edit_text(
        f"✅ Смена <b>{obj.name}</b> теперь активна.\n"
        f"🗓 {obj.start_date.strftime(_DATE_FMT)} — {obj.end_date.strftime(_DATE_FMT)}",
        reply_markup=_home_kb, parse_mode="HTML",
    )
    await callback.answer()


# ── /schedule_add ─────────────────────────────────────────────────────────────

@router.message(Command("schedule_add"))
async def cmd_schedule_add(message: Message, state: FSMContext, staff: Staff | None = None):
    if not _require_admin(staff):
        await message.answer("⛔ У вас нет прав для выполнения этой команды.")
        return
    async with async_session_factory() as session:
        active = await get_active_session(session)
    if not active:
        await message.answer("❌ Нет активной смены. Сначала активируйте смену.", reply_markup=_home_kb)
        return
    await state.update_data(session_id=active.id)
    await message.answer(
        f"📅 Добавление в расписание смены <b>{active.name}</b>\n\nВыберите тип дня:",
        reply_markup=_day_type_kb, parse_mode="HTML",
    )
    await state.set_state(ScheduleAddFSM.waiting_day_type)


@router.callback_query(ScheduleAddFSM.waiting_day_type, F.data.startswith("sched_day:"))
async def fsm_sched_day_type(callback: CallbackQuery, state: FSMContext):
    day_type = callback.data.split(":")[1]
    await state.update_data(day_type=day_type)
    label = DAY_TYPE_LABELS[DayType(day_type)]
    await callback.message.edit_text(
        f"Тип дня: <b>{label}</b>\n\nВведите <b>время</b> (формат: ЧЧ:ММ):",
        reply_markup=_cancel_kb, parse_mode="HTML",
    )
    await state.set_state(ScheduleAddFSM.waiting_time)
    await callback.answer()


@router.message(ScheduleAddFSM.waiting_time)
async def fsm_sched_time(message: Message, state: FSMContext):
    try:
        t = datetime.strptime(message.text.strip(), _TIME_FMT).time()
    except ValueError:
        await message.answer("❌ Неверный формат. Введите время в формате ЧЧ:ММ:", reply_markup=_cancel_kb)
        return
    await state.update_data(time=t.strftime(_TIME_FMT))
    await message.answer("Введите <b>описание</b> мероприятия:", reply_markup=_cancel_kb, parse_mode="HTML")
    await state.set_state(ScheduleAddFSM.waiting_label)


@router.message(ScheduleAddFSM.waiting_label)
async def fsm_sched_label(message: Message, state: FSMContext):
    label = message.text.strip()
    if len(label) < 2:
        await message.answer("❌ Описание слишком короткое. Введите ещё раз:", reply_markup=_cancel_kb)
        return
    data = await state.get_data()
    t = datetime.strptime(data["time"], _TIME_FMT).time()
    day_type = DayType(data["day_type"])

    async with async_session_factory() as session:
        item = await add_schedule_item(session, data["session_id"], day_type, t, label)

    await state.clear()
    await message.answer(
        f"✅ Добавлено в расписание!\n\n"
        f"🕐 <b>{item.time.strftime(_TIME_FMT)}</b> — {item.label}\n"
        f"Тип дня: {DAY_TYPE_LABELS[item.day_type]}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➕ Добавить ещё", callback_data="schedule_add_more")],
            [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")],
        ]),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "schedule_add_more")
async def cb_schedule_add_more(callback: CallbackQuery, state: FSMContext, staff: Staff | None = None):
    if not _require_admin(staff):
        await callback.answer("⛔ Нет прав", show_alert=True)
        return
    async with async_session_factory() as session:
        active = await get_active_session(session)
    if not active:
        await callback.message.edit_text("❌ Нет активной смены.", reply_markup=_home_kb)
        await callback.answer()
        return
    await state.update_data(session_id=active.id)
    await callback.message.edit_text(
        f"📅 Добавление в расписание смены <b>{active.name}</b>\n\nВыберите тип дня:",
        reply_markup=_day_type_kb, parse_mode="HTML",
    )
    await state.set_state(ScheduleAddFSM.waiting_day_type)
    await callback.answer()


# ── /schedule_view ────────────────────────────────────────────────────────────

@router.message(Command("schedule_view"))
async def cmd_schedule_view(message: Message, staff: Staff | None = None):
    if not _require_admin(staff):
        await message.answer("⛔ У вас нет прав для выполнения этой команды.")
        return
    async with async_session_factory() as session:
        active = await get_active_session(session)
        if not active:
            await message.answer("❌ Нет активной смены.", reply_markup=_home_kb)
            return
        items = await get_schedule(session, active.id)

    await message.answer(_format_schedule(active.name, items), reply_markup=_home_kb, parse_mode="HTML")


def _format_schedule(session_name: str, items) -> str:
    if not items:
        return f"📅 Расписание смены <b>{session_name}</b>\n\nРасписание пустое."
    weekday = [i for i in items if i.day_type == DayType.weekday]
    weekend = [i for i in items if i.day_type == DayType.weekend]
    lines = [f"📅 Расписание смены <b>{session_name}</b>\n"]
    if weekday:
        lines.append("<b>📆 Будние дни:</b>")
        for i in weekday:
            lines.append(f"  {i.time.strftime(_TIME_FMT)} — {i.label}")
    if weekend:
        lines.append("\n<b>🌅 Выходные дни:</b>")
        for i in weekend:
            lines.append(f"  {i.time.strftime(_TIME_FMT)} — {i.label}")
    return "\n".join(lines)


# ── /schedule_copy ────────────────────────────────────────────────────────────

@router.message(Command("schedule_copy"))
async def cmd_schedule_copy(message: Message, staff: Staff | None = None):
    if not _require_admin(staff):
        await message.answer("⛔ У вас нет прав для выполнения этой команды.")
        return
    args = message.text.split(maxsplit=1)
    if len(args) < 2 or not args[1].strip().isdigit():
        await message.answer("❌ Укажите ID смены-источника.\nФормат: /schedule_copy <session_id>")
        return
    from_id = int(args[1].strip())
    async with async_session_factory() as session:
        active = await get_active_session(session)
        if not active:
            await message.answer("❌ Нет активной смены. Сначала активируйте смену.", reply_markup=_home_kb)
            return
        source = await get_session_by_id(session, from_id)
        if not source:
            await message.answer(f"❌ Смена с ID {from_id} не найдена.")
            return
        count = await copy_schedule(session, active.id, from_id)
    await message.answer(
        f"✅ Скопировано <b>{count}</b> записей расписания\n"
        f"из смены <b>{source.name}</b> в <b>{active.name}</b>.",
        reply_markup=_home_kb, parse_mode="HTML",
    )
