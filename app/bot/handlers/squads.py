from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from app.bot.states import SquadEditFSM, SquadNewFSM
from app.db.base import async_session_factory
from app.db.crud import (
    create_squad,
    get_all_squads,
    get_free_staff_by_role,
    get_squad_by_id,
    get_staff_by_id,
    get_staff_by_telegram_id,
    update_squad,
)
from app.db.models import ROLE_LABELS, Staff, StaffRole

router = Router(name="squads")

_COUNSELOR_ROLES = {StaffRole.counselor, StaffRole.senior_counselor}
_EDUCATOR_ROLES = {StaffRole.educator}

_cancel_kb = InlineKeyboardMarkup(
    inline_keyboard=[[InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_fsm")]]
)

_skip_cancel_kb = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="⏭ Пропустить", callback_data="squad_skip")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_fsm")],
    ]
)


def _squad_text(squad) -> str:
    counselor = squad.counselor.full_name if squad.counselor else "—"
    educator = squad.educator.full_name if squad.educator else "—"
    members = [m for m in squad.members if m.id not in {squad.counselor_id, squad.educator_id}]
    return (
        f"🏕 <b>{squad.name}</b> (ID: {squad.id})\n"
        f"  Вожатый: {counselor}\n"
        f"  Воспитатель: {educator}\n"
        f"  Детей: {len(members)}"
    )


def _require_admin(staff: Staff | None) -> bool:
    return staff is not None and staff.role == StaffRole.admin


# ── /squad_new ────────────────────────────────────────────────────────────────

@router.message(Command("squad_new"))
async def cmd_squad_new(message: Message, state: FSMContext, staff: Staff | None = None):
    if not _require_admin(staff):
        await message.answer("⛔ У вас нет прав для выполнения этой команды.")
        return
    await message.answer(
        "🏕 Создание отряда\n\nВведите <b>название</b> отряда:",
        reply_markup=_cancel_kb, parse_mode="HTML",
    )
    await state.set_state(SquadNewFSM.waiting_name)


@router.message(SquadNewFSM.waiting_name)
async def fsm_squad_name(message: Message, state: FSMContext):
    name = message.text.strip()
    if len(name) < 1:
        await message.answer("❌ Название слишком короткое. Введите ещё раз:", reply_markup=_cancel_kb)
        return
    await state.update_data(name=name)
    await message.answer(
        "Введите <b>Telegram ID вожатого</b> (или пропустите):",
        reply_markup=_skip_cancel_kb, parse_mode="HTML",
    )
    await state.set_state(SquadNewFSM.waiting_counselor)


@router.message(SquadNewFSM.waiting_counselor)
async def fsm_squad_counselor(message: Message, state: FSMContext):
    text = message.text.strip()
    if not text.isdigit():
        await message.answer("❌ Введите числовой Telegram ID:", reply_markup=_skip_cancel_kb)
        return
    async with async_session_factory() as session:
        person = await get_staff_by_telegram_id(session, int(text))
    if not person:
        await message.answer("❌ Сотрудник не найден. Введите ещё раз:", reply_markup=_skip_cancel_kb)
        return
    if person.role not in _COUNSELOR_ROLES:
        await message.answer(
            f"❌ У сотрудника роль «{ROLE_LABELS[person.role]}», а нужна роль вожатого. Введите другой ID:",
            reply_markup=_skip_cancel_kb, parse_mode="HTML",
        )
        return
    await state.update_data(counselor_id=person.id, counselor_name=person.full_name)
    await message.answer(
        f"✅ Вожатый: <b>{person.full_name}</b>\n\nВведите <b>Telegram ID воспитателя</b> (или пропустите):",
        reply_markup=_skip_cancel_kb, parse_mode="HTML",
    )
    await state.set_state(SquadNewFSM.waiting_educator)


@router.callback_query(SquadNewFSM.waiting_counselor, F.data == "squad_skip")
async def fsm_squad_counselor_skip(callback: CallbackQuery, state: FSMContext):
    await state.update_data(counselor_id=None)
    await callback.message.edit_text(
        "Введите <b>Telegram ID воспитателя</b> (или пропустите):",
        reply_markup=_skip_cancel_kb, parse_mode="HTML",
    )
    await state.set_state(SquadNewFSM.waiting_educator)
    await callback.answer()


@router.message(SquadNewFSM.waiting_educator)
async def fsm_squad_educator(message: Message, state: FSMContext):
    text = message.text.strip()
    if not text.isdigit():
        await message.answer("❌ Введите числовой Telegram ID:", reply_markup=_skip_cancel_kb)
        return
    async with async_session_factory() as session:
        person = await get_staff_by_telegram_id(session, int(text))
    if not person:
        await message.answer("❌ Сотрудник не найден. Введите ещё раз:", reply_markup=_skip_cancel_kb)
        return
    if person.role not in _EDUCATOR_ROLES:
        await message.answer(
            f"❌ У сотрудника роль «{ROLE_LABELS[person.role]}», а нужна роль воспитателя. Введите другой ID:",
            reply_markup=_skip_cancel_kb, parse_mode="HTML",
        )
        return
    await state.update_data(educator_id=person.id, educator_name=person.full_name)
    await _finish_squad_creation(message, state)


@router.callback_query(SquadNewFSM.waiting_educator, F.data == "squad_skip")
async def fsm_squad_educator_skip(callback: CallbackQuery, state: FSMContext):
    await state.update_data(educator_id=None)
    await _finish_squad_creation(callback.message, state, edit=True)
    await callback.answer()


async def _finish_squad_creation(message: Message, state: FSMContext, edit: bool = False):
    data = await state.get_data()
    await state.clear()
    async with async_session_factory() as session:
        squad = await create_squad(
            session,
            data["name"],
            counselor_id=data.get("counselor_id"),
            educator_id=data.get("educator_id"),
        )
    counselor = data.get("counselor_name", "—")
    educator = data.get("educator_name", "—")
    text = (
        f"✅ Отряд создан!\n\n"
        f"🏕 <b>{squad.name}</b> (ID: {squad.id})\n"
        f"  Вожатый: {counselor}\n"
        f"  Воспитатель: {educator}"
    )
    if edit:
        await message.edit_text(text, parse_mode="HTML")
    else:
        await message.answer(text, parse_mode="HTML")


# ── /squad_list ───────────────────────────────────────────────────────────────

@router.message(Command("squad_list"))
async def cmd_squad_list(message: Message, staff: Staff | None = None):
    if not _require_admin(staff):
        await message.answer("⛔ У вас нет прав для выполнения этой команды.")
        return
    await _send_squad_list(message)


async def _send_squad_list(message: Message, edit: bool = False):
    async with async_session_factory() as session:
        squads = await get_all_squads(session)
    if not squads:
        text = "📋 Отрядов пока нет."
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➕ Создать отряд", callback_data="squad_new")]
        ])
    else:
        lines = ["📋 <b>Отряды:</b>\n"]
        for sq in squads:
            lines.append(_squad_text(sq))
        text = "\n\n".join(lines)
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➕ Создать отряд", callback_data="squad_new")]
        ])
    if edit:
        await message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    else:
        await message.answer(text, reply_markup=kb, parse_mode="HTML")


@router.callback_query(F.data == "squad_list")
async def cb_squad_list(callback: CallbackQuery, staff: Staff | None = None):
    if not _require_admin(staff):
        await callback.answer("⛔ Нет прав", show_alert=True)
        return
    await _send_squad_list(callback.message, edit=True)
    await callback.answer()


@router.callback_query(F.data == "squad_new")
async def cb_squad_new(callback: CallbackQuery, state: FSMContext, staff: Staff | None = None):
    if not _require_admin(staff):
        await callback.answer("⛔ Нет прав", show_alert=True)
        return
    await callback.message.edit_text(
        "🏕 Создание отряда\n\nВведите <b>название</b> отряда:",
        reply_markup=_cancel_kb, parse_mode="HTML",
    )
    await state.set_state(SquadNewFSM.waiting_name)
    await callback.answer()


# ── /squad_edit ───────────────────────────────────────────────────────────────

@router.message(Command("squad_edit"))
async def cmd_squad_edit(message: Message, state: FSMContext, staff: Staff | None = None):
    if not _require_admin(staff):
        await message.answer("⛔ У вас нет прав для выполнения этой команды.")
        return
    args = message.text.split(maxsplit=1)
    if len(args) < 2 or not args[1].strip().isdigit():
        await message.answer("❌ Укажите ID отряда.\nФормат: /squad_edit <id>")
        return
    squad_id = int(args[1].strip())
    async with async_session_factory() as session:
        squad = await get_squad_by_id(session, squad_id)
    if not squad:
        await message.answer(f"❌ Отряд с ID {squad_id} не найден.")
        return
    await state.update_data(squad_id=squad_id)
    await message.answer(
        f"Редактирование отряда <b>{squad.name}</b>\n\nЧто изменить?",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="👤 Вожатый", callback_data="squad_edit_field:counselor")],
            [InlineKeyboardButton(text="👩‍🏫 Воспитатель", callback_data="squad_edit_field:educator")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_fsm")],
        ]),
        parse_mode="HTML",
    )
    await state.set_state(SquadEditFSM.waiting_field)


@router.callback_query(SquadEditFSM.waiting_field, F.data.startswith("squad_edit_field:"))
async def fsm_squad_edit_field(callback: CallbackQuery, state: FSMContext):
    field = callback.data.split(":")[1]
    await state.update_data(field=field)
    label = "вожатого" if field == "counselor" else "воспитателя"
    await callback.message.edit_text(
        f"Введите <b>Telegram ID</b> нового {label}:",
        reply_markup=_cancel_kb, parse_mode="HTML",
    )
    await state.set_state(SquadEditFSM.waiting_staff)
    await callback.answer()


@router.message(SquadEditFSM.waiting_staff)
async def fsm_squad_edit_staff(message: Message, state: FSMContext):
    text = message.text.strip()
    if not text.isdigit():
        await message.answer("❌ Введите числовой Telegram ID:", reply_markup=_cancel_kb)
        return
    data = await state.get_data()
    field = data["field"]
    squad_id = data["squad_id"]

    async with async_session_factory() as session:
        person = await get_staff_by_telegram_id(session, int(text))
        if not person:
            await message.answer("❌ Сотрудник не найден. Введите ещё раз:", reply_markup=_cancel_kb)
            return
        allowed = _COUNSELOR_ROLES if field == "counselor" else _EDUCATOR_ROLES
        if person.role not in allowed:
            role_name = "вожатого" if field == "counselor" else "воспитателя"
            await message.answer(
                f"❌ Роль «{ROLE_LABELS[person.role]}» не подходит для {role_name}. Введите другой ID:",
                reply_markup=_cancel_kb, parse_mode="HTML",
            )
            return
        kwargs = {f"{field}_id": person.id}
        squad = await update_squad(session, squad_id, **kwargs)

    await state.clear()
    await message.answer(
        f"✅ Отряд обновлён!\n\n{_squad_text(squad)}",
        parse_mode="HTML",
    )


# ── /my_squad ─────────────────────────────────────────────────────────────────

@router.message(Command("my_squad"))
async def cmd_my_squad(message: Message, staff: Staff | None = None):
    if staff is None:
        await message.answer("❌ Вы не зарегистрированы в системе.")
        return
    if not staff.squad_id:
        await message.answer("ℹ️ Вы не закреплены за отрядом.")
        return
    async with async_session_factory() as session:
        squad = await get_squad_by_id(session, staff.squad_id)
    if not squad:
        await message.answer("❌ Отряд не найден.")
        return
    await message.answer(_squad_text(squad), parse_mode="HTML")


# ── /find_replacement ─────────────────────────────────────────────────────────

@router.message(Command("find_replacement"))
async def cmd_find_replacement(message: Message, staff: Staff | None = None):
    if not _require_admin(staff):
        await message.answer("⛔ У вас нет прав для выполнения этой команды.")
        return
    await message.answer(
        "🔍 Поиск замены\n\nВыберите роль:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="👤 Вожатый", callback_data="free_staff:counselor")],
            [InlineKeyboardButton(text="👩‍🏫 Старший вожатый", callback_data="free_staff:senior_counselor")],
            [InlineKeyboardButton(text="🧑‍🏫 Воспитатель", callback_data="free_staff:educator")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_fsm")],
        ]),
    )


@router.callback_query(F.data.startswith("free_staff:"))
async def cb_free_staff(callback: CallbackQuery, staff: Staff | None = None):
    if not _require_admin(staff):
        await callback.answer("⛔ Нет прав", show_alert=True)
        return
    role_value = callback.data.split(":")[1]
    try:
        role = StaffRole(role_value)
    except ValueError:
        await callback.answer("❌ Неверная роль", show_alert=True)
        return
    async with async_session_factory() as session:
        free = await get_free_staff_by_role(session, role)
    role_label = ROLE_LABELS[role]
    if not free:
        await callback.message.edit_text(f"😔 Нет свободных сотрудников с ролью «{role_label}».")
        await callback.answer()
        return
    lines = [f"✅ Свободные сотрудники — <b>{role_label}</b>:\n"]
    for p in free:
        lines.append(f"• {p.full_name} (ID: <code>{p.telegram_id}</code>)")
    await callback.message.edit_text("\n".join(lines), parse_mode="HTML")
    await callback.answer()
