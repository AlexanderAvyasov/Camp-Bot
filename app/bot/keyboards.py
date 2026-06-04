from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.db.models import ROLE_LABELS, StaffRole


# ── Постоянное меню снизу ─────────────────────────────────────────────────────

def admin_reply_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="👥 Сотрудники"), KeyboardButton(text="🏕 Смены")],
            [KeyboardButton(text="🏕 Отряды"), KeyboardButton(text="📅 Расписание")],
            [KeyboardButton(text="✅ Задачи"), KeyboardButton(text="👤 Мой профиль")],
        ],
        resize_keyboard=True,
        persistent=True,
    )


def tasks_admin_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📋 Все задачи", callback_data="tasks_all_btn")],
            [InlineKeyboardButton(text="⚠️ Просроченные", callback_data="tasks_pending_btn")],
            [InlineKeyboardButton(text="📝 Шаблоны", callback_data="templates_list_btn")],
        ]
    )


def tasks_staff_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📋 Мои задачи", callback_data="mytasks_btn")],
        ]
    )


def squads_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📋 Список отрядов", callback_data="squad_list")],
            [InlineKeyboardButton(text="➕ Новый отряд", callback_data="squad_new")],
            [InlineKeyboardButton(text="🔍 Найти замену", callback_data="find_replacement")],
        ]
    )


def staff_reply_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="✅ Задачи"), KeyboardButton(text="📅 Расписание")],
            [KeyboardButton(text="👤 Мой профиль")],
        ],
        resize_keyboard=True,
        persistent=True,
    )


def remove_reply_menu() -> ReplyKeyboardRemove:
    return ReplyKeyboardRemove()


# ── Inline-клавиатуры ─────────────────────────────────────────────────────────

def back_button(callback_data: str = "main_menu") -> list[InlineKeyboardButton]:
    return [InlineKeyboardButton(text="◀️ Назад", callback_data=callback_data)]


def role_menu(prefix: str = "set_role") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for role in StaffRole:
        builder.button(text=ROLE_LABELS[role], callback_data=f"{prefix}:{role.value}")
    builder.adjust(2)
    builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_fsm"))
    return builder.as_markup()


def staff_actions_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📋 Список сотрудников", callback_data="staff_list:0")],
            [InlineKeyboardButton(text="➕ Добавить сотрудника", callback_data="add_staff")],
        ]
    )


def sessions_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📋 Список смен", callback_data="session_list")],
            [InlineKeyboardButton(text="➕ Новая смена", callback_data="session_new")],
            [InlineKeyboardButton(text="📅 Расписание", callback_data="schedule_view")],
        ]
    )


def schedule_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="👁 Просмотр расписания", callback_data="schedule_view")],
            [InlineKeyboardButton(text="➕ Добавить мероприятие", callback_data="schedule_add")],
        ]
    )


def pagination_keyboard(page: int, total_pages: int, prefix: str = "staff_list") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if page > 0:
        builder.button(text="◀️ Назад", callback_data=f"{prefix}:{page - 1}")
    if page < total_pages - 1:
        builder.button(text="Вперёд ▶️", callback_data=f"{prefix}:{page + 1}")
    builder.adjust(2)
    return builder.as_markup()


def confirm_keyboard(yes_data: str, no_data: str = "cancel") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Да", callback_data=yes_data),
                InlineKeyboardButton(text="❌ Нет", callback_data=no_data),
            ]
        ]
    )


def staff_edit_role_keyboard(staff_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for role in StaffRole:
        builder.button(text=ROLE_LABELS[role], callback_data=f"edit_role:{staff_id}:{role.value}")
    builder.adjust(2)
    return builder.as_markup()


def staff_list_empty_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="➕ Добавить сотрудника", callback_data="add_staff")],
        ]
    )


# Оставляем для совместимости со старым кодом
def admin_main_menu() -> InlineKeyboardMarkup:
    return staff_actions_menu()


def staff_main_menu(role_label: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[])
