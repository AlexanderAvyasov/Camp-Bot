"""Обработчики кнопок главного меню (reply keyboard)."""
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

from app.bot.keyboards import (
    analytics_submenu_kb,
    announcements_submenu_kb,
    calendar_submenu_kb,
    children_submenu_kb,
    checklists_submenu_kb,
    duties_submenu_kb,
    management_submenu_kb,
    tasks_submenu_kb,
    task_menu_filter_kb,
    back_btn,
)
from app.bot.states import IncidentFSM, AnnounceFSM
from app.db.base import async_session_factory
from app.db.crud import (
    get_active_session,
    get_all_active_staff,
    get_announcements,
    get_circles,
    get_duties_by_staff,
    get_events,
    get_tasks_for_staff,
    get_all_tasks,
    mark_announcement_read,
    get_circle_members,
)
from app.db.models import Staff, StaffRole, STATUS_LABELS, PRIORITY_LABELS, TaskStatus, TaskPriority

router = Router(name="menu")
_ADMIN_ROLES = {StaffRole.admin, StaffRole.senior_counselor}

_PRIORITY_EMOJI = {
    TaskPriority.high: "🔴",
    TaskPriority.medium: "🟡",
    TaskPriority.low: "🟢",
}

_STATUS_EMOJI = {
    TaskStatus.new: "🆕",
    TaskStatus.accepted: "👀",
    TaskStatus.in_progress: "🔨",
    TaskStatus.done: "✅",
    TaskStatus.overdue: "🔴",
}

PAGE_SIZE = 5


def _task_line(task) -> str:
    pe = _PRIORITY_EMOJI.get(task.priority, "⚪")
    se = STATUS_LABELS.get(task.status, str(task.status))
    dl = task.deadline.strftime("%d.%m %H:%M") if task.deadline else "—"
    return f"{pe} #{task.id} {task.title}\n⏰ {dl} • {se}"


# ── ЗАДАЧИ ───────────────────────────────────────────────────────────────────

_TASKS_BUTTONS = {"📋 Задачи", "📋 Мои задачи"}

@router.message(F.text.in_(_TASKS_BUTTONS))
async def menu_tasks(message: Message, staff: Staff | None = None):
    if staff is None:
        return
    is_admin = staff.role in _ADMIN_ROLES
    await message.answer(
        "<b>📋 Задачи</b>",
        reply_markup=tasks_submenu_kb(is_admin),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("menu_my_tasks:"))
async def cb_menu_my_tasks(callback: CallbackQuery, staff: Staff | None = None):
    if staff is None:
        return await callback.answer()
    page = int(callback.data.split(":")[1])
    async with async_session_factory() as session:
        sess = await get_active_session(session)
        tasks = await get_tasks_for_staff(session, staff.id, session_id=sess.id if sess else None)

    start = page * PAGE_SIZE
    page_tasks = tasks[start: start + PAGE_SIZE]
    total_pages = max(1, (len(tasks) + PAGE_SIZE - 1) // PAGE_SIZE)

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    if not page_tasks:
        text = "📭 Здесь пока пусто"
        kb = InlineKeyboardMarkup(inline_keyboard=[])
    else:
        lines = []
        for t in page_tasks:
            lines.append(_task_line(t))
        text = "<b>📋 Мои задачи</b>\n─────────────────\n" + "\n\n".join(lines)
        rows = []
        nav = []
        if page > 0:
            nav.append(InlineKeyboardButton(text="← Пред.", callback_data=f"menu_my_tasks:{page-1}"))
        nav.append(InlineKeyboardButton(text=f"{page+1}/{total_pages}", callback_data="noop"))
        if page < total_pages - 1:
            nav.append(InlineKeyboardButton(text="След. →", callback_data=f"menu_my_tasks:{page+1}"))
        if nav:
            rows.append(nav)
        kb = InlineKeyboardMarkup(inline_keyboard=rows)

    try:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except Exception:
        await callback.message.answer(text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("menu_all_tasks:"))
async def cb_menu_all_tasks(callback: CallbackQuery, staff: Staff | None = None):
    if staff is None or staff.role not in _ADMIN_ROLES:
        return await callback.answer("⛔ Нет прав", show_alert=True)
    parts = callback.data.split(":")
    filter_key = parts[1]
    page = int(parts[2])

    status_map = {
        "new": TaskStatus.new,
        "in_progress": TaskStatus.in_progress,
        "overdue": TaskStatus.overdue,
    }

    async with async_session_factory() as session:
        sess = await get_active_session(session)
        tasks = await get_all_tasks(session, session_id=sess.id if sess else None)

    if filter_key in status_map:
        tasks = [t for t in tasks if t.status == status_map[filter_key]]

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    start = page * PAGE_SIZE
    page_tasks = tasks[start: start + PAGE_SIZE]
    total_pages = max(1, (len(tasks) + PAGE_SIZE - 1) // PAGE_SIZE)

    filter_kb = task_menu_filter_kb(filter_key)
    rows = list(filter_kb.inline_keyboard)
    if page_tasks:
        lines = [_task_line(t) for t in page_tasks]
        text = f"<b>📊 Все задачи</b> [{len(tasks)}]\n─────────────────\n" + "\n\n".join(lines)
        nav = []
        if page > 0:
            nav.append(InlineKeyboardButton(text="← Пред.", callback_data=f"menu_all_tasks:{filter_key}:{page-1}"))
        nav.append(InlineKeyboardButton(text=f"{page+1}/{total_pages}", callback_data="noop"))
        if page < total_pages - 1:
            nav.append(InlineKeyboardButton(text="След. →", callback_data=f"menu_all_tasks:{filter_key}:{page+1}"))
        if nav:
            rows.append(nav)
    else:
        text = "<b>📊 Все задачи</b>\n─────────────────\n📭 Здесь пока пусто"

    kb = InlineKeyboardMarkup(inline_keyboard=rows)
    try:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except Exception:
        await callback.message.answer(text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()


# ── КАЛЕНДАРЬ / РАСПИСАНИЕ ───────────────────────────────────────────────────

_CALENDAR_BUTTONS = {"📅 Календарь", "📅 Расписание"}

@router.message(F.text.in_(_CALENDAR_BUTTONS))
async def menu_calendar(message: Message, staff: Staff | None = None):
    if staff is None:
        return
    is_admin = staff.role in _ADMIN_ROLES
    await message.answer(
        "<b>📅 Календарь</b>",
        reply_markup=calendar_submenu_kb(is_admin),
        parse_mode="HTML",
    )


# ── ДЕТИ ─────────────────────────────────────────────────────────────────────

_CHILDREN_BUTTONS = {"👦 Дети", "👦 Мой отряд"}

@router.message(F.text.in_(_CHILDREN_BUTTONS))
async def menu_children(message: Message, staff: Staff | None = None):
    if staff is None:
        return
    has_squad = staff.role in {StaffRole.counselor, StaffRole.educator}
    await message.answer(
        "<b>👦 Дети</b>",
        reply_markup=children_submenu_kb(has_squad=has_squad),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "ch_my_squad")
async def cb_my_squad(callback: CallbackQuery, staff: Staff | None = None):
    if staff is None:
        return await callback.answer()
    from app.db.crud import search_children
    from aiogram.types import InlineKeyboardMarkup
    if not staff.squad_id:
        await callback.message.edit_text("❌ Вы не привязаны к отряду.", reply_markup=InlineKeyboardMarkup(inline_keyboard=[]))
        await callback.answer()
        return
    async with async_session_factory() as session:
        children, total = await search_children(session, squad_id=staff.squad_id, limit=50)
    if not children:
        await callback.message.edit_text("📭 В вашем отряде нет детей.", reply_markup=InlineKeyboardMarkup(inline_keyboard=[]))
        await callback.answer()
        return
    from aiogram.types import InlineKeyboardButton
    rows = [[InlineKeyboardButton(text=f"👦 {c.full_name}", callback_data=f"child_view:{c.id}")] for c in children]
    await callback.message.edit_text(
        f"👦 <b>Мой отряд</b> ({total} чел.):",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data == "ch_birthdays")
async def cb_birthdays(callback: CallbackQuery):
    from app.db.crud import get_birthdays_range
    from aiogram.types import InlineKeyboardMarkup
    async with async_session_factory() as session:
        pairs = await get_birthdays_range(session, 7)
    if not pairs:
        text = "📭 Именинников на ближайшую неделю нет."
    else:
        lines = ["<b>🎂 Именинники (7 дней):</b>\n"]
        for d, c in pairs:
            lines.append(f"🎂 {d.strftime('%d.%m')} — {c.full_name}")
        text = "\n".join(lines)
    from aiogram.types import InlineKeyboardMarkup
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=[]))
    await callback.answer()


# ── ИНЦИДЕНТ ─────────────────────────────────────────────────────────────────

@router.message(F.text == "🚨 Инцидент")
async def menu_incident(message: Message, state: FSMContext, staff: Staff | None = None):
    if staff is None:
        return
    from app.bot.handlers.incidents import _incident_types_kb
    await message.answer(
        "🚨 <b>Новый инцидент</b>\n\nВыберите тип:",
        reply_markup=_incident_types_kb(),
        parse_mode="HTML",
    )
    await state.set_state(IncidentFSM.waiting_type)


# ── ДЕЖУРСТВО ────────────────────────────────────────────────────────────────

@router.message(F.text == "🔄 Дежурство")
async def menu_duties(message: Message, staff: Staff | None = None):
    if staff is None:
        return
    await message.answer(
        "<b>🔄 Дежурство</b>",
        reply_markup=duties_submenu_kb(),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "duty_my")
async def cb_duty_my(callback: CallbackQuery, staff: Staff | None = None):
    if staff is None:
        return await callback.answer()
    async with async_session_factory() as session:
        duties = await get_duties_by_staff(session, staff.id)
    from app.db.models import DUTY_TYPE_LABELS
    from aiogram.types import InlineKeyboardMarkup
    if not duties:
        text = "📭 Предстоящих дежурств нет."
    else:
        lines = ["<b>📋 Мои дежурства:</b>\n"]
        for d in duties[:10]:
            emoji = {"scheduled": "📅", "active": "🔄", "completed": "✅"}.get(d.status.value, "?")
            lines.append(f"{emoji} {DUTY_TYPE_LABELS[d.type]} — {d.date.strftime('%d.%m')} [ID:{d.id}]")
        text = "\n".join(lines)
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=[]))
    await callback.answer()


@router.callback_query(F.data == "duty_alarm_now")
async def cb_duty_alarm(callback: CallbackQuery, staff: Staff | None = None):
    if staff is None:
        return await callback.answer()
    from app.bot.bot import get_bot
    bot = get_bot()
    async with async_session_factory() as session:
        all_staff = await get_all_active_staff(session)
    sent = 0
    for s in all_staff:
        if s.role in _ADMIN_ROLES:
            try:
                await bot.send_message(
                    s.telegram_id,
                    f"🚨 <b>ТРЕВОГА НА ДЕЖУРСТВЕ!</b>\n\nСообщение от: {staff.full_name}",
                    parse_mode="HTML",
                )
                sent += 1
            except Exception:
                pass
    await callback.answer(f"🚨 Тревога отправлена {sent} администраторам.", show_alert=True)


@router.callback_query(F.data == "duty_complete")
async def cb_duty_complete(callback: CallbackQuery, staff: Staff | None = None):
    if staff is None:
        return await callback.answer()
    async with async_session_factory() as session:
        duties = await get_duties_by_staff(session, staff.id)
    active = [d for d in duties if d.status.value in ("scheduled", "active")]
    if not active:
        await callback.answer("📭 Нет активных дежурств.", show_alert=True)
        return
    duty = active[0]
    from app.db.crud import update_duty_status, duty_add_checkpoint
    from app.db.models import DutyStatus
    async with async_session_factory() as session:
        await update_duty_status(session, duty.id, DutyStatus.completed)
        await duty_add_checkpoint(session, duty.id, "Завершено")
    await callback.answer(f"✅ Дежурство #{duty.id} завершено.", show_alert=True)


# ── ЧЕК-ЛИСТЫ ────────────────────────────────────────────────────────────────

@router.message(F.text == "📝 Чек-лист")
async def menu_checklists(message: Message, staff: Staff | None = None):
    if staff is None:
        return
    await message.answer(
        "<b>📝 Чек-листы</b>",
        reply_markup=checklists_submenu_kb(),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("cl_start:"))
async def cb_cl_start(callback: CallbackQuery, staff: Staff | None = None):
    if staff is None:
        return await callback.answer()
    cl_type_val = callback.data.split(":")[1]
    from app.db.models import ChecklistType
    from app.db.crud import get_checklist_templates, start_checklist_run
    from app.bot.handlers.checklists import _run_kb
    cl_type = ChecklistType(cl_type_val)
    async with async_session_factory() as session:
        templates = await get_checklist_templates(session, type_=cl_type)
    if not templates:
        await callback.answer("❌ Нет шаблонов. Создайте: /checklist_add", show_alert=True)
        return
    tmpl = templates[0]
    async with async_session_factory() as session:
        run = await start_checklist_run(session, tmpl.id, staff.id)
    await callback.message.answer(
        f"📋 <b>{tmpl.title}</b>",
        reply_markup=_run_kb(run.id, run.results),
        parse_mode="HTML",
    )
    await callback.answer()


# ── ОБЪЯВЛЕНИЯ ───────────────────────────────────────────────────────────────

@router.message(F.text == "📣 Объявления")
async def menu_announcements(message: Message, staff: Staff | None = None):
    if staff is None:
        return
    is_admin = staff.role in _ADMIN_ROLES
    await message.answer(
        "<b>📣 Объявления</b>",
        reply_markup=announcements_submenu_kb(is_admin),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "ann_unread")
async def cb_ann_unread(callback: CallbackQuery, staff: Staff | None = None):
    if staff is None:
        return await callback.answer()
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    from app.db.crud import get_announcement_reads
    async with async_session_factory() as session:
        announcements = await get_announcements(session, limit=50)
        # Filter unread in Python since get_announcements doesn't support unread_for
        read_ids: set[int] = set()
        for ann in announcements:
            reads = await get_announcement_reads(session, ann.id)
            if any(r.staff_id == staff.id for r in reads):
                read_ids.add(ann.id)
    unread = [a for a in announcements if a.id not in read_ids][:10]
    if not unread:
        await callback.message.edit_text("📭 Новых объявлений нет.", reply_markup=InlineKeyboardMarkup(inline_keyboard=[]))
        return await callback.answer()
    rows = []
    lines = ["<b>📣 Непрочитанные объявления:</b>\n"]
    for ann in unread:
        lines.append(f"📣 {ann.created_at.strftime('%d.%m %H:%M')}\n{ann.text[:100]}{'...' if len(ann.text) > 100 else ''}")
        rows.append([InlineKeyboardButton(text=f"✅ Прочитано #{ann.id}", callback_data=f"ann_read:{ann.id}")])
    await callback.message.edit_text(
        "\n\n".join(lines),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("ann_read:"))
async def cb_ann_read(callback: CallbackQuery, staff: Staff | None = None):
    if staff is None:
        return await callback.answer()
    ann_id = int(callback.data.split(":")[1])
    async with async_session_factory() as session:
        await mark_announcement_read(session, ann_id, staff.id)
    await callback.answer("✅ Отмечено как прочитанное")


@router.callback_query(F.data.startswith("ann_history:"))
async def cb_ann_history(callback: CallbackQuery, staff: Staff | None = None):
    if staff is None:
        return await callback.answer()
    page = int(callback.data.split(":")[1])
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    async with async_session_factory() as session:
        announcements = await get_announcements(session, limit=20)
    start = page * PAGE_SIZE
    items = announcements[start: start + PAGE_SIZE]
    total = max(1, (len(announcements) + PAGE_SIZE - 1) // PAGE_SIZE)
    if not items:
        text = "📭 Объявлений нет."
        kb = InlineKeyboardMarkup(inline_keyboard=[])
    else:
        lines = ["<b>📜 История объявлений:</b>\n"]
        for ann in items:
            lines.append(f"📣 {ann.created_at.strftime('%d.%m %H:%M')}\n{ann.text[:120]}{'...' if len(ann.text) > 120 else ''}")
        text = "\n\n".join(lines)
        nav = []
        if page > 0:
            nav.append(InlineKeyboardButton(text="← Пред.", callback_data=f"ann_history:{page-1}"))
        nav.append(InlineKeyboardButton(text=f"{page+1}/{total}", callback_data="noop"))
        if page < total - 1:
            nav.append(InlineKeyboardButton(text="След. →", callback_data=f"ann_history:{page+1}"))
        kb = InlineKeyboardMarkup(inline_keyboard=[nav] if nav else [])
    try:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except Exception:
        await callback.message.answer(text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "announce_create")
async def cb_announce_create(callback: CallbackQuery, state: FSMContext, staff: Staff | None = None):
    if staff is None or staff.role not in _ADMIN_ROLES:
        return await callback.answer("⛔ Нет прав", show_alert=True)
    await state.set_state(AnnounceFSM.waiting_text)
    await callback.message.answer("📣 Введите текст объявления:")
    await callback.answer()


# ── АНАЛИТИКА ────────────────────────────────────────────────────────────────

@router.message(F.text == "📊 Аналитика")
async def menu_analytics(message: Message, staff: Staff | None = None):
    if staff is None or staff.role not in _ADMIN_ROLES:
        return
    await message.answer(
        "<b>📊 Аналитика</b>",
        reply_markup=analytics_submenu_kb(),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "analytics_session")
async def cb_analytics_session(callback: CallbackQuery, staff: Staff | None = None):
    if staff is None or staff.role not in _ADMIN_ROLES:
        return await callback.answer("⛔", show_alert=True)
    from app.db.crud import get_session_stats
    from aiogram.types import InlineKeyboardMarkup
    async with async_session_factory() as session:
        sess = await get_active_session(session)
        if not sess:
            await callback.answer("❌ Нет активной смены", show_alert=True)
            return
        stats = await get_session_stats(session, sess.id)
    done, total = stats["done_tasks"], stats["total_tasks"]
    pct = round(done / total * 100) if total else 0
    text = (
        f"<b>📊 Аналитика смены «{sess.name}»</b>\n"
        f"─────────────────\n"
        f"📋 Задачи: {done}/{total} ({pct}%)\n"
        f"🎉 Мероприятий: {stats['total_events']}\n"
        f"🚨 Инцидентов: {stats['total_incidents']}"
    )
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=[]))
    await callback.answer()


@router.callback_query(F.data == "analytics_excel")
async def cb_analytics_excel(callback: CallbackQuery, staff: Staff | None = None):
    if staff is None or staff.role not in _ADMIN_ROLES:
        return await callback.answer("⛔", show_alert=True)
    await callback.answer("Используйте команду /report_excel", show_alert=True)


# ── УПРАВЛЕНИЕ ───────────────────────────────────────────────────────────────

@router.message(F.text == "⚙️ Управление")
async def menu_management(message: Message, staff: Staff | None = None):
    if staff is None or staff.role not in _ADMIN_ROLES:
        return
    await message.answer(
        "<b>⚙️ Управление</b>",
        reply_markup=management_submenu_kb(),
        parse_mode="HTML",
    )


# ── КРУЖОК ───────────────────────────────────────────────────────────────────

@router.message(F.text == "🧩 Мой кружок")
async def menu_my_circle(message: Message, staff: Staff | None = None):
    if staff is None:
        return
    async with async_session_factory() as session:
        circles = await get_circles(session, leader_id=staff.id)
    if not circles:
        await message.answer("📭 У вас нет назначенных кружков.")
        return
    c = circles[0]
    async with async_session_factory() as session:
        members = await get_circle_members(session, c.id)
    from app.bot.handlers.circles import _circle_text
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    text = _circle_text(c) + f"\n\nУчастников: {len(members)}"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Отметить посещаемость", callback_data=f"att_start:{c.id}")]
    ])
    await message.answer(text, reply_markup=kb, parse_mode="HTML")


# ── ПОСЕЩАЕМОСТЬ ─────────────────────────────────────────────────────────────

@router.message(F.text == "✅ Посещаемость")
async def menu_attendance(message: Message, staff: Staff | None = None):
    if staff is None:
        return
    async with async_session_factory() as session:
        circles = await get_circles(session, leader_id=staff.id)
    if not circles:
        await message.answer("📭 У вас нет назначенных кружков.")
        return
    # Redirect to /attendance command behavior
    from app.bot.handlers.circles import cmd_attendance
    await cmd_attendance(message, staff=staff)


# ── NOOP callback ────────────────────────────────────────────────────────────

@router.callback_query(F.data == "noop")
async def cb_noop(callback: CallbackQuery):
    await callback.answer()


# ── duty_admin_view ───────────────────────────────────────────────────────────

@router.callback_query(F.data == "duty_admin_view")
async def cb_duty_admin_view(callback: CallbackQuery, staff: Staff | None = None):
    if staff is None or staff.role not in _ADMIN_ROLES:
        return await callback.answer("⛔", show_alert=True)
    await callback.answer("Используйте команду /duty_view", show_alert=True)
