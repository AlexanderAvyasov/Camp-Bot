from datetime import datetime, timezone

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from app.bot.states import TaskCreateFSM, TemplateFSM
from app.db.base import async_session_factory
from app.db.crud import (
    add_task_log,
    add_task_photo,
    create_task,
    create_template,
    get_active_session,
    get_all_active_staff,
    get_all_tasks,
    get_all_templates,
    get_overdue_tasks,
    get_staff_by_id,
    get_staff_by_telegram_id,
    get_task_by_id,
    get_task_logs,
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

_DATE_FMT = "%d.%m.%Y %H:%M"
_ADMIN_ROLES = {StaffRole.admin, StaffRole.senior_counselor}
_PAGE_SIZE = 5

_cancel_kb = InlineKeyboardMarkup(
    inline_keyboard=[[InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_fsm")]]
)

_priority_kb = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text="🟢 Низкий", callback_data="task_prio:low"),
            InlineKeyboardButton(text="🟡 Средний", callback_data="task_prio:medium"),
            InlineKeyboardButton(text="🔴 Высокий", callback_data="task_prio:high"),
        ],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_fsm")],
    ]
)

_skip_cancel_kb = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="⏭ Без дедлайна", callback_data="task_skip_deadline")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_fsm")],
    ]
)


def _task_text(task, show_assignee: bool = True) -> str:
    deadline_str = task.deadline.strftime(_DATE_FMT) if task.deadline else "—"
    assignee_str = ""
    if show_assignee and task.assignee:
        assignee_str = f"\nИсполнитель: {task.assignee.full_name}"
    elif show_assignee and task.group_role:
        assignee_str = f"\nГруппа: {ROLE_LABELS.get(task.group_role, task.group_role)}"
    return (
        f"📋 <b>{task.title}</b> (ID: {task.id})\n"
        f"Статус: {STATUS_LABELS[task.status]}\n"
        f"Приоритет: {PRIORITY_LABELS[task.priority]}\n"
        f"Дедлайн: {deadline_str}"
        f"{assignee_str}"
    )


def _task_inline_kb(task_id: int, is_assignee: bool = False) -> InlineKeyboardMarkup:
    rows = []
    if is_assignee:
        rows.append([
            InlineKeyboardButton(text="✅ Принять", callback_data=f"task_accept:{task_id}"),
            InlineKeyboardButton(text="❓ Уточнить", callback_data=f"task_clarify:{task_id}"),
        ])
        rows.append([InlineKeyboardButton(text="✔️ Выполнено", callback_data=f"task_done:{task_id}")])
    return InlineKeyboardMarkup(inline_keyboard=rows) if rows else None


# ── /task @username title | deadline | priority ───────────────────────────────

@router.message(Command("task"))
async def cmd_task(message: Message, state: FSMContext, staff: Staff | None = None):
    if staff is None or staff.role not in _ADMIN_ROLES:
        await message.answer("⛔ У вас нет прав для выполнения этой команды.")
        return
    # Parse inline: /task @username title | deadline | priority
    args = message.text.split(maxsplit=1)
    if len(args) > 1:
        await _parse_task_inline(message, args[1], staff)
        return
    # FSM flow
    await message.answer(
        "➕ Создание задачи\n\nВведите <b>Telegram ID</b> исполнителя (или пропустите для группы):",
        reply_markup=_skip_cancel_kb, parse_mode="HTML",
    )
    await state.set_state(TaskCreateFSM.waiting_assignee)


async def _parse_task_inline(message: Message, args_str: str, creator: Staff):
    parts = [p.strip() for p in args_str.split("|")]
    title = parts[0] if parts else ""
    deadline_str = parts[1] if len(parts) > 1 else None
    priority_str = parts[2].lower() if len(parts) > 2 else "medium"

    # Extract username/id from first word
    words = title.split(maxsplit=1)
    telegram_id = None
    if words and words[0].lstrip("@").isdigit():
        telegram_id = int(words[0].lstrip("@"))
        title = words[1] if len(words) > 1 else ""

    deadline = None
    if deadline_str:
        try:
            deadline = datetime.strptime(deadline_str, "%d.%m.%Y %H:%M").replace(tzinfo=timezone.utc)
        except ValueError:
            try:
                deadline = datetime.strptime(deadline_str, "%d.%m.%Y").replace(tzinfo=timezone.utc)
            except ValueError:
                pass

    priority = TaskPriority.medium
    for p in TaskPriority:
        if p.value == priority_str:
            priority = p

    async with async_session_factory() as session:
        active = await get_active_session(session)
        assignee = None
        if telegram_id:
            assignee = await get_staff_by_telegram_id(session, telegram_id)
        task = await create_task(
            session, title=title, created_by=creator.id,
            session_id=active.id if active else None,
            assigned_to=assignee.id if assignee else None,
            priority=priority, deadline=deadline,
        )
        await add_task_log(session, task.id, creator.id, "created")

    await message.answer(f"✅ Задача создана!\n\n{_task_text(task)}", parse_mode="HTML")

    if assignee:
        try:
            bot: Bot = message.bot
            kb = _task_inline_kb(task.id, is_assignee=True)
            await bot.send_message(
                assignee.telegram_id,
                f"📋 Вам назначена задача!\n\n{_task_text(task, show_assignee=False)}",
                reply_markup=kb, parse_mode="HTML",
            )
        except Exception:
            pass


# FSM flow for /task without inline args

@router.callback_query(TaskCreateFSM.waiting_assignee, F.data == "task_skip_deadline")
async def fsm_task_skip_assignee(callback: CallbackQuery, state: FSMContext):
    await state.update_data(assigned_to=None)
    await callback.message.edit_text(
        "Введите <b>название задачи</b>:", reply_markup=_cancel_kb, parse_mode="HTML"
    )
    await state.set_state(TaskCreateFSM.waiting_title)
    await callback.answer()


@router.message(TaskCreateFSM.waiting_assignee)
async def fsm_task_assignee(message: Message, state: FSMContext):
    text = message.text.strip()
    if not text.isdigit():
        await message.answer("❌ Введите числовой Telegram ID:", reply_markup=_skip_cancel_kb)
        return
    async with async_session_factory() as session:
        person = await get_staff_by_telegram_id(session, int(text))
    if not person:
        await message.answer("❌ Сотрудник не найден:", reply_markup=_skip_cancel_kb)
        return
    await state.update_data(assigned_to=person.id, assignee_name=person.full_name)
    await message.answer(
        f"Исполнитель: <b>{person.full_name}</b>\n\nВведите <b>название задачи</b>:",
        reply_markup=_cancel_kb, parse_mode="HTML",
    )
    await state.set_state(TaskCreateFSM.waiting_title)


@router.message(TaskCreateFSM.waiting_title)
async def fsm_task_title(message: Message, state: FSMContext):
    await state.update_data(title=message.text.strip())
    await message.answer(
        "Введите <b>дедлайн</b> (формат: ДД.ММ.ГГГГ ЧЧ:ММ) или пропустите:",
        reply_markup=_skip_cancel_kb, parse_mode="HTML",
    )
    await state.set_state(TaskCreateFSM.waiting_deadline)


@router.message(TaskCreateFSM.waiting_deadline)
async def fsm_task_deadline(message: Message, state: FSMContext):
    text = message.text.strip()
    try:
        dt = datetime.strptime(text, "%d.%m.%Y %H:%M").replace(tzinfo=timezone.utc)
    except ValueError:
        try:
            dt = datetime.strptime(text, "%d.%m.%Y").replace(tzinfo=timezone.utc)
        except ValueError:
            await message.answer("❌ Неверный формат. Введите ДД.ММ.ГГГГ ЧЧ:ММ:", reply_markup=_skip_cancel_kb)
            return
    await state.update_data(deadline=dt.isoformat())
    await message.answer("Выберите <b>приоритет</b>:", reply_markup=_priority_kb, parse_mode="HTML")
    await state.set_state(TaskCreateFSM.waiting_priority)


@router.callback_query(TaskCreateFSM.waiting_deadline, F.data == "task_skip_deadline")
async def fsm_task_skip_deadline(callback: CallbackQuery, state: FSMContext):
    await state.update_data(deadline=None)
    await callback.message.edit_text("Выберите <b>приоритет</b>:", reply_markup=_priority_kb, parse_mode="HTML")
    await state.set_state(TaskCreateFSM.waiting_priority)
    await callback.answer()


@router.callback_query(TaskCreateFSM.waiting_priority, F.data.startswith("task_prio:"))
async def fsm_task_priority(callback: CallbackQuery, state: FSMContext, staff: Staff | None = None):
    priority = TaskPriority(callback.data.split(":")[1])
    data = await state.get_data()
    await state.clear()

    deadline = datetime.fromisoformat(data["deadline"]) if data.get("deadline") else None
    async with async_session_factory() as session:
        active = await get_active_session(session)
        task = await create_task(
            session,
            title=data["title"],
            created_by=staff.id,
            session_id=active.id if active else None,
            assigned_to=data.get("assigned_to"),
            priority=priority,
            deadline=deadline,
        )
        await add_task_log(session, task.id, staff.id, "created")
        assignee_tg_id = None
        if task.assigned_to and task.assignee:
            assignee_tg_id = task.assignee.telegram_id

    await callback.message.edit_text(f"✅ Задача создана!\n\n{_task_text(task)}", parse_mode="HTML")
    await callback.answer()

    if assignee_tg_id:
        try:
            kb = _task_inline_kb(task.id, is_assignee=True)
            await callback.bot.send_message(
                assignee_tg_id,
                f"📋 Вам назначена задача!\n\n{_task_text(task, show_assignee=False)}",
                reply_markup=kb, parse_mode="HTML",
            )
        except Exception:
            pass


# ── /task_group {role} title | deadline ──────────────────────────────────────

@router.message(Command("task_group"))
async def cmd_task_group(message: Message, staff: Staff | None = None):
    if staff is None or staff.role not in _ADMIN_ROLES:
        await message.answer("⛔ У вас нет прав для выполнения этой команды.")
        return
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer(
            "❌ Формат: /task_group {role} title | deadline\n"
            "Роли: counselor, educator, coach, ..."
        )
        return
    parts = args[1].split(maxsplit=1)
    role_str = parts[0]
    rest = parts[1] if len(parts) > 1 else ""
    try:
        role = StaffRole(role_str)
    except ValueError:
        await message.answer(f"❌ Неизвестная роль: {role_str}")
        return

    title_parts = [p.strip() for p in rest.split("|")]
    title = title_parts[0]
    deadline = None
    if len(title_parts) > 1:
        try:
            deadline = datetime.strptime(title_parts[1], "%d.%m.%Y %H:%M").replace(tzinfo=timezone.utc)
        except ValueError:
            try:
                deadline = datetime.strptime(title_parts[1], "%d.%m.%Y").replace(tzinfo=timezone.utc)
            except ValueError:
                pass

    async with async_session_factory() as session:
        active = await get_active_session(session)
        all_staff = await get_all_active_staff(session)
        targets = [s for s in all_staff if s.role == role]
        tasks = []
        for target in targets:
            t = await create_task(
                session, title=title, created_by=staff.id,
                session_id=active.id if active else None,
                assigned_to=target.id, group_role=role, deadline=deadline,
            )
            await add_task_log(session, t.id, staff.id, "created")
            tasks.append((t, target.telegram_id))

    await message.answer(
        f"✅ Создано <b>{len(tasks)}</b> задач для роли «{ROLE_LABELS.get(role, role)}»",
        parse_mode="HTML",
    )
    for task, tg_id in tasks:
        try:
            kb = _task_inline_kb(task.id, is_assignee=True)
            await message.bot.send_message(
                tg_id,
                f"📋 Вам назначена задача!\n\n{_task_text(task, show_assignee=False)}",
                reply_markup=kb, parse_mode="HTML",
            )
        except Exception:
            pass


# ── /mytasks ──────────────────────────────────────────────────────────────────

@router.message(Command("mytasks"))
async def cmd_mytasks(message: Message, staff: Staff | None = None):
    if staff is None:
        return
    async with async_session_factory() as session:
        tasks = await get_tasks_for_staff(session, staff.id)
    if not tasks:
        await message.answer("✅ У вас нет активных задач.")
        return
    lines = [f"📋 <b>Ваши задачи</b> ({len(tasks)}):\n"]
    for t in tasks:
        deadline_str = t.deadline.strftime(_DATE_FMT) if t.deadline else "—"
        lines.append(
            f"• <b>{t.title}</b> (ID: {t.id})\n"
            f"  {STATUS_LABELS[t.status]} | {PRIORITY_LABELS[t.priority]} | до {deadline_str}"
        )
    await message.answer(
        "\n\n".join(lines),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Обновить", callback_data="mytasks_refresh")]
        ]),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "mytasks_refresh")
async def cb_mytasks_refresh(callback: CallbackQuery, staff: Staff | None = None):
    if staff is None:
        await callback.answer()
        return
    async with async_session_factory() as session:
        tasks = await get_tasks_for_staff(session, staff.id)
    if not tasks:
        await callback.message.edit_text("✅ У вас нет активных задач.")
        await callback.answer()
        return
    lines = [f"📋 <b>Ваши задачи</b> ({len(tasks)}):\n"]
    for t in tasks:
        deadline_str = t.deadline.strftime(_DATE_FMT) if t.deadline else "—"
        lines.append(
            f"• <b>{t.title}</b> (ID: {t.id})\n"
            f"  {STATUS_LABELS[t.status]} | {PRIORITY_LABELS[t.priority]} | до {deadline_str}"
        )
    await callback.message.edit_text(
        "\n\n".join(lines),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Обновить", callback_data="mytasks_refresh")]
        ]),
        parse_mode="HTML",
    )
    await callback.answer()


# ── /done {id} ────────────────────────────────────────────────────────────────

@router.message(Command("done"))
async def cmd_done(message: Message, staff: Staff | None = None):
    if staff is None:
        return
    args = message.text.split(maxsplit=1)
    if len(args) < 2 or not args[1].strip().isdigit():
        await message.answer("❌ Формат: /done <id>")
        return
    task_id = int(args[1].strip())
    async with async_session_factory() as session:
        task = await get_task_by_id(session, task_id)
        if not task:
            await message.answer("❌ Задача не найдена.")
            return
        if task.assigned_to != staff.id and staff.role not in _ADMIN_ROLES:
            await message.answer("⛔ Это не ваша задача.")
            return
        task = await update_task_status(session, task_id, staff.id, TaskStatus.done, "marked done")
        creator_tg = None
        if task.creator and task.creator.id != staff.id:
            creator_tg = task.creator.telegram_id

    await message.answer(f"✔️ Задача <b>{task.title}</b> выполнена!", parse_mode="HTML")
    if creator_tg:
        try:
            await message.bot.send_message(
                creator_tg,
                f"✔️ Задача выполнена!\n\n{_task_text(task)}",
                parse_mode="HTML",
            )
        except Exception:
            pass


# ── Accept / Clarify callbacks ────────────────────────────────────────────────

@router.callback_query(F.data.startswith("task_accept:"))
async def cb_task_accept(callback: CallbackQuery, staff: Staff | None = None):
    task_id = int(callback.data.split(":")[1])
    async with async_session_factory() as session:
        task = await get_task_by_id(session, task_id)
        if not task or (task.assigned_to != staff.id and staff.role not in _ADMIN_ROLES):
            await callback.answer("⛔ Нет доступа", show_alert=True)
            return
        task = await update_task_status(session, task_id, staff.id, TaskStatus.accepted, "accepted")
    await callback.message.edit_text(
        f"✅ Задача принята!\n\n{_task_text(task, show_assignee=False)}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✔️ Выполнено", callback_data=f"task_done:{task_id}")]
        ]),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("task_clarify:"))
async def cb_task_clarify(callback: CallbackQuery, staff: Staff | None = None):
    task_id = int(callback.data.split(":")[1])
    async with async_session_factory() as session:
        task = await get_task_by_id(session, task_id)
        if not task:
            await callback.answer("❌ Задача не найдена", show_alert=True)
            return
        await add_task_log(session, task_id, staff.id, "requested clarification")
        creator_tg = task.creator.telegram_id if task.creator else None

    await callback.answer("❓ Запрос уточнения отправлен создателю")
    if creator_tg:
        try:
            await callback.bot.send_message(
                creator_tg,
                f"❓ Сотрудник {staff.full_name} запрашивает уточнение по задаче:\n\n{_task_text(task)}",
                parse_mode="HTML",
            )
        except Exception:
            pass


@router.callback_query(F.data.startswith("task_done:"))
async def cb_task_done(callback: CallbackQuery, staff: Staff | None = None):
    task_id = int(callback.data.split(":")[1])
    async with async_session_factory() as session:
        task = await get_task_by_id(session, task_id)
        if not task or (task.assigned_to != staff.id and staff.role not in _ADMIN_ROLES):
            await callback.answer("⛔ Нет доступа", show_alert=True)
            return
        task = await update_task_status(session, task_id, staff.id, TaskStatus.done, "marked done")
        creator_tg = task.creator.telegram_id if task.creator and task.creator.id != staff.id else None

    await callback.message.edit_text(f"✔️ Задача выполнена!\n\n{_task_text(task, show_assignee=False)}", parse_mode="HTML")
    await callback.answer()
    if creator_tg:
        try:
            await callback.bot.send_message(creator_tg, f"✔️ Задача выполнена!\n\n{_task_text(task)}", parse_mode="HTML")
        except Exception:
            pass


# ── Photo upload ──────────────────────────────────────────────────────────────

@router.message(F.photo & F.reply_to_message)
async def handle_task_photo(message: Message, staff: Staff | None = None):
    if staff is None:
        return
    # Check if replying to a task message by looking for "ID:" in the original
    reply_text = message.reply_to_message.text or message.reply_to_message.caption or ""
    task_id = None
    for part in reply_text.split():
        if part.startswith("ID:"):
            try:
                task_id = int(part[3:].rstrip(")"))
            except ValueError:
                pass
    if task_id is None:
        return

    photo = message.photo[-1]
    photo_url = photo.file_id  # store file_id as reference
    async with async_session_factory() as session:
        task = await get_task_by_id(session, task_id)
        if not task:
            return
        await add_task_photo(session, task_id, photo_url)
        await add_task_log(session, task_id, staff.id, "photo uploaded")
    await message.answer(f"📸 Фото прикреплено к задаче <b>{task.title}</b>.", parse_mode="HTML")


# ── /tasks_all ────────────────────────────────────────────────────────────────

@router.message(Command("tasks_all"))
async def cmd_tasks_all(message: Message, staff: Staff | None = None):
    if staff is None or staff.role not in _ADMIN_ROLES:
        await message.answer("⛔ У вас нет прав для выполнения этой команды.")
        return
    await _send_tasks_page(message, page=0)


@router.callback_query(F.data.startswith("tasks_page:"))
async def cb_tasks_page(callback: CallbackQuery, staff: Staff | None = None):
    if staff is None or staff.role not in _ADMIN_ROLES:
        await callback.answer("⛔ Нет прав", show_alert=True)
        return
    page = int(callback.data.split(":")[1])
    await _send_tasks_page(callback.message, page=page, edit=True)
    await callback.answer()


async def _send_tasks_page(message: Message, page: int, edit: bool = False):
    async with async_session_factory() as session:
        tasks, total = await get_all_tasks(session, offset=page * _PAGE_SIZE, limit=_PAGE_SIZE)
    total_pages = max(1, (total + _PAGE_SIZE - 1) // _PAGE_SIZE)
    lines = [f"📋 <b>Все задачи</b> (стр. {page + 1}/{total_pages})\n"]
    for t in tasks:
        lines.append(_task_text(t))
    text = "\n\n".join(lines)
    buttons = []
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="◀️", callback_data=f"tasks_page:{page - 1}"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton(text="▶️", callback_data=f"tasks_page:{page + 1}"))
    if nav:
        buttons.append(nav)
    kb = InlineKeyboardMarkup(inline_keyboard=buttons) if buttons else None
    if edit:
        await message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    else:
        await message.answer(text, reply_markup=kb, parse_mode="HTML")


# ── /tasks_pending ────────────────────────────────────────────────────────────

@router.message(Command("tasks_pending"))
async def cmd_tasks_pending(message: Message, staff: Staff | None = None):
    if staff is None or staff.role not in _ADMIN_ROLES:
        await message.answer("⛔ У вас нет прав для выполнения этой команды.")
        return
    async with async_session_factory() as session:
        tasks = await get_overdue_tasks(session)
    if not tasks:
        await message.answer("✅ Просроченных задач нет.")
        return
    lines = [f"⚠️ <b>Просроченные задачи</b> ({len(tasks)}):\n"]
    for t in tasks:
        lines.append(_task_text(t))
    await message.answer("\n\n".join(lines), parse_mode="HTML")


# ── /task_pause {id} {days} ───────────────────────────────────────────────────

@router.message(Command("task_pause"))
async def cmd_task_pause(message: Message, staff: Staff | None = None):
    if staff is None or staff.role not in _ADMIN_ROLES:
        await message.answer("⛔ У вас нет прав для выполнения этой команды.")
        return
    parts = message.text.split()
    if len(parts) < 3 or not parts[1].isdigit() or not parts[2].isdigit():
        await message.answer("❌ Формат: /task_pause <id> <дней>")
        return
    task_id, days = int(parts[1]), int(parts[2])
    from datetime import timedelta
    paused_until = (datetime.utcnow() + timedelta(days=days)).date()
    async with async_session_factory() as session:
        task = await update_task(session, task_id, paused_until=paused_until)
        if task:
            await add_task_log(session, task_id, staff.id, f"paused for {days} days")
    if not task:
        await message.answer("❌ Задача не найдена.")
        return
    await message.answer(f"⏸ Задача <b>{task.title}</b> приостановлена до {paused_until.strftime('%d.%m.%Y')}.", parse_mode="HTML")


# ── Templates ─────────────────────────────────────────────────────────────────

@router.message(Command("template_add"))
async def cmd_template_add(message: Message, state: FSMContext, staff: Staff | None = None):
    if staff is None or staff.role not in _ADMIN_ROLES:
        await message.answer("⛔ У вас нет прав для выполнения этой команды.")
        return
    await message.answer("📋 Создание шаблона\n\nВведите <b>название</b>:", reply_markup=_cancel_kb, parse_mode="HTML")
    await state.set_state(TemplateFSM.waiting_title)


@router.message(TemplateFSM.waiting_title)
async def fsm_tmpl_title(message: Message, state: FSMContext):
    await state.update_data(title=message.text.strip())
    await message.answer(
        "Введите <b>описание</b> (или пропустите):",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⏭ Пропустить", callback_data="tmpl_skip_desc")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_fsm")],
        ]),
        parse_mode="HTML",
    )
    await state.set_state(TemplateFSM.waiting_description)


@router.message(TemplateFSM.waiting_description)
async def fsm_tmpl_desc(message: Message, state: FSMContext):
    await state.update_data(description=message.text.strip())
    await _ask_tmpl_role(message, state)


@router.callback_query(TemplateFSM.waiting_description, F.data == "tmpl_skip_desc")
async def fsm_tmpl_skip_desc(callback: CallbackQuery, state: FSMContext):
    await state.update_data(description=None)
    await _ask_tmpl_role(callback.message, state, edit=True)
    await callback.answer()


async def _ask_tmpl_role(message: Message, state: FSMContext, edit: bool = False):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=lbl, callback_data=f"tmpl_role:{r.value}")]
        for r, lbl in ROLE_LABELS.items()
    ] + [[InlineKeyboardButton(text="⏭ Без роли", callback_data="tmpl_role:none"),
          InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_fsm")]])
    text = "Выберите <b>целевую роль</b> (или пропустите):"
    if edit:
        await message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    else:
        await message.answer(text, reply_markup=kb, parse_mode="HTML")
    await state.set_state(TemplateFSM.waiting_role)


@router.callback_query(TemplateFSM.waiting_role, F.data.startswith("tmpl_role:"))
async def fsm_tmpl_role(callback: CallbackQuery, state: FSMContext):
    val = callback.data.split(":")[1]
    role = StaffRole(val) if val != "none" else None
    await state.update_data(group_role=role.value if role else None)
    await callback.message.edit_text("Выберите <b>приоритет</b>:", reply_markup=_priority_kb, parse_mode="HTML")
    await state.set_state(TemplateFSM.waiting_priority)
    await callback.answer()


@router.callback_query(TemplateFSM.waiting_priority, F.data.startswith("task_prio:"))
async def fsm_tmpl_priority(callback: CallbackQuery, state: FSMContext):
    priority = TaskPriority(callback.data.split(":")[1])
    await state.update_data(priority=priority.value)
    await callback.message.edit_text(
        "Выберите <b>повторение</b>:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📅 Ежедневно", callback_data="tmpl_recur:daily"),
             InlineKeyboardButton(text="📆 Еженедельно", callback_data="tmpl_recur:weekly")],
            [InlineKeyboardButton(text="⏭ Без повторения", callback_data="tmpl_recur:none"),
             InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_fsm")],
        ]),
        parse_mode="HTML",
    )
    await state.set_state(TemplateFSM.waiting_recurrence)
    await callback.answer()


@router.callback_query(TemplateFSM.waiting_recurrence, F.data.startswith("tmpl_recur:"))
async def fsm_tmpl_recurrence(callback: CallbackQuery, state: FSMContext, staff: Staff | None = None):
    val = callback.data.split(":")[1]
    recurrence = RecurrenceType(val) if val != "none" else None
    data = await state.get_data()
    await state.clear()

    role_val = data.get("group_role")
    role = StaffRole(role_val) if role_val else None
    priority = TaskPriority(data.get("priority", "medium"))

    async with async_session_factory() as session:
        tmpl = await create_template(
            session, data["title"], data.get("description"),
            role, priority, recurrence,
        )

    await callback.message.edit_text(
        f"✅ Шаблон создан!\n\n"
        f"📋 <b>{tmpl.title}</b> (ID: {tmpl.id})\n"
        f"Приоритет: {PRIORITY_LABELS[tmpl.priority]}\n"
        f"Повторение: {tmpl.recurrence_type.value if tmpl.recurrence_type else '—'}",
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(Command("template_list"))
async def cmd_template_list(message: Message, staff: Staff | None = None):
    if staff is None or staff.role not in _ADMIN_ROLES:
        await message.answer("⛔ У вас нет прав для выполнения этой команды.")
        return
    async with async_session_factory() as session:
        templates = await get_all_templates(session)
    if not templates:
        await message.answer("📋 Шаблонов нет.")
        return
    lines = ["📋 <b>Шаблоны задач:</b>\n"]
    for t in templates:
        role_str = ROLE_LABELS.get(t.group_role, "—") if t.group_role else "—"
        recur_str = t.recurrence_type.value if t.recurrence_type else "—"
        lines.append(
            f"<b>{t.title}</b> (ID: {t.id})\n"
            f"  Роль: {role_str} | {PRIORITY_LABELS[t.priority]} | Повтор: {recur_str}"
        )
    await message.answer("\n\n".join(lines), parse_mode="HTML")


@router.message(Command("task_from_template"))
async def cmd_task_from_template(message: Message, staff: Staff | None = None):
    if staff is None or staff.role not in _ADMIN_ROLES:
        await message.answer("⛔ У вас нет прав для выполнения этой команды.")
        return
    parts = message.text.split()
    if len(parts) < 2 or not parts[1].isdigit():
        await message.answer("❌ Формат: /task_from_template <template_id>")
        return
    tmpl_id = int(parts[1])
    async with async_session_factory() as session:
        tmpl = await get_template_by_id(session, tmpl_id)
        if not tmpl:
            await message.answer("❌ Шаблон не найден.")
            return
        active = await get_active_session(session)
        is_recurring = tmpl.recurrence_type is not None
        task = await create_task(
            session, title=tmpl.title, description=tmpl.description,
            created_by=staff.id, session_id=active.id if active else None,
            group_role=tmpl.group_role, priority=tmpl.priority,
            is_recurring=is_recurring, recurrence_type=tmpl.recurrence_type,
            template_id=tmpl.id,
        )
        await add_task_log(session, task.id, staff.id, f"created from template {tmpl_id}")

        # Notify all matching role staff if group_role set
        notified = []
        if tmpl.group_role:
            all_staff = await get_all_active_staff(session)
            notified = [s for s in all_staff if s.role == tmpl.group_role]

    await message.answer(f"✅ Задача создана из шаблона!\n\n{_task_text(task)}", parse_mode="HTML")
    for target in notified:
        try:
            kb = _task_inline_kb(task.id, is_assignee=True)
            await message.bot.send_message(
                target.telegram_id,
                f"📋 Вам назначена задача!\n\n{_task_text(task, show_assignee=False)}",
                reply_markup=kb, parse_mode="HTML",
            )
        except Exception:
            pass
