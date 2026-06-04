from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.types import CallbackQuery, Message

from app.bot.keyboards import (
    calendar_menu,
    main_menu_kb,
    sessions_menu,
    squads_menu,
    staff_actions_menu,
    tasks_admin_menu,
    tasks_staff_menu,
)
from app.db.base import async_session_factory
from app.db.crud import get_active_session, get_schedule, log_action
from app.db.models import ROLE_LABELS, Staff, StaffRole
from app.config import settings

router = Router(name="start")

_onboarded: set[int] = set()

_ONBOARDING = {
    StaffRole.admin: "👋 Добро пожаловать, Администратор!\n\nИспользуйте кнопки меню внизу для управления лагерем.",
    StaffRole.senior_counselor: "👋 Добро пожаловать, Старший вожатый!\n\nИспользуйте кнопки меню внизу.",
    StaffRole.counselor: "👋 Добро пожаловать, Вожатый!\n\nИспользуйте кнопки меню внизу.",
    StaffRole.educator: "👋 Добро пожаловать, Воспитатель!\n\nИспользуйте кнопки меню внизу.",
    StaffRole.coach: "👋 Добро пожаловать, Тренер!\n\nИспользуйте кнопки меню внизу.",
    StaffRole.swim_coach: "👋 Добро пожаловать, Тренер по плаванию!\n\nИспользуйте кнопки меню внизу.",
    StaffRole.music: "👋 Добро пожаловать, Музыкальный руководитель!\n\nИспользуйте кнопки меню внизу.",
    StaffRole.circle_leader: "👋 Добро пожаловать, Руководитель кружка!\n\nИспользуйте кнопки меню внизу.",
}


def _get_menu_kb(staff: Staff):
    return main_menu_kb(staff.role, webapp_url=getattr(settings, "webapp_url", ""))


async def _show_main_menu(message: Message, staff: Staff):
    role_label = ROLE_LABELS.get(staff.role, str(staff.role))
    text = f"Привет, <b>{staff.full_name}</b>!\nВаша роль: {role_label}"
    await message.answer(text, reply_markup=_get_menu_kb(staff), parse_mode="HTML")


@router.message(CommandStart())
async def cmd_start(message: Message, staff: Staff | None = None):
    if staff is None:
        await message.answer(
            "❌ Вы не зарегистрированы в системе лагеря.\n"
            "Обратитесь к администратору для получения доступа."
        )
        return

    async with async_session_factory() as session:
        await log_action(session, staff.id, "login")

    is_new = staff.telegram_id not in _onboarded
    if is_new:
        _onboarded.add(staff.telegram_id)
        onboarding_text = _ONBOARDING.get(staff.role, "👋 Добро пожаловать!")
        await message.answer(onboarding_text)

    await _show_main_menu(message, staff)


# ── Кнопки нижнего меню (старые + совместимость) ──────────────────────────────

@router.message(F.text == "👥 Сотрудники")
async def menu_staff(message: Message, staff: Staff | None = None):
    if staff is None or staff.role not in {StaffRole.admin, StaffRole.senior_counselor}:
        return
    await message.answer("👥 <b>Управление сотрудниками</b>", reply_markup=staff_actions_menu(), parse_mode="HTML")


@router.message(F.text == "🏕 Отряды")
async def menu_squads(message: Message, staff: Staff | None = None):
    if staff is None or staff.role not in {StaffRole.admin, StaffRole.senior_counselor}:
        return
    await message.answer("🏕 <b>Управление отрядами</b>", reply_markup=squads_menu(), parse_mode="HTML")


@router.message(F.text == "🏕 Смены")
async def menu_sessions(message: Message, staff: Staff | None = None):
    if staff is None or staff.role not in {StaffRole.admin, StaffRole.senior_counselor}:
        return
    await message.answer("🏕 <b>Управление сменами</b>", reply_markup=sessions_menu(), parse_mode="HTML")


@router.message(F.text == "📅 Расписание")
async def menu_schedule(message: Message, staff: Staff | None = None):
    if staff is None:
        return
    if staff.role in {StaffRole.admin, StaffRole.senior_counselor}:
        await message.answer("📅 <b>Расписание</b>", reply_markup=sessions_menu(), parse_mode="HTML")
    else:
        async with async_session_factory() as session:
            active = await get_active_session(session)
            if not active:
                await message.answer("❌ Нет активной смены.")
                return
            items = await get_schedule(session, active.id)
        from app.bot.handlers.sessions import _format_schedule
        await message.answer(_format_schedule(active.name, items), parse_mode="HTML")


@router.message(F.text == "🗓 Календарь")
async def menu_calendar_old(message: Message, staff: Staff | None = None):
    if staff is None:
        return
    await message.answer("🗓 <b>Календарь мероприятий</b>", reply_markup=calendar_menu(), parse_mode="HTML")


@router.message(F.text == "✅ Задачи")
async def menu_tasks_old(message: Message, staff: Staff | None = None):
    if staff is None:
        return
    if staff.role in {StaffRole.admin, StaffRole.senior_counselor}:
        await message.answer("✅ <b>Управление задачами</b>", reply_markup=tasks_admin_menu(), parse_mode="HTML")
    else:
        await message.answer("✅ <b>Мои задачи</b>", reply_markup=tasks_staff_menu(), parse_mode="HTML")


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


# ── Навигация из инлайн меню ──────────────────────────────────────────────────

@router.callback_query(F.data == "tasks_back")
async def cb_tasks_back(callback: CallbackQuery, staff: Staff | None = None):
    if staff and staff.role in {StaffRole.admin, StaffRole.senior_counselor}:
        await callback.message.edit_text("✅ <b>Задачи</b>", reply_markup=tasks_admin_menu(), parse_mode="HTML")
    elif staff:
        await callback.message.edit_text("✅ <b>Мои задачи</b>", reply_markup=tasks_staff_menu(), parse_mode="HTML")
    await callback.answer()
