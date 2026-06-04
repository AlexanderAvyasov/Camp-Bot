from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    WebAppInfo,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.db.models import (
    PRIORITY_LABELS,
    ROLE_LABELS,
    StaffRole,
    TaskPriority,
    TaskStatus,
)


# ── Динамическое главное меню ─────────────────────────────────────────────────

def _webapp_btn(webapp_url: str) -> KeyboardButton:
    if webapp_url:
        return KeyboardButton(text="🌐 Mini App", web_app=WebAppInfo(url=webapp_url))
    return KeyboardButton(text="🌐 Mini App")


def main_menu_kb(role: StaffRole, webapp_url: str = "") -> ReplyKeyboardMarkup:
    wa = _webapp_btn(webapp_url)
    if role in (StaffRole.admin, StaffRole.senior_counselor):
        keyboard = [
            [KeyboardButton(text="👥 Сотрудники"), KeyboardButton(text="📋 Задачи")],
            [KeyboardButton(text="📅 Календарь"), KeyboardButton(text="📣 Объявления")],
            [KeyboardButton(text="👦 Дети"), KeyboardButton(text="📊 Аналитика")],
            [KeyboardButton(text="⚙️ Управление"), wa],
        ]
    elif role in (StaffRole.counselor, StaffRole.educator):
        keyboard = [
            [KeyboardButton(text="📋 Мои задачи"), KeyboardButton(text="📅 Расписание")],
            [KeyboardButton(text="👦 Мой отряд"), KeyboardButton(text="🚨 Инцидент")],
            [KeyboardButton(text="🔄 Дежурство"), KeyboardButton(text="📝 Чек-лист")],
            [wa],
        ]
    elif role in (StaffRole.coach, StaffRole.swim_coach, StaffRole.music):
        keyboard = [
            [KeyboardButton(text="📋 Мои задачи"), KeyboardButton(text="📅 Расписание")],
            [KeyboardButton(text="🚨 Инцидент"), wa],
        ]
    elif role == StaffRole.circle_leader:
        keyboard = [
            [KeyboardButton(text="📋 Мои задачи"), KeyboardButton(text="🧩 Мой кружок")],
            [KeyboardButton(text="✅ Посещаемость"), wa],
        ]
    else:
        keyboard = [
            [KeyboardButton(text="📋 Мои задачи"), wa],
        ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True, persistent=True)


# ── Inline-хелперы меню ───────────────────────────────────────────────────────

def back_btn(callback_data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text="← Назад", callback_data=callback_data)


def tasks_submenu_kb(is_admin: bool) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text="📋 Мои задачи", callback_data="menu_my_tasks:0")]]
    if is_admin:
        rows.append([InlineKeyboardButton(text="➕ Создать задачу", callback_data="task_create")])
        rows.append([InlineKeyboardButton(text="📊 Все задачи", callback_data="menu_all_tasks:all:0")])
        rows.append([InlineKeyboardButton(text="📁 Шаблоны", callback_data="templates_list:0")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def calendar_submenu_kb(is_admin: bool) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text="📅 Сегодня", callback_data="cal:today"),
         InlineKeyboardButton(text="📆 Неделя", callback_data="cal:week")],
        [InlineKeyboardButton(text="👤 Мой график", callback_data="cal:my")],
    ]
    if is_admin:
        rows.append([InlineKeyboardButton(text="➕ Новое мероприятие", callback_data="event_add")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def children_submenu_kb(has_squad: bool = False) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text="🔍 Поиск ребёнка", callback_data="ch_search")],
    ]
    if has_squad:
        rows.append([InlineKeyboardButton(text="👦 Мой отряд", callback_data="ch_my_squad")])
    rows.append([InlineKeyboardButton(text="🎂 Именинники", callback_data="ch_birthdays")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def duties_submenu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Моё дежурство", callback_data="duty_my")],
        [InlineKeyboardButton(text="📍 Отметка", callback_data="duty_checkpoint")],
        [InlineKeyboardButton(text="✅ Сдать дежурство", callback_data="duty_complete")],
        [InlineKeyboardButton(text="🚨 Тревога", callback_data="duty_alarm_now")],
    ])


def checklists_submenu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Перед мероприятием", callback_data="cl_start:pre_event")],
        [InlineKeyboardButton(text="🌙 Отбой", callback_data="cl_start:lights_out")],
    ])


def announcements_submenu_kb(is_admin: bool) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text="📣 Новые объявления", callback_data="ann_unread")],
        [InlineKeyboardButton(text="📜 История", callback_data="ann_history:0")],
    ]
    if is_admin:
        rows.append([InlineKeyboardButton(text="➕ Создать объявление", callback_data="announce_create")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def analytics_submenu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👤 По сотруднику", callback_data="analytics_staff")],
        [InlineKeyboardButton(text="🏕 По смене", callback_data="analytics_session")],
        [InlineKeyboardButton(text="📋 Отчёт Excel", callback_data="analytics_excel")],
    ])


def management_submenu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👥 Сотрудники", callback_data="staff_list:0")],
        [InlineKeyboardButton(text="🏕 Отряды", callback_data="squad_list")],
        [InlineKeyboardButton(text="🔄 Дежурства", callback_data="duty_admin_view")],
        [InlineKeyboardButton(text="🏕 Смены", callback_data="session_list")],
        [InlineKeyboardButton(text="📁 Импорт детей", callback_data="mgmt_import")],
    ])


def task_menu_filter_kb(current: str) -> InlineKeyboardMarkup:
    filters = [("all", "Все"), ("new", "Новые"), ("in_progress", "В работе"), ("overdue", "Просрочены")]
    rows = [[InlineKeyboardButton(
        text=f"{'✓ ' if current == k else ''}{label}",
        callback_data=f"menu_all_tasks:{k}:0"
    ) for k, label in filters]]
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ── Постоянное меню снизу ─────────────────────────────────────────────────────

def admin_reply_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="👥 Сотрудники"), KeyboardButton(text="🏕 Смены")],
            [KeyboardButton(text="🏕 Отряды"), KeyboardButton(text="📅 Расписание")],
            [KeyboardButton(text="✅ Задачи"), KeyboardButton(text="🗓 Календарь")],
            [KeyboardButton(text="👦 Дети"), KeyboardButton(text="👤 Мой профиль")],
        ],
        resize_keyboard=True,
        persistent=True,
    )


def staff_reply_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="✅ Задачи"), KeyboardButton(text="🗓 Календарь")],
            [KeyboardButton(text="👦 Дети"), KeyboardButton(text="📅 Расписание")],
            [KeyboardButton(text="👤 Мой профиль")],
        ],
        resize_keyboard=True,
        persistent=True,
    )


def remove_reply_menu() -> ReplyKeyboardRemove:
    return ReplyKeyboardRemove()


# ── Общие кнопки ─────────────────────────────────────────────────────────────

def cancel_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_fsm")]]
    )


def skip_cancel_kb(skip_data: str = "skip") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⏭ Пропустить", callback_data=skip_data)],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_fsm")],
        ]
    )


def confirm_kb(yes_data: str, no_data: str = "cancel_fsm") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(text="✅ Да", callback_data=yes_data),
            InlineKeyboardButton(text="❌ Нет", callback_data=no_data),
        ]]
    )


def pagination_keyboard(page: int, total_pages: int, prefix: str = "staff_list") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if page > 0:
        builder.button(text="◀️", callback_data=f"{prefix}:{page - 1}")
    if page < total_pages - 1:
        builder.button(text="▶️", callback_data=f"{prefix}:{page + 1}")
    builder.adjust(2)
    return builder.as_markup()


# ── Сотрудники ────────────────────────────────────────────────────────────────

def staff_actions_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📋 Список сотрудников", callback_data="staff_list:0")],
            [InlineKeyboardButton(text="➕ Добавить сотрудника", callback_data="add_staff")],
        ]
    )


def role_menu(prefix: str = "set_role") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for role in StaffRole:
        builder.button(text=ROLE_LABELS[role], callback_data=f"{prefix}:{role.value}")
    builder.adjust(2)
    builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_fsm"))
    return builder.as_markup()


def staff_edit_role_keyboard(staff_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for role in StaffRole:
        builder.button(text=ROLE_LABELS[role], callback_data=f"edit_role:{staff_id}:{role.value}")
    builder.adjust(2)
    return builder.as_markup()


def staff_item_kb(staff_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✏️ Изменить роль", callback_data=f"edit_role_prompt:{staff_id}")],
            [InlineKeyboardButton(text="🗑 Деактивировать", callback_data=f"deactivate_staff:{staff_id}")],
            [InlineKeyboardButton(text="◀️ К списку", callback_data="staff_list:0")],
        ]
    )


# ── Смены ─────────────────────────────────────────────────────────────────────

def sessions_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📋 Список смен", callback_data="session_list")],
            [InlineKeyboardButton(text="➕ Новая смена", callback_data="session_new")],
            [InlineKeyboardButton(text="📅 Просмотр расписания", callback_data="schedule_view")],
            [InlineKeyboardButton(text="➕ Добавить в расписание", callback_data="schedule_add")],
        ]
    )


def session_item_kb(session_id: int, is_active: bool) -> InlineKeyboardMarkup:
    rows = []
    if not is_active:
        rows.append([InlineKeyboardButton(text="▶️ Активировать", callback_data=f"session_activate:{session_id}")])
    rows.append([InlineKeyboardButton(text="📅 Расписание", callback_data=f"schedule_view:{session_id}")])
    rows.append([InlineKeyboardButton(text="◀️ К списку", callback_data="session_list")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def day_type_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📅 Будний день", callback_data="sched_day:weekday")],
            [InlineKeyboardButton(text="🎉 Выходной день", callback_data="sched_day:weekend")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_fsm")],
        ]
    )


def schedule_add_more_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="➕ Добавить ещё", callback_data="schedule_add")],
            [InlineKeyboardButton(text="✅ Готово", callback_data="schedule_done")],
        ]
    )


def schedule_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="👁 Расписание", callback_data="schedule_view")],
            [InlineKeyboardButton(text="➕ Добавить", callback_data="schedule_add")],
        ]
    )


# ── Отряды ────────────────────────────────────────────────────────────────────

def squads_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📋 Список отрядов", callback_data="squad_list")],
            [InlineKeyboardButton(text="➕ Новый отряд", callback_data="squad_new")],
            [InlineKeyboardButton(text="🔍 Найти замену", callback_data="find_replacement")],
        ]
    )


def squad_item_kb(squad_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✏️ Редактировать", callback_data=f"squad_edit:{squad_id}")],
            [InlineKeyboardButton(text="🗑 Удалить", callback_data=f"squad_del_confirm:{squad_id}")],
            [InlineKeyboardButton(text="◀️ К списку", callback_data="squad_list")],
        ]
    )


def squad_edit_field_kb(squad_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📝 Название", callback_data=f"squad_field:{squad_id}:name")],
            [InlineKeyboardButton(text="🧑 Вожатый", callback_data=f"squad_field:{squad_id}:counselor")],
            [InlineKeyboardButton(text="👩 Воспитатель 1", callback_data=f"squad_field:{squad_id}:educator")],
            [InlineKeyboardButton(text="👩 Воспитатель 2", callback_data=f"squad_field:{squad_id}:educator_2")],
            [InlineKeyboardButton(text="◀️ Назад", callback_data=f"squad_view:{squad_id}")],
        ]
    )


def find_replacement_role_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    roles = [StaffRole.counselor, StaffRole.educator, StaffRole.coach,
             StaffRole.swim_coach, StaffRole.music, StaffRole.circle_leader]
    for role in roles:
        builder.button(text=ROLE_LABELS[role], callback_data=f"replacement_role:{role.value}")
    builder.adjust(2)
    builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_fsm"))
    return builder.as_markup()


# ── Задачи ────────────────────────────────────────────────────────────────────

def tasks_admin_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="➕ Создать задачу", callback_data="task_create")],
            [InlineKeyboardButton(text="📋 Все задачи", callback_data="tasks_all:0")],
            [InlineKeyboardButton(text="⚠️ Просроченные", callback_data="tasks_overdue:0")],
            [InlineKeyboardButton(text="⏸ Поставить задачу на паузу", callback_data="task_pause_menu")],
            [InlineKeyboardButton(text="📝 Шаблоны", callback_data="templates_list:0")],
            [InlineKeyboardButton(text="➕ Новый шаблон", callback_data="template_new")],
        ]
    )


def tasks_staff_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📋 Мои задачи", callback_data="my_tasks:0")],
        ]
    )


def task_group_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for role in StaffRole:
        if role != StaffRole.admin:
            builder.button(text=ROLE_LABELS[role], callback_data=f"task_group:{role.value}")
    builder.adjust(2)
    builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_fsm"))
    return builder.as_markup()


def task_assignee_kb(staff_list: list, role_value: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="👥 Для всей группы", callback_data=f"task_assignee:group:{role_value}")
    for s in staff_list:
        builder.button(text=f"👤 {s.full_name}", callback_data=f"task_assignee:{s.id}:{role_value}")
    builder.adjust(1)
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="task_create"))
    return builder.as_markup()


def task_priority_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=lbl, callback_data=f"task_priority:{p.value}")]
            for p, lbl in PRIORITY_LABELS.items()
        ] + [[InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_fsm")]]
    )


def task_deadline_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⏭ Без дедлайна", callback_data="task_deadline:skip")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_fsm")],
        ]
    )


def task_action_kb(task_id: int, status: TaskStatus, is_assignee: bool) -> InlineKeyboardMarkup | None:
    rows = []
    if is_assignee:
        if status == TaskStatus.new:
            rows.append([InlineKeyboardButton(text="✅ Принять", callback_data=f"task_accept:{task_id}")])
        if status in (TaskStatus.new, TaskStatus.accepted):
            rows.append([InlineKeyboardButton(text="🔄 В работу", callback_data=f"task_inprogress:{task_id}")])
        if status != TaskStatus.done:
            rows.append([InlineKeyboardButton(text="✔️ Выполнено", callback_data=f"task_done:{task_id}")])
            rows.append([InlineKeyboardButton(text="❓ Уточнить", callback_data=f"task_clarify:{task_id}")])
    return InlineKeyboardMarkup(inline_keyboard=rows) if rows else None


def task_admin_action_kb(task_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⏸ Пауза", callback_data=f"task_pause_start:{task_id}"),
             InlineKeyboardButton(text="🗑 Удалить", callback_data=f"task_del_confirm:{task_id}")],
        ]
    )


def template_item_kb(tmpl_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="▶️ Создать задачу из шаблона", callback_data=f"task_from_template:{tmpl_id}")],
            [InlineKeyboardButton(text="◀️ К шаблонам", callback_data="templates_list:0")],
        ]
    )


def template_recurrence_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📅 Ежедневно", callback_data="tmpl_recur:daily")],
            [InlineKeyboardButton(text="📅 Еженедельно", callback_data="tmpl_recur:weekly")],
            [InlineKeyboardButton(text="⏭ Без повторения", callback_data="tmpl_recur:none")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_fsm")],
        ]
    )


# ── Календарь / мероприятия ───────────────────────────────────────────────────

def calendar_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📅 Сегодня", callback_data="cal:today"),
                InlineKeyboardButton(text="📆 Неделя", callback_data="cal:week"),
            ],
            [InlineKeyboardButton(text="👤 Мой график", callback_data="cal:my")],
            [InlineKeyboardButton(text="➕ Новое мероприятие", callback_data="event_add")],
        ]
    )


def event_type_kb() -> InlineKeyboardMarkup:
    from app.db.models import EVENT_TYPE_LABELS
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=lbl, callback_data=f"ev_type:{t.value}")]
            for t, lbl in EVENT_TYPE_LABELS.items()
        ] + [[InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_fsm")]]
    )


def event_action_kb(event_id: int, is_admin: bool) -> InlineKeyboardMarkup | None:
    rows = []
    if is_admin:
        rows.append([
            InlineKeyboardButton(text="✏️ Редактировать", callback_data=f"event_edit_start:{event_id}"),
            InlineKeyboardButton(text="🗑 Удалить", callback_data=f"event_del_confirm:{event_id}"),
        ])
        rows.append([InlineKeyboardButton(text="📋 Копировать", callback_data=f"event_copy_start:{event_id}")])
    return InlineKeyboardMarkup(inline_keyboard=rows) if rows else None


def event_edit_field_kb(event_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📝 Название", callback_data=f"ev_field:{event_id}:title")],
            [InlineKeyboardButton(text="📍 Место", callback_data=f"ev_field:{event_id}:location")],
            [InlineKeyboardButton(text="🕐 Начало", callback_data=f"ev_field:{event_id}:start")],
            [InlineKeyboardButton(text="🕑 Конец", callback_data=f"ev_field:{event_id}:end")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_fsm")],
        ]
    )


# ── Совместимость со старым кодом ─────────────────────────────────────────────

def admin_main_menu() -> InlineKeyboardMarkup:
    return staff_actions_menu()


def staff_main_menu(role_label: str = "") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[])


def staff_list_empty_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="➕ Добавить сотрудника", callback_data="add_staff")],
        ]
    )


def confirm_keyboard(yes_data: str, no_data: str = "cancel_fsm") -> InlineKeyboardMarkup:
    return confirm_kb(yes_data, no_data)
