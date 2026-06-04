from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.types import Message

from app.bot.keyboards import (
    admin_reply_menu,
    schedule_menu,
    sessions_menu,
    squads_menu,
    staff_reply_menu,
    staff_actions_menu,
    tasks_admin_menu,
    tasks_staff_menu,
)
from app.bot.texts import ONBOARDING
from app.db.models import ROLE_LABELS, Staff, StaffRole

router = Router(name="start")

_onboarded: set[int] = set()


async def _show_main_menu(message: Message, staff: Staff):
    role_label = ROLE_LABELS.get(staff.role, str(staff.role))
    text = f"Привет, <b>{staff.full_name}</b>!\nВаша роль: {role_label}"
    if staff.role == StaffRole.admin:
        await message.answer(text, reply_markup=admin_reply_menu(), parse_mode="HTML")
    else:
        await message.answer(text, reply_markup=staff_reply_menu(), parse_mode="HTML")


@router.message(CommandStart())
async def cmd_start(message: Message, staff: Staff | None = None):
    if staff is None:
        await message.answer(
            "❌ Вы не зарегистрированы в системе лагеря.\n"
            "Обратитесь к администратору для получения доступа."
        )
        return

    is_new = staff.telegram_id not in _onboarded
    if is_new:
        _onboarded.add(staff.telegram_id)
        onboarding_text = ONBOARDING.get(staff.role, "👋 Добро пожаловать!")
        await message.answer(onboarding_text)

    await _show_main_menu(message, staff)


# ── Кнопки нижнего меню ───────────────────────────────────────────────────────

@router.message(F.text == "👥 Сотрудники")
async def menu_staff(message: Message, staff: Staff | None = None):
    if staff is None or staff.role != StaffRole.admin:
        return
    await message.answer("👥 Управление сотрудниками:", reply_markup=staff_actions_menu())


@router.message(F.text == "🏕 Отряды")
async def menu_squads(message: Message, staff: Staff | None = None):
    if staff is None or staff.role != StaffRole.admin:
        return
    await message.answer("🏕 Управление отрядами:", reply_markup=squads_menu())


@router.message(F.text == "🏕 Смены")
async def menu_sessions(message: Message, staff: Staff | None = None):
    if staff is None or staff.role != StaffRole.admin:
        return
    await message.answer("🏕 Управление сменами:", reply_markup=sessions_menu())


@router.message(F.text == "📅 Расписание")
async def menu_schedule(message: Message, staff: Staff | None = None):
    if staff is None:
        return
    if staff.role == StaffRole.admin:
        await message.answer("📅 Расписание:", reply_markup=schedule_menu())
    else:
        # Для не-админов сразу показываем расписание активной смены
        from app.db.base import async_session_factory
        from app.db.crud import get_active_session, get_schedule
        async with async_session_factory() as session:
            active = await get_active_session(session)
            if not active:
                await message.answer("❌ Нет активной смены.")
                return
            items = await get_schedule(session, active.id)
        from app.bot.handlers.sessions import _format_schedule
        await message.answer(_format_schedule(active.name, items), parse_mode="HTML")


@router.message(F.text == "🗓 Календарь")
async def menu_calendar(message: Message, staff: Staff | None = None):
    if staff is None:
        return
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
    await message.answer(
        "🗓 Календарь мероприятий",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="📅 Сегодня", callback_data="cal:today"),
                InlineKeyboardButton(text="📆 Неделя", callback_data="cal:week"),
            ],
            [InlineKeyboardButton(text="👤 Мой график", callback_data="cal:my")],
        ]),
    )


@router.message(F.text == "✅ Задачи")
async def menu_tasks(message: Message, staff: Staff | None = None):
    if staff is None:
        return
    if staff.role == StaffRole.admin:
        await message.answer("✅ Управление задачами:", reply_markup=tasks_admin_menu())
    else:
        await message.answer("✅ Мои задачи:", reply_markup=tasks_staff_menu())


@router.message(F.text == "👤 Мой профиль")
async def menu_profile(message: Message, staff: Staff | None = None):
    if staff is None:
        return
    role_label = ROLE_LABELS.get(staff.role, str(staff.role))
    squad_info = f"\nОтряд: {staff.squad.name}" if staff.squad else ""
    await message.answer(
        f"👤 <b>{staff.full_name}</b>\n"
        f"Роль: {role_label}{squad_info}\n"
        f"Telegram ID: <code>{staff.telegram_id}</code>",
        parse_mode="HTML",
    )
