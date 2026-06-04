from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.db.models import ROLE_LABELS, StaffRole


def role_menu(prefix: str = "set_role") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for role in StaffRole:
        builder.button(text=ROLE_LABELS[role], callback_data=f"{prefix}:{role.value}")
    builder.adjust(2)
    return builder.as_markup()


def admin_main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="👥 Список сотрудников", callback_data="staff_list:0")],
            [InlineKeyboardButton(text="➕ Добавить сотрудника", callback_data="add_staff")],
        ]
    )


def staff_main_menu(role_label: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"👤 Моя роль: {role_label}", callback_data="my_profile")],
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
