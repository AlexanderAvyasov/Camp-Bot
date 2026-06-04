from datetime import datetime, timedelta, timezone

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.bot.keyboards import (
    cancel_kb,
    task_action_kb,
    task_admin_action_kb,
    task_assignee_kb,
    task_deadline_kb,
    task_group_kb,
    task_priority_kb,
    tasks_admin_menu,
    tasks_staff_menu,
    template_item_kb,
    template_recurrence_kb,
    confirm_kb,
    role_menu,
)
from app.bot.states import TaskCreateFSM, TaskFromTemplateFSM, TemplateFSM, TaskPauseFSM
from app.db.base import async_session_factory
from app.db.crud import (
    add_task_log,
    create_task,
    create_template,
    get_all_tasks,
    get_all_templates,
    get_staff_by_id,
    get_staff_by_role,
    get_task_by_id,
    get_tasks_for_staff,
    get_template_by_id,
    update_task,
    update_task_status,
)
from app.db.models import (
    PRIORITY_LABELS,
    ROLE_LABELS,
    STATUS_LABELS,
    RecurrenceType,
    Staff,
    StaffRole,
    TaskPriority,
    TaskStatus,
)

router = Router(name="tasks")

_ADMIN_ROLES = {StaffRole.admin, StaffRole.senior_counselor}
_DT_FMT = "%d.%m.%Y %H:%M"
_D_FMT = "%d.%m.%Y"
PAGE_SIZE = 5


def _task_text(task) -> str:
    assignee = task.assignee.full_name if task.assignee else "—"
    group = ROLE_LABELS.get(task.group_role, "—") if task.group_role else "—"
    deadline = task.deadline.strftime(_DT_FMT) if task.deadline else "—"
    priority = PRIORITY_LABELS.get(task.priority, task.priority)
    status = STATUS_LABELS.get(task.status, task.status)
    return (
        f"📋 <b>{task.title}</b> (ID: {task.id})\n"
        f"Статус: {status}\n"
        f"Приоритет: {priority}\n"
        f"Группа: {group}\n"
        f"Исполнитель: {assignee}\n"
        f"Дедлайн: {deadline}"
    )


# ── Меню задач (вызывается из start.py) ──────────────────────────────────────

@router.callback_query(F.data == "task_create")
async def cb_task_create(callback: CallbackQuery, state: FSMContext, staff: Staff | None = None):
    if staff is None or staff.role not in _ADMIN_ROLES:
        await callback.answer("⛔ Нет прав", show_alert=True)
        return
    await callback.message.answer(
        "➕ <b>Новая задача</b>\n\nВведите <b>название</b> задачи:",
        reply_markup=cancel_kb(), parse_mode="HTML",
    )
    await state.set_state(TaskCreateFSM.waiting_title)
    await callback.answer()


@router.message(TaskCreateFSM.waiting_title)
async def fsm_task_title(message: Message, state: FSMContext):
    await state.update_data(title=message.text.strip())
    await message.answer(
        "Выберите <b>группу</b> исполнителей:",
        reply_markup=task_group_kb(), parse_mode="HTML",
    )
    await state.set_state(TaskCreateFSM.waiting_group)


@router.callback_query(TaskCreateFSM.waiting_group, F.data.startswith("task_group:"))
async def fsm_task_group(callback: CallbackQuery, state: FSMContext):
    role_value = callback.data.split(":")[1]
    role = StaffRole(role_value)
    await state.update_data(group_role=role_value)

    async with async_session_factory() as session:
        staff_list = await get_staff_by_role(session, role)

    role_label = ROLE_LABELS[role]
    await callback.message.edit_text(
        f"Группа: <b>{role_label}</b>\n\nВыберите исполнителя или назначьте для всей группы:",
        reply_markup=task_assignee_kb(staff_list, role_value),
        parse_mode="HTML",
    )
    await state.set_state(TaskCreateFSM.waiting_assignee)
    await callback.answer()


@router.callback_query(TaskCreateFSM.waiting_assignee, F.data.startswith("task_assignee:"))
async def fsm_task_assignee(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split(":")
    assignee_part = parts[1]  # "group" or staff_id
    role_value = parts[2]

    if assignee_part == "group":
        await state.update_data(assigned_to=None, group_role=role_value)
    else:
        await state.update_data(assigned_to=int(assignee_part), group_role=role_value)

    await callback.message.edit_text(
        "Выберите <b>приоритет</b>:",
        reply_markup=task_priority_kb(), parse_mode="HTML",
    )
    await state.set_state(TaskCreateFSM.waiting_priority)
    await callback.answer()


@router.callback_query(TaskCreateFSM.waiting_priority, F.data.startswith("task_priority:"))
async def fsm_task_priority(callback: CallbackQuery, state: FSMContext):
    priority = TaskPriority(callback.data.split(":")[1])
    await state.update_data(priority=priority.value)
    await callback.message.edit_text(
        "Введите <b>дедлайн</b> (ДД.ММ.ГГГГ ЧЧ:ММ) или пропустите:",
        reply_markup=task_deadline_kb(), parse_mode="HTML",
    )
    await state.set_state(TaskCreateFSM.waiting_deadline)
    await callback.answer()


@router.callback_query(TaskCreateFSM.waiting_deadline, F.data == "task_deadline:skip")
async def fsm_task_deadline_skip(callback: CallbackQuery, state: FSMContext, staff: Staff | None = None):
    await state.update_data(deadline=None)
    await _finish_task_creation(callback.message, state, staff)
    await callback.answer()


@router.message(TaskCreateFSM.waiting_deadline)
async def fsm_task_deadline(message: Message, state: FSMContext, staff: Staff | None = None):
    try:
        dt = datetime.strptime(message.text.strip(), _DT_FMT).replace(tzinfo=timezone.utc)
        await state.update_data(deadline=dt.isoformat())
    except ValueError:
        await message.answer(f"❌ Неверный формат. Введите ДД.ММ.ГГГГ ЧЧ:ММ или нажмите «Пропустить»:",
                             reply_markup=task_deadline_kb())
        return
    await _finish_task_creation(message, state, staff)


async def _finish_task_creation(message: Message, state: FSMContext, staff: Staff | None):
    data = await state.get_data()
    deadline = datetime.fromisoformat(data["deadline"]) if data.get("deadline") else None
    group_role = StaffRole(data["group_role"]) if data.get("group_role") else None
    priority = TaskPriority(data.get("priority", TaskPriority.medium.value))
    assigned_to = data.get("assigned_to")

    async with async_session_factory() as session:
        task = await create_task(
            session,
            title=data["title"],
            created_by=staff.id if staff else 0,
            assigned_to=assigned_to,
            group_role=group_role,
            priority=priority,
            deadline=deadline,
        )

    await state.clear()

    # Уведомить исполнителя
    if assigned_to:
        async with async_session_factory() as session:
            assignee = await get_staff_by_id(session, assigned_to)
        if assignee and assignee.telegram_id:
            try:
                from app.bot.bot import get_bot
                bot = get_bot()
                await bot.send_message(
                    assignee.telegram_id,
                    f"📋 Вам назначена задача: <b>{task.title}</b>\n"
                    f"Приоритет: {PRIORITY_LABELS[priority]}\n"
                    f"Дедлайн: {task.deadline.strftime(_DT_FMT) if task.deadline else '—'}",
                    parse_mode="HTML",
                )
            except Exception:
                pass

    await message.answer(
        f"✅ Задача создана!\n\n{_task_text(task)}",
        reply_markup=task_admin_action_kb(task.id),
        parse_mode="HTML",
    )


# ── Просмотр задач ────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("tasks_all:"))
async def cb_tasks_all(callback: CallbackQuery, staff: Staff | None = None):
    if staff is None or staff.role not in _ADMIN_ROLES:
        await callback.answer("⛔ Нет прав", show_alert=True)
        return
    page = int(callback.data.split(":")[1])
    async with async_session_factory() as session:
        tasks, total = await get_all_tasks(session, offset=page * PAGE_SIZE, limit=PAGE_SIZE)
    await _send_task_list(callback, tasks, total, page, "tasks_all", "📋 <b>Все задачи</b>")


@router.callback_query(F.data.startswith("tasks_overdue:"))
async def cb_tasks_overdue(callback: CallbackQuery, staff: Staff | None = None):
    if staff is None or staff.role not in _ADMIN_ROLES:
        await callback.answer("⛔ Нет прав", show_alert=True)
        return
    page = int(callback.data.split(":")[1])
    async with async_session_factory() as session:
        tasks, total = await get_all_tasks(session, status=TaskStatus.overdue, offset=page * PAGE_SIZE, limit=PAGE_SIZE)
    await _send_task_list(callback, tasks, total, page, "tasks_overdue", "⚠️ <b>Просроченные задачи</b>")


@router.callback_query(F.data.startswith("my_tasks:"))
async def cb_my_tasks(callback: CallbackQuery, staff: Staff | None = None):
    if staff is None:
        await callback.answer("⛔ Нет прав", show_alert=True)
        return
    async with async_session_factory() as session:
        tasks = await get_tasks_for_staff(session, staff.id)

    if not tasks:
        await callback.message.edit_text("📋 У вас нет активных задач.", reply_markup=tasks_staff_menu())
        await callback.answer()
        return

    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
    rows = []
    for t in tasks:
        status_icon = STATUS_LABELS.get(t.status, "")[:2]
        rows.append([InlineKeyboardButton(
            text=f"{status_icon} {t.title[:35]}",
            callback_data=f"task_view:{t.id}",
        )])
    await callback.message.edit_text(
        f"📋 <b>Мои задачи</b> ({len(tasks)}):",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
        parse_mode="HTML",
    )
    await callback.answer()


async def _send_task_list(callback: CallbackQuery, tasks: list, total: int, page: int, prefix: str, header: str):
    if not tasks:
        await callback.message.edit_text(
            f"{header}\n\nЗадач нет.",
            reply_markup=tasks_admin_menu(),
            parse_mode="HTML",
        )
        await callback.answer()
        return

    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    rows = []
    for t in tasks:
        status_icon = STATUS_LABELS.get(t.status, "")[:2]
        assignee = t.assignee.full_name if t.assignee else ROLE_LABELS.get(t.group_role, "—") if t.group_role else "—"
        rows.append([InlineKeyboardButton(
            text=f"{status_icon} {t.title[:30]} — {assignee[:15]}",
            callback_data=f"task_view:{t.id}",
        )])

    total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="◀️", callback_data=f"{prefix}:{page - 1}"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton(text="▶️", callback_data=f"{prefix}:{page + 1}"))
    if nav:
        rows.append(nav)

    await callback.message.edit_text(
        f"{header} (стр. {page + 1}/{total_pages})",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("task_view:"))
async def cb_task_view(callback: CallbackQuery, staff: Staff | None = None):
    if staff is None:
        await callback.answer("⛔ Нет прав", show_alert=True)
        return
    task_id = int(callback.data.split(":")[1])
    async with async_session_factory() as session:
        task = await get_task_by_id(session, task_id)
    if not task:
        await callback.answer("❌ Задача не найдена", show_alert=True)
        return

    is_assignee = task.assigned_to == staff.id
    is_admin = staff.role in _ADMIN_ROLES

    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()

    if is_assignee:
        if task.status == TaskStatus.new:
            builder.button(text="✅ Принять", callback_data=f"task_accept:{task_id}")
        if task.status in (TaskStatus.new, TaskStatus.accepted):
            builder.button(text="🔄 В работу", callback_data=f"task_inprogress:{task_id}")
        if task.status != TaskStatus.done:
            builder.button(text="✔️ Выполнено", callback_data=f"task_done:{task_id}")
            builder.button(text="❓ Уточнить", callback_data=f"task_clarify:{task_id}")
    if is_admin:
        builder.button(text="🗑 Удалить", callback_data=f"task_del_confirm:{task_id}")
    builder.adjust(2)

    kb = builder.as_markup() if (is_assignee or is_admin) else None
    try:
        await callback.message.edit_text(_task_text(task), reply_markup=kb, parse_mode="HTML")
    except Exception:
        await callback.message.answer(_task_text(task), reply_markup=kb, parse_mode="HTML")
    await callback.answer()


# ── Действия с задачами ───────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("task_accept:"))
async def cb_task_accept(callback: CallbackQuery, staff: Staff | None = None):
    if staff is None:
        return
    task_id = int(callback.data.split(":")[1])
    async with async_session_factory() as session:
        task = await update_task_status(session, task_id, staff.id, TaskStatus.accepted, "Принята")
    await callback.message.edit_text(_task_text(task), parse_mode="HTML")
    await callback.answer("✅ Задача принята")


@router.callback_query(F.data.startswith("task_inprogress:"))
async def cb_task_inprogress(callback: CallbackQuery, staff: Staff | None = None):
    if staff is None:
        return
    task_id = int(callback.data.split(":")[1])
    async with async_session_factory() as session:
        task = await update_task_status(session, task_id, staff.id, TaskStatus.in_progress, "В работе")
    await callback.message.edit_text(_task_text(task), parse_mode="HTML")
    await callback.answer("🔄 Задача в работе")


@router.callback_query(F.data.startswith("task_done:"))
async def cb_task_done(callback: CallbackQuery, staff: Staff | None = None):
    if staff is None:
        return
    task_id = int(callback.data.split(":")[1])
    async with async_session_factory() as session:
        task = await update_task_status(session, task_id, staff.id, TaskStatus.done, "Выполнена")

    # Уведомить создателя
    async with async_session_factory() as session:
        creator = await get_staff_by_id(session, task.created_by)
    if creator and creator.telegram_id:
        try:
            from app.bot.bot import get_bot
            bot = get_bot()
            await bot.send_message(
                creator.telegram_id,
                f"✔️ Задача <b>{task.title}</b> выполнена сотрудником <b>{staff.full_name}</b>.",
                parse_mode="HTML",
            )
        except Exception:
            pass

    await callback.message.edit_text(_task_text(task), parse_mode="HTML")
    await callback.answer("✔️ Задача выполнена!")


@router.callback_query(F.data.startswith("task_clarify:"))
async def cb_task_clarify(callback: CallbackQuery, staff: Staff | None = None):
    if staff is None:
        return
    task_id = int(callback.data.split(":")[1])
    async with async_session_factory() as session:
        task = await get_task_by_id(session, task_id)
        await add_task_log(session, task_id, staff.id, f"Запрос уточнения от {staff.full_name}")
        creator = await get_staff_by_id(session, task.created_by)

    if creator and creator.telegram_id:
        try:
            from app.bot.bot import get_bot
            bot = get_bot()
            await bot.send_message(
                creator.telegram_id,
                f"❓ <b>{staff.full_name}</b> просит уточнения по задаче <b>{task.title}</b>.",
                parse_mode="HTML",
            )
        except Exception:
            pass

    await callback.answer("❓ Запрос на уточнение отправлен", show_alert=True)


@router.callback_query(F.data.startswith("task_del_confirm:"))
async def cb_task_del_confirm(callback: CallbackQuery, staff: Staff | None = None):
    if staff is None or staff.role not in _ADMIN_ROLES:
        await callback.answer("⛔ Нет прав", show_alert=True)
        return
    task_id = int(callback.data.split(":")[1])
    await callback.message.edit_text(
        "❗ Удалить задачу?",
        reply_markup=confirm_kb(f"task_del:{task_id}", f"task_view:{task_id}"),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("task_del:"))
async def cb_task_del(callback: CallbackQuery, staff: Staff | None = None):
    if staff is None or staff.role not in _ADMIN_ROLES:
        await callback.answer("⛔ Нет прав", show_alert=True)
        return
    task_id = int(callback.data.split(":")[1])
    from sqlalchemy import delete as sql_delete
    from app.db.models import Task, TaskLog, TaskPhoto
    async with async_session_factory() as session:
        task = await get_task_by_id(session, task_id)
        if task:
            title = task.title
            await session.execute(sql_delete(TaskLog).where(TaskLog.task_id == task_id))
            await session.execute(sql_delete(TaskPhoto).where(TaskPhoto.task_id == task_id))
            await session.delete(task)
            await session.commit()
    await callback.message.edit_text(f"🗑 Задача <b>{title}</b> удалена.", parse_mode="HTML")
    await callback.answer()


# ── Шаблоны ───────────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("templates_list:"))
async def cb_templates_list(callback: CallbackQuery, staff: Staff | None = None):
    if staff is None or staff.role not in _ADMIN_ROLES:
        await callback.answer("⛔ Нет прав", show_alert=True)
        return
    async with async_session_factory() as session:
        templates = await get_all_templates(session)

    if not templates:
        await callback.message.edit_text(
            "📝 <b>Шаблоны задач</b>\n\nШаблонов пока нет.",
            reply_markup=tasks_admin_menu(), parse_mode="HTML",
        )
        await callback.answer()
        return

    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
    rows = [[InlineKeyboardButton(text=f"📝 {t.title}", callback_data=f"template_view:{t.id}")] for t in templates]
    rows.append([InlineKeyboardButton(text="➕ Новый шаблон", callback_data="template_new")])
    rows.append([InlineKeyboardButton(text="◀️ Назад", callback_data="tasks_back")])
    await callback.message.edit_text(
        f"📝 <b>Шаблоны задач</b> ({len(templates)}):",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("template_view:"))
async def cb_template_view(callback: CallbackQuery, staff: Staff | None = None):
    if staff is None or staff.role not in _ADMIN_ROLES:
        await callback.answer("⛔ Нет прав", show_alert=True)
        return
    tmpl_id = int(callback.data.split(":")[1])
    async with async_session_factory() as session:
        tmpl = await get_template_by_id(session, tmpl_id)
    if not tmpl:
        await callback.answer("❌ Шаблон не найден", show_alert=True)
        return

    group = ROLE_LABELS.get(tmpl.group_role, "—") if tmpl.group_role else "—"
    recur = {"daily": "Ежедневно", "weekly": "Еженедельно"}.get(tmpl.recurrence_type, "Нет") if tmpl.recurrence_type else "Нет"
    text = (
        f"📝 <b>{tmpl.title}</b>\n"
        f"Описание: {tmpl.description or '—'}\n"
        f"Группа: {group}\n"
        f"Приоритет: {PRIORITY_LABELS.get(tmpl.priority, tmpl.priority)}\n"
        f"Повторение: {recur}"
    )
    await callback.message.edit_text(text, reply_markup=template_item_kb(tmpl_id), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "template_new")
async def cb_template_new(callback: CallbackQuery, state: FSMContext, staff: Staff | None = None):
    if staff is None or staff.role not in _ADMIN_ROLES:
        await callback.answer("⛔ Нет прав", show_alert=True)
        return
    await callback.message.answer(
        "📝 <b>Новый шаблон</b>\n\nВведите <b>название</b>:",
        reply_markup=cancel_kb(), parse_mode="HTML",
    )
    await state.set_state(TemplateFSM.waiting_title)
    await callback.answer()


@router.message(TemplateFSM.waiting_title)
async def fsm_tmpl_title(message: Message, state: FSMContext):
    await state.update_data(title=message.text.strip())
    from app.bot.keyboards import skip_cancel_kb
    await message.answer("Введите <b>описание</b> (или пропустите):", reply_markup=skip_cancel_kb("tmpl_skip_desc"), parse_mode="HTML")
    await state.set_state(TemplateFSM.waiting_description)


@router.callback_query(TemplateFSM.waiting_description, F.data == "tmpl_skip_desc")
async def fsm_tmpl_skip_desc(callback: CallbackQuery, state: FSMContext):
    await state.update_data(description=None)
    await callback.message.edit_text("Выберите <b>роль группы</b>:", reply_markup=role_menu("tmpl_role"), parse_mode="HTML")
    await state.set_state(TemplateFSM.waiting_role)
    await callback.answer()


@router.message(TemplateFSM.waiting_description)
async def fsm_tmpl_desc(message: Message, state: FSMContext):
    await state.update_data(description=message.text.strip())
    await message.answer("Выберите <b>роль группы</b>:", reply_markup=role_menu("tmpl_role"), parse_mode="HTML")
    await state.set_state(TemplateFSM.waiting_role)


@router.callback_query(TemplateFSM.waiting_role, F.data.startswith("tmpl_role:"))
async def fsm_tmpl_role(callback: CallbackQuery, state: FSMContext):
    role_value = callback.data.split(":")[1]
    await state.update_data(group_role=role_value)
    await callback.message.edit_text("Выберите <b>приоритет</b>:", reply_markup=task_priority_kb(), parse_mode="HTML")
    await state.set_state(TemplateFSM.waiting_priority)
    await callback.answer()


@router.callback_query(TemplateFSM.waiting_priority, F.data.startswith("task_priority:"))
async def fsm_tmpl_priority(callback: CallbackQuery, state: FSMContext):
    priority = TaskPriority(callback.data.split(":")[1])
    await state.update_data(priority=priority.value)
    await callback.message.edit_text("Выберите <b>повторение</b>:", reply_markup=template_recurrence_kb(), parse_mode="HTML")
    await state.set_state(TemplateFSM.waiting_recurrence)
    await callback.answer()


@router.callback_query(TemplateFSM.waiting_recurrence, F.data.startswith("tmpl_recur:"))
async def fsm_tmpl_recur(callback: CallbackQuery, state: FSMContext, staff: Staff | None = None):
    recur_value = callback.data.split(":")[1]
    recurrence = RecurrenceType(recur_value) if recur_value != "none" else None
    data = await state.get_data()

    async with async_session_factory() as session:
        tmpl = await create_template(
            session,
            title=data["title"],
            description=data.get("description"),
            group_role=StaffRole(data["group_role"]) if data.get("group_role") else None,
            priority=TaskPriority(data["priority"]),
            recurrence_type=recurrence,
        )

    await state.clear()
    await callback.message.edit_text(
        f"✅ Шаблон <b>{tmpl.title}</b> создан!",
        reply_markup=template_item_kb(tmpl.id),
        parse_mode="HTML",
    )
    await callback.answer()


# ── Задача из шаблона ─────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("task_from_template:"))
async def cb_task_from_template(callback: CallbackQuery, state: FSMContext, staff: Staff | None = None):
    if staff is None or staff.role not in _ADMIN_ROLES:
        await callback.answer("⛔ Нет прав", show_alert=True)
        return
    tmpl_id = int(callback.data.split(":")[1])
    await state.update_data(template_id=tmpl_id)

    async with async_session_factory() as session:
        tmpl = await get_template_by_id(session, tmpl_id)

    # Если у шаблона есть роль — сразу показываем список исполнителей
    if tmpl and tmpl.group_role:
        async with async_session_factory() as session:
            staff_list = await get_staff_by_role(session, tmpl.group_role)
        await state.update_data(group_role=tmpl.group_role.value)
        await callback.message.answer(
            f"Шаблон: <b>{tmpl.title}</b>\nВыберите исполнителя:",
            reply_markup=task_assignee_kb(staff_list, tmpl.group_role.value),
            parse_mode="HTML",
        )
        await state.set_state(TaskFromTemplateFSM.waiting_assignee)
    else:
        await callback.message.answer(
            f"Шаблон: <b>{tmpl.title if tmpl else '?'}</b>\n\nВыберите группу:",
            reply_markup=task_group_kb(), parse_mode="HTML",
        )
        await state.set_state(TaskFromTemplateFSM.waiting_group)
    await callback.answer()


@router.callback_query(TaskFromTemplateFSM.waiting_group, F.data.startswith("task_group:"))
async def fsm_tft_group(callback: CallbackQuery, state: FSMContext):
    role_value = callback.data.split(":")[1]
    role = StaffRole(role_value)
    await state.update_data(group_role=role_value)
    async with async_session_factory() as session:
        staff_list = await get_staff_by_role(session, role)
    await callback.message.edit_text(
        f"Группа: <b>{ROLE_LABELS[role]}</b>\n\nВыберите исполнителя:",
        reply_markup=task_assignee_kb(staff_list, role_value),
        parse_mode="HTML",
    )
    await state.set_state(TaskFromTemplateFSM.waiting_assignee)
    await callback.answer()


@router.callback_query(TaskFromTemplateFSM.waiting_assignee, F.data.startswith("task_assignee:"))
async def fsm_tft_assignee(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split(":")
    assignee_part = parts[1]
    role_value = parts[2]
    if assignee_part == "group":
        await state.update_data(assigned_to=None, group_role=role_value)
    else:
        await state.update_data(assigned_to=int(assignee_part), group_role=role_value)
    await callback.message.edit_text(
        "Введите <b>дедлайн</b> (ДД.ММ.ГГГГ ЧЧ:ММ) или пропустите:",
        reply_markup=task_deadline_kb(), parse_mode="HTML",
    )
    await state.set_state(TaskFromTemplateFSM.waiting_deadline)
    await callback.answer()


@router.callback_query(TaskFromTemplateFSM.waiting_deadline, F.data == "task_deadline:skip")
async def fsm_tft_deadline_skip(callback: CallbackQuery, state: FSMContext, staff: Staff | None = None):
    await state.update_data(deadline=None)
    await _finish_tft(callback.message, state, staff)
    await callback.answer()


@router.message(TaskFromTemplateFSM.waiting_deadline)
async def fsm_tft_deadline(message: Message, state: FSMContext, staff: Staff | None = None):
    try:
        dt = datetime.strptime(message.text.strip(), _DT_FMT).replace(tzinfo=timezone.utc)
        await state.update_data(deadline=dt.isoformat())
    except ValueError:
        await message.answer("❌ Неверный формат:", reply_markup=task_deadline_kb())
        return
    await _finish_tft(message, state, staff)


async def _finish_tft(message: Message, state: FSMContext, staff: Staff | None):
    data = await state.get_data()
    deadline = datetime.fromisoformat(data["deadline"]) if data.get("deadline") else None
    group_role = StaffRole(data["group_role"]) if data.get("group_role") else None
    assigned_to = data.get("assigned_to")
    tmpl_id = data.get("template_id")

    async with async_session_factory() as session:
        tmpl = await get_template_by_id(session, tmpl_id)
        task = await create_task(
            session,
            title=tmpl.title if tmpl else "Задача",
            created_by=staff.id if staff else 0,
            assigned_to=assigned_to,
            group_role=group_role,
            priority=tmpl.priority if tmpl else TaskPriority.medium,
            deadline=deadline,
            template_id=tmpl_id,
        )

    await state.clear()
    await message.answer(
        f"✅ Задача из шаблона создана!\n\n{_task_text(task)}",
        reply_markup=task_admin_action_kb(task.id),
        parse_mode="HTML",
    )


# ── Пауза задачи ─────────────────────────────────────────────────────────────

@router.callback_query(F.data == "task_pause_menu")
async def cb_task_pause_menu(callback: CallbackQuery, state: FSMContext, staff: Staff | None = None):
    if staff is None or staff.role not in _ADMIN_ROLES:
        await callback.answer("⛔ Нет прав", show_alert=True)
        return
    await callback.message.answer(
        "⏸ <b>Пауза задачи</b>\n\nВведите <b>ID задачи</b>:",
        reply_markup=cancel_kb(), parse_mode="HTML",
    )
    await state.set_state(TaskPauseFSM.waiting_task_id)
    await callback.answer()


@router.callback_query(F.data.startswith("task_pause_start:"))
async def cb_task_pause_start(callback: CallbackQuery, state: FSMContext, staff: Staff | None = None):
    if staff is None or staff.role not in _ADMIN_ROLES:
        await callback.answer("⛔ Нет прав", show_alert=True)
        return
    task_id = int(callback.data.split(":")[1])
    await state.update_data(pause_task_id=task_id)
    await callback.message.answer(
        "⏸ <b>Пауза задачи</b>\n\nНа сколько дней поставить задачу на паузу?",
        reply_markup=cancel_kb(), parse_mode="HTML",
    )
    await state.set_state(TaskPauseFSM.waiting_days)
    await callback.answer()


@router.message(TaskPauseFSM.waiting_task_id)
async def fsm_pause_task_id(message: Message, state: FSMContext, staff: Staff | None = None):
    if not message.text or not message.text.strip().isdigit():
        await message.answer("❌ Введите числовой ID задачи:", reply_markup=cancel_kb())
        return
    task_id = int(message.text.strip())
    async with async_session_factory() as session:
        task = await get_task_by_id(session, task_id)
    if not task:
        await message.answer("❌ Задача не найдена. Введите другой ID:", reply_markup=cancel_kb())
        return
    await state.update_data(pause_task_id=task_id)
    await message.answer(
        f"Задача: <b>{task.title}</b>\n\nНа сколько дней поставить на паузу?",
        reply_markup=cancel_kb(), parse_mode="HTML",
    )
    await state.set_state(TaskPauseFSM.waiting_days)


@router.message(TaskPauseFSM.waiting_days)
async def fsm_pause_days(message: Message, state: FSMContext, staff: Staff | None = None):
    if not message.text or not message.text.strip().isdigit():
        await message.answer("❌ Введите количество дней (число):", reply_markup=cancel_kb())
        return
    days = int(message.text.strip())
    if days < 1 or days > 365:
        await message.answer("❌ Введите от 1 до 365 дней:", reply_markup=cancel_kb())
        return

    data = await state.get_data()
    task_id = data["pause_task_id"]
    paused_until = (datetime.now(tz=timezone.utc) + timedelta(days=days)).date()

    async with async_session_factory() as session:
        task = await update_task(session, task_id, paused_until=paused_until)
        if task and staff:
            await add_task_log(session, task_id, staff.id, f"Задача поставлена на паузу до {paused_until.strftime('%d.%m.%Y')}")

    await state.clear()
    if task:
        await message.answer(
            f"⏸ Задача <b>{task.title}</b> поставлена на паузу до <b>{paused_until.strftime('%d.%m.%Y')}</b>.",
            parse_mode="HTML",
        )
    else:
        await message.answer("❌ Задача не найдена.")
