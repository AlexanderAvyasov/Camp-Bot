from datetime import datetime, timedelta, timezone

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from app.bot.keyboards import cancel_kb, calendar_menu
from app.bot.states import EventAddFSM, EventCopyFSM, EventEditFSM
from app.db.base import async_session_factory
from app.db.crud import (
    check_location_conflict,
    check_responsible_conflict,
    copy_event,
    create_event,
    create_event_reminders,
    delete_event,
    get_active_session,
    get_all_active_staff,
    get_event_by_id,
    get_events,
    get_staff_by_telegram_id,
    update_event,
)
from app.db.models import (
    EVENT_TYPE_LABELS,
    ROLE_LABELS,
    EventType,
    Staff,
    StaffRole,
)

router = Router(name="events")

_DT_FMT = "%d.%m.%Y %H:%M"
_D_FMT = "%d.%m.%Y"
_ADMIN_ROLES = {StaffRole.admin, StaffRole.senior_counselor}

_cancel_kb = InlineKeyboardMarkup(
    inline_keyboard=[[InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_fsm")]]
)
_skip_cancel_kb = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="⏭ Пропустить", callback_data="ev_skip")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_fsm")],
    ]
)
_event_type_kb = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text=lbl, callback_data=f"ev_type:{t.value}")]
        for t, lbl in EVENT_TYPE_LABELS.items()
    ] + [[InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_fsm")]]
)


def _event_text(event) -> str:
    type_label = EVENT_TYPE_LABELS.get(event.type, event.type)
    responsible = event.responsible.full_name if event.responsible else "—"
    location = event.location or "—"
    members_count = len(event.members)
    return (
        f"📅 <b>{event.title}</b> (ID: {event.id})\n"
        f"Тип: {type_label}\n"
        f"Место: {location}\n"
        f"Ответственный: {responsible}\n"
        f"Участников: {members_count}\n"
        f"🕐 {event.start_time.strftime(_DT_FMT)} — {event.end_time.strftime('%H:%M')}"
    )


def _format_events_list(events: list, header: str) -> str:
    if not events:
        return f"{header}\n\nМероприятий нет."
    lines = [f"{header}\n"]
    current_date = None
    for ev in events:
        ev_date = ev.start_time.date()
        if ev_date != current_date:
            current_date = ev_date
            lines.append(f"\n<b>{ev_date.strftime('%d.%m.%Y')}</b>")
        type_label = EVENT_TYPE_LABELS.get(ev.type, ev.type)
        location = f" | {ev.location}" if ev.location else ""
        lines.append(
            f"  {ev.start_time.strftime('%H:%M')}–{ev.end_time.strftime('%H:%M')} "
            f"<b>{ev.title}</b>{location} — {type_label}"
        )
    return "\n".join(lines)


def _event_list_kb(events: list, is_admin: bool) -> InlineKeyboardMarkup:
    rows = []
    for ev in events:
        rows.append([InlineKeyboardButton(
            text=f"📅 {ev.start_time.strftime('%H:%M')} {ev.title}",
            callback_data=f"event_view:{ev.id}",
        )])
    nav = [
        InlineKeyboardButton(text="📅 Сегодня", callback_data="cal:today"),
        InlineKeyboardButton(text="📆 Неделя", callback_data="cal:week"),
    ]
    rows.append(nav)
    if is_admin:
        rows.append([InlineKeyboardButton(text="➕ Новое мероприятие", callback_data="event_add")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ── Просмотр календаря ────────────────────────────────────────────────────────

@router.callback_query(F.data == "cal:today")
async def cb_cal_today(callback: CallbackQuery, staff: Staff | None = None):
    now = datetime.now(tz=timezone.utc)
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    day_end = day_start + timedelta(days=1)
    async with async_session_factory() as session:
        events = await get_events(session, date_from=day_start, date_to=day_end)
    is_admin = staff is not None and staff.role in _ADMIN_ROLES
    text = _format_events_list(events, f"📅 <b>Сегодня, {now.strftime('%d.%m.%Y')}</b>")
    await callback.message.edit_text(text, reply_markup=_event_list_kb(events, is_admin), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "cal:week")
async def cb_cal_week(callback: CallbackQuery, staff: Staff | None = None):
    now = datetime.now(tz=timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    week_end = now + timedelta(days=7)
    async with async_session_factory() as session:
        events = await get_events(session, date_from=now, date_to=week_end)
    is_admin = staff is not None and staff.role in _ADMIN_ROLES
    text = _format_events_list(events, "📆 <b>Ближайшие 7 дней</b>")
    await callback.message.edit_text(text, reply_markup=_event_list_kb(events, is_admin), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "cal:my")
async def cb_cal_my(callback: CallbackQuery, staff: Staff | None = None):
    if staff is None:
        await callback.answer()
        return
    now = datetime.now(tz=timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    async with async_session_factory() as session:
        events = await get_events(session, date_from=now, staff_id=staff.id)
    text = _format_events_list(events, f"👤 <b>Мой график — {staff.full_name}</b>")
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="📅 Сегодня", callback_data="cal:today"),
        InlineKeyboardButton(text="📆 Неделя", callback_data="cal:week"),
    ]])
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()


# ── Просмотр мероприятия ──────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("event_view:"))
async def cb_event_view(callback: CallbackQuery, staff: Staff | None = None):
    event_id = int(callback.data.split(":")[1])
    async with async_session_factory() as session:
        event = await get_event_by_id(session, event_id)
    if not event:
        await callback.answer("❌ Мероприятие не найдено", show_alert=True)
        return
    is_admin = staff is not None and staff.role in _ADMIN_ROLES
    rows = []
    if is_admin:
        rows.append([
            InlineKeyboardButton(text="✏️ Редактировать", callback_data=f"event_edit_start:{event_id}"),
            InlineKeyboardButton(text="🗑 Удалить", callback_data=f"event_del_confirm:{event_id}"),
        ])
        rows.append([InlineKeyboardButton(text="📋 Копировать", callback_data=f"event_copy_start:{event_id}")])
    rows.append([InlineKeyboardButton(text="◀️ Назад", callback_data="cal:today")])
    kb = InlineKeyboardMarkup(inline_keyboard=rows)
    try:
        await callback.message.edit_text(_event_text(event), reply_markup=kb, parse_mode="HTML")
    except Exception:
        await callback.message.answer(_event_text(event), reply_markup=kb, parse_mode="HTML")
    await callback.answer()


# ── Добавить мероприятие FSM ──────────────────────────────────────────────────

@router.callback_query(F.data == "event_add")
async def cb_event_add(callback: CallbackQuery, state: FSMContext, staff: Staff | None = None):
    if staff is None or staff.role not in _ADMIN_ROLES:
        await callback.answer("⛔ Нет прав", show_alert=True)
        return
    await callback.message.answer(
        "➕ <b>Новое мероприятие</b>\n\nВведите <b>название</b>:",
        reply_markup=_cancel_kb, parse_mode="HTML",
    )
    await state.set_state(EventAddFSM.waiting_title)
    await callback.answer()


@router.message(EventAddFSM.waiting_title)
async def fsm_ev_title(message: Message, state: FSMContext):
    await state.update_data(title=message.text.strip())
    await message.answer("Выберите <b>тип</b> мероприятия:", reply_markup=_event_type_kb, parse_mode="HTML")
    await state.set_state(EventAddFSM.waiting_type)


@router.callback_query(EventAddFSM.waiting_type, F.data.startswith("ev_type:"))
async def fsm_ev_type(callback: CallbackQuery, state: FSMContext):
    ev_type = EventType(callback.data.split(":")[1])
    await state.update_data(ev_type=ev_type.value)
    await callback.message.edit_text(
        f"Тип: {EVENT_TYPE_LABELS[ev_type]}\n\nВведите <b>место проведения</b> (или пропустите):",
        reply_markup=_skip_cancel_kb, parse_mode="HTML",
    )
    await state.set_state(EventAddFSM.waiting_location)
    await callback.answer()


@router.message(EventAddFSM.waiting_location)
async def fsm_ev_location(message: Message, state: FSMContext):
    await state.update_data(location=message.text.strip())
    await message.answer(
        "Введите <b>Telegram ID ответственного</b> (или пропустите):",
        reply_markup=_skip_cancel_kb, parse_mode="HTML",
    )
    await state.set_state(EventAddFSM.waiting_responsible)


@router.callback_query(EventAddFSM.waiting_location, F.data == "ev_skip")
async def fsm_ev_location_skip(callback: CallbackQuery, state: FSMContext):
    await state.update_data(location=None)
    await callback.message.edit_text(
        "Введите <b>Telegram ID ответственного</b> (или пропустите):",
        reply_markup=_skip_cancel_kb, parse_mode="HTML",
    )
    await state.set_state(EventAddFSM.waiting_responsible)
    await callback.answer()


@router.message(EventAddFSM.waiting_responsible)
async def fsm_ev_responsible(message: Message, state: FSMContext):
    text = message.text.strip()
    if not text.isdigit():
        await message.answer("❌ Введите числовой Telegram ID:", reply_markup=_skip_cancel_kb)
        return
    async with async_session_factory() as session:
        person = await get_staff_by_telegram_id(session, int(text))
    if not person:
        await message.answer("❌ Сотрудник не найден:", reply_markup=_skip_cancel_kb)
        return
    await state.update_data(responsible_id=person.id, responsible_name=person.full_name)
    await _ask_members(message, state)


@router.callback_query(EventAddFSM.waiting_responsible, F.data == "ev_skip")
async def fsm_ev_responsible_skip(callback: CallbackQuery, state: FSMContext):
    await state.update_data(responsible_id=None)
    await _ask_members(callback.message, state, edit=True)
    await callback.answer()


async def _ask_members(message: Message, state: FSMContext, edit: bool = False):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"👥 {lbl}", callback_data=f"ev_members_role:{r.value}")]
        for r, lbl in ROLE_LABELS.items()
    ] + [
        [InlineKeyboardButton(text="✏️ Вручную (ID через запятую)", callback_data="ev_members_manual")],
        [
            InlineKeyboardButton(text="⏭ Без участников", callback_data="ev_skip"),
            InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_fsm"),
        ],
    ])
    text = "Добавить <b>участников</b>: выберите роль или введите вручную:"
    if edit:
        await message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    else:
        await message.answer(text, reply_markup=kb, parse_mode="HTML")
    await state.set_state(EventAddFSM.waiting_members)


@router.callback_query(EventAddFSM.waiting_members, F.data.startswith("ev_members_role:"))
async def fsm_ev_members_role(callback: CallbackQuery, state: FSMContext):
    role = StaffRole(callback.data.split(":")[1])
    async with async_session_factory() as session:
        all_staff = await get_all_active_staff(session)
    ids = [s.id for s in all_staff if s.role == role]
    await state.update_data(member_ids=ids)
    await callback.message.edit_text(
        f"Участники: все «{ROLE_LABELS[role]}» ({len(ids)} чел.)\n\nВведите <b>дату и время начала</b> (ДД.ММ.ГГГГ ЧЧ:ММ):",
        reply_markup=_cancel_kb, parse_mode="HTML",
    )
    await state.set_state(EventAddFSM.waiting_start)
    await callback.answer()


@router.callback_query(EventAddFSM.waiting_members, F.data == "ev_members_manual")
async def fsm_ev_members_manual_prompt(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "Введите <b>Telegram ID</b> участников через запятую:",
        reply_markup=_cancel_kb, parse_mode="HTML",
    )
    await state.update_data(_members_manual=True)
    await callback.answer()


@router.message(EventAddFSM.waiting_members)
async def fsm_ev_members_text(message: Message, state: FSMContext):
    data = await state.get_data()
    if not data.get("_members_manual"):
        return
    parts = [p.strip() for p in message.text.split(",") if p.strip().isdigit()]
    ids = []
    async with async_session_factory() as session:
        for tg_id in parts:
            person = await get_staff_by_telegram_id(session, int(tg_id))
            if person:
                ids.append(person.id)
    await state.update_data(member_ids=ids, _members_manual=False)
    await message.answer(
        f"Участников найдено: {len(ids)}\n\nВведите <b>дату и время начала</b> (ДД.ММ.ГГГГ ЧЧ:ММ):",
        reply_markup=_cancel_kb, parse_mode="HTML",
    )
    await state.set_state(EventAddFSM.waiting_start)


@router.callback_query(EventAddFSM.waiting_members, F.data == "ev_skip")
async def fsm_ev_members_skip(callback: CallbackQuery, state: FSMContext):
    await state.update_data(member_ids=[])
    await callback.message.edit_text(
        "Введите <b>дату и время начала</b> (ДД.ММ.ГГГГ ЧЧ:ММ):",
        reply_markup=_cancel_kb, parse_mode="HTML",
    )
    await state.set_state(EventAddFSM.waiting_start)
    await callback.answer()


@router.message(EventAddFSM.waiting_start)
async def fsm_ev_start(message: Message, state: FSMContext):
    try:
        dt = datetime.strptime(message.text.strip(), _DT_FMT).replace(tzinfo=timezone.utc)
    except ValueError:
        await message.answer("❌ Формат: ДД.ММ.ГГГГ ЧЧ:ММ", reply_markup=_cancel_kb)
        return
    await state.update_data(start_time=dt.isoformat())
    await message.answer(
        "Введите <b>дату и время окончания</b> (ДД.ММ.ГГГГ ЧЧ:ММ):",
        reply_markup=_cancel_kb, parse_mode="HTML",
    )
    await state.set_state(EventAddFSM.waiting_end)


@router.message(EventAddFSM.waiting_end)
async def fsm_ev_end(message: Message, state: FSMContext, staff: Staff | None = None):
    try:
        dt = datetime.strptime(message.text.strip(), _DT_FMT).replace(tzinfo=timezone.utc)
    except ValueError:
        await message.answer("❌ Формат: ДД.ММ.ГГГГ ЧЧ:ММ", reply_markup=_cancel_kb)
        return
    data = await state.get_data()
    start = datetime.fromisoformat(data["start_time"])
    if dt <= start:
        await message.answer("❌ Время окончания должно быть позже начала:", reply_markup=_cancel_kb)
        return
    await state.update_data(end_time=dt.isoformat())

    warnings = []
    async with async_session_factory() as session:
        active = await get_active_session(session)
        sid = active.id if active else None
        if data.get("location"):
            conflicts = await check_location_conflict(session, data["location"], start, dt, sid)
            if conflicts:
                warnings.append(f"⚠️ Место «{data['location']}» занято: {', '.join(e.title for e in conflicts)}")
        if data.get("responsible_id"):
            rconflicts = await check_responsible_conflict(session, data["responsible_id"], start, dt)
            if rconflicts:
                warnings.append(f"⚠️ Ответственный занят: {', '.join(e.title for e in rconflicts)}")

    ev_type = EventType(data["ev_type"])
    confirm_text = (
        f"📋 <b>Подтвердите создание мероприятия:</b>\n\n"
        f"<b>{data['title']}</b>\n"
        f"Тип: {EVENT_TYPE_LABELS[ev_type]}\n"
        f"Место: {data.get('location') or '—'}\n"
        f"Ответственный: {data.get('responsible_name') or '—'}\n"
        f"Участников: {len(data.get('member_ids') or [])}\n"
        f"🕐 {start.strftime(_DT_FMT)} — {dt.strftime('%H:%M')}"
    )
    if warnings:
        confirm_text += "\n\n" + "\n".join(warnings)

    await message.answer(
        confirm_text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="✅ Создать", callback_data="ev_confirm"),
            InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_fsm"),
        ]]),
        parse_mode="HTML",
    )
    await state.set_state(EventAddFSM.confirm)


@router.callback_query(EventAddFSM.confirm, F.data == "ev_confirm")
async def fsm_ev_confirm(callback: CallbackQuery, state: FSMContext, staff: Staff | None = None):
    data = await state.get_data()
    await state.clear()

    start = datetime.fromisoformat(data["start_time"])
    end = datetime.fromisoformat(data["end_time"])

    async with async_session_factory() as session:
        active = await get_active_session(session)
        event = await create_event(
            session,
            title=data["title"],
            event_type=EventType(data["ev_type"]),
            start_time=start, end_time=end,
            location=data.get("location"),
            responsible_id=data.get("responsible_id"),
            session_id=active.id if active else None,
            member_ids=data.get("member_ids") or [],
        )
        member_staff_ids = [m.staff_id for m in event.members]
        await create_event_reminders(session, event.id, member_staff_ids, start)
        member_tg_ids = [m.staff.telegram_id for m in event.members if m.staff]

    await callback.message.edit_text(f"✅ Мероприятие создано!\n\n{_event_text(event)}", parse_mode="HTML")
    await callback.answer()

    for tg_id in member_tg_ids:
        try:
            await callback.bot.send_message(tg_id, f"📅 Вы добавлены в мероприятие!\n\n{_event_text(event)}", parse_mode="HTML")
        except Exception:
            pass


# ── Редактирование мероприятия ────────────────────────────────────────────────

@router.callback_query(F.data.startswith("event_edit_start:"))
async def cb_event_edit_start(callback: CallbackQuery, state: FSMContext, staff: Staff | None = None):
    if staff is None or staff.role not in _ADMIN_ROLES:
        await callback.answer("⛔ Нет прав", show_alert=True)
        return
    event_id = int(callback.data.split(":")[1])
    async with async_session_factory() as session:
        event = await get_event_by_id(session, event_id)
    if not event:
        await callback.answer("❌ Мероприятие не найдено", show_alert=True)
        return
    await state.update_data(event_id=event_id)
    await callback.message.edit_text(
        f"✏️ <b>{event.title}</b>\n\nЧто изменить?",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📝 Название", callback_data="ev_edit:title"),
             InlineKeyboardButton(text="📍 Место", callback_data="ev_edit:location")],
            [InlineKeyboardButton(text="🕐 Начало", callback_data="ev_edit:start"),
             InlineKeyboardButton(text="🕑 Конец", callback_data="ev_edit:end")],
            [InlineKeyboardButton(text="👤 Ответственный", callback_data="ev_edit:responsible")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_fsm")],
        ]),
        parse_mode="HTML",
    )
    await state.set_state(EventEditFSM.waiting_field)
    await callback.answer()


@router.callback_query(EventEditFSM.waiting_field, F.data.startswith("ev_edit:"))
async def fsm_ev_edit_field(callback: CallbackQuery, state: FSMContext):
    field = callback.data.split(":")[1]
    await state.update_data(edit_field=field)
    prompts = {
        "title": "Введите новое <b>название</b>:",
        "location": "Введите новое <b>место</b>:",
        "start": "Введите новое <b>время начала</b> (ДД.ММ.ГГГГ ЧЧ:ММ):",
        "end": "Введите новое <b>время окончания</b> (ДД.ММ.ГГГГ ЧЧ:ММ):",
        "responsible": "Введите <b>Telegram ID</b> нового ответственного:",
    }
    await callback.message.edit_text(prompts[field], reply_markup=_cancel_kb, parse_mode="HTML")
    await state.set_state(EventEditFSM.waiting_value)
    await callback.answer()


@router.message(EventEditFSM.waiting_value)
async def fsm_ev_edit_value(message: Message, state: FSMContext):
    data = await state.get_data()
    field = data["edit_field"]
    event_id = data["event_id"]
    value = message.text.strip()
    kwargs = {}

    if field == "title":
        kwargs["title"] = value
    elif field == "location":
        kwargs["location"] = value
    elif field in ("start", "end"):
        try:
            dt = datetime.strptime(value, _DT_FMT).replace(tzinfo=timezone.utc)
        except ValueError:
            await message.answer("❌ Формат: ДД.ММ.ГГГГ ЧЧ:ММ", reply_markup=_cancel_kb)
            return
        kwargs["start_time" if field == "start" else "end_time"] = dt
    elif field == "responsible":
        if not value.isdigit():
            await message.answer("❌ Введите числовой Telegram ID:", reply_markup=_cancel_kb)
            return
        async with async_session_factory() as session:
            person = await get_staff_by_telegram_id(session, int(value))
        if not person:
            await message.answer("❌ Сотрудник не найден:", reply_markup=_cancel_kb)
            return
        kwargs["responsible_id"] = person.id

    async with async_session_factory() as session:
        event = await update_event(session, event_id, **kwargs)

    await state.clear()
    await message.answer(f"✅ Обновлено!\n\n{_event_text(event)}", parse_mode="HTML")


# ── Удаление мероприятия ──────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("event_del_confirm:"))
async def cb_event_del_confirm(callback: CallbackQuery, staff: Staff | None = None):
    if staff is None or staff.role not in _ADMIN_ROLES:
        await callback.answer("⛔ Нет прав", show_alert=True)
        return
    event_id = int(callback.data.split(":")[1])
    async with async_session_factory() as session:
        event = await get_event_by_id(session, event_id)
    if not event:
        await callback.answer("❌ Не найдено", show_alert=True)
        return
    await callback.message.edit_text(
        f"❗ Удалить мероприятие <b>{event.title}</b>?",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="✅ Да", callback_data=f"event_del:{event_id}"),
            InlineKeyboardButton(text="❌ Нет", callback_data=f"event_view:{event_id}"),
        ]]),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("event_del:"))
async def cb_event_del(callback: CallbackQuery, staff: Staff | None = None):
    if staff is None or staff.role not in _ADMIN_ROLES:
        await callback.answer("⛔ Нет прав", show_alert=True)
        return
    event_id = int(callback.data.split(":")[1])
    async with async_session_factory() as session:
        ok = await delete_event(session, event_id)
    if ok:
        await callback.message.edit_text("✅ Мероприятие удалено.", reply_markup=calendar_menu())
    else:
        await callback.message.edit_text("❌ Мероприятие не найдено.")
    await callback.answer()


# ── Копирование мероприятия ───────────────────────────────────────────────────

@router.callback_query(F.data.startswith("event_copy_start:"))
async def cb_event_copy_start(callback: CallbackQuery, state: FSMContext, staff: Staff | None = None):
    if staff is None or staff.role not in _ADMIN_ROLES:
        await callback.answer("⛔ Нет прав", show_alert=True)
        return
    event_id = int(callback.data.split(":")[1])
    await state.update_data(copy_event_id=event_id)
    await callback.message.answer(
        "📋 Введите дату для копии (ДД.ММ.ГГГГ):",
        reply_markup=_cancel_kb,
    )
    await state.set_state(EventCopyFSM.waiting_date)
    await callback.answer()


@router.message(EventCopyFSM.waiting_date)
async def fsm_event_copy_date(message: Message, state: FSMContext):
    try:
        from datetime import date as date_type
        new_date = datetime.strptime(message.text.strip(), _D_FMT).date()
    except ValueError:
        await message.answer("❌ Формат: ДД.ММ.ГГГГ", reply_markup=_cancel_kb)
        return
    data = await state.get_data()
    event_id = data["copy_event_id"]
    async with async_session_factory() as session:
        new_event = await copy_event(session, event_id, new_date)
    await state.clear()
    if not new_event:
        await message.answer("❌ Мероприятие не найдено.")
        return
    await message.answer(f"✅ Скопировано!\n\n{_event_text(new_event)}", parse_mode="HTML")


# ── Экстренное оповещение ─────────────────────────────────────────────────────

@router.message(Command("day_mode_emergency"))
async def cmd_day_mode_emergency(message: Message, staff: Staff | None = None):
    if staff is None or staff.role not in _ADMIN_ROLES:
        await message.answer("⛔ У вас нет прав.")
        return
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("❌ Формат: /day_mode_emergency <текст>")
        return
    broadcast_text = f"🚨 <b>ИЗМЕНЕНИЕ РЕЖИМА ДНЯ</b>\n\n{args[1]}"
    async with async_session_factory() as session:
        all_staff = await get_all_active_staff(session)
    sent = 0
    for s in all_staff:
        if s.telegram_id == staff.telegram_id:
            continue
        try:
            await message.bot.send_message(s.telegram_id, broadcast_text, parse_mode="HTML")
            sent += 1
        except Exception:
            pass
    await message.answer(f"✅ Оповещение отправлено {sent} сотрудникам.")
