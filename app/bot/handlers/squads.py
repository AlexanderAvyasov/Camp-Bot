from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from app.bot.keyboards import (
    cancel_kb,
    confirm_kb,
    find_replacement_role_kb,
    squad_edit_field_kb,
    squad_item_kb,
    squads_menu,
)
from app.bot.states import SquadEditFSM, SquadNewFSM
from app.db.base import async_session_factory
from app.db.crud import (
    create_squad,
    get_all_active_staff,
    get_all_squads,
    get_free_staff_by_role,
    get_squad_by_id,
    update_squad,
)
from app.db.models import ROLE_LABELS, Staff, StaffRole

router = Router(name="squads")

_ADMIN_ROLES = {StaffRole.admin, StaffRole.senior_counselor}

# Role shown in staff picker for each squad field
_FIELD_ROLES = {
    "counselor":   StaffRole.counselor,
    "educator":    StaffRole.educator,
    "educator_2":  StaffRole.educator,
}
_FIELD_LABELS = {
    "counselor":  "Вожатый",
    "educator":   "Воспитатель 1",
    "educator_2": "Воспитатель 2",
}


def _squad_text(squad) -> str:
    counselor  = squad.counselor.full_name  if squad.counselor  else "—"
    educator   = squad.educator.full_name   if squad.educator   else "—"
    educator_2 = squad.educator_2.full_name if squad.educator_2 else "—"
    members_count = len([
        m for m in squad.members
        if m.id not in {squad.counselor_id, squad.educator_id, squad.educator_id_2}
    ])
    return (
        f"🏕 <b>{squad.name}</b>\n"
        f"Вожатый: {counselor}\n"
        f"Воспитатель 1: {educator}\n"
        f"Воспитатель 2: {educator_2}\n"
        f"Участников: {members_count}"
    )


def _staff_pick_kb(staff_list: list, callback_prefix: str, skip_cb: str) -> InlineKeyboardMarkup:
    """Inline keyboard with one button per staff member + Skip."""
    rows = [
        [InlineKeyboardButton(text=f"👤 {s.full_name}", callback_data=f"{callback_prefix}:{s.id}")]
        for s in staff_list
    ]
    rows.append([InlineKeyboardButton(text="➡️ Пропустить", callback_data=skip_cb)])
    rows.append([InlineKeyboardButton(text="✕ Отмена", callback_data="cancel_fsm")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ── Список отрядов ────────────────────────────────────────────────────────────

@router.callback_query(F.data == "squad_list")
async def cb_squad_list(callback: CallbackQuery, db=None, staff: Staff | None = None):
    if staff is None or staff.role not in _ADMIN_ROLES:
        await callback.answer("⛔ Нет прав", show_alert=True)
        return
    async with async_session_factory() as session:
        squads = await get_all_squads(session)

    if not squads:
        await callback.message.edit_text(
            "🏕 <b>Отряды</b>\n\nОтрядов пока нет.",
            reply_markup=squads_menu(), parse_mode="HTML",
        )
        await callback.answer()
        return

    rows = [[InlineKeyboardButton(text=f"🏕 {s.name}", callback_data=f"squad_view:{s.id}")] for s in squads]
    rows.append([InlineKeyboardButton(text="➕ Новый отряд", callback_data="squad_new")])
    rows.append([InlineKeyboardButton(text="🔍 Найти замену", callback_data="find_replacement")])
    await callback.message.edit_text(
        f"🏕 <b>Отряды</b> ({len(squads)}):",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("squad_view:"))
async def cb_squad_view(callback: CallbackQuery, staff: Staff | None = None):
    if staff is None or staff.role not in _ADMIN_ROLES:
        await callback.answer("⛔ Нет прав", show_alert=True)
        return
    squad_id = int(callback.data.split(":")[1])
    async with async_session_factory() as session:
        squad = await get_squad_by_id(session, squad_id)
    if not squad:
        await callback.answer("❌ Отряд не найден", show_alert=True)
        return
    await callback.message.edit_text(
        _squad_text(squad), reply_markup=squad_item_kb(squad_id), parse_mode="HTML"
    )
    await callback.answer()


# ── Новый отряд — FSM с выбором из списка ────────────────────────────────────

@router.callback_query(F.data == "squad_new")
async def cb_squad_new(callback: CallbackQuery, state: FSMContext, staff: Staff | None = None):
    if staff is None or staff.role not in _ADMIN_ROLES:
        await callback.answer("⛔ Нет прав", show_alert=True)
        return
    await callback.message.answer(
        "🏕 <b>Новый отряд</b>\n\nВведите название отряда:",
        reply_markup=cancel_kb(), parse_mode="HTML",
    )
    await state.set_state(SquadNewFSM.waiting_name)
    await callback.answer()


@router.message(SquadNewFSM.waiting_name)
async def fsm_squad_name(message: Message, state: FSMContext):
    name = message.text.strip()
    if not name:
        await message.answer("❌ Название не может быть пустым:")
        return
    await state.update_data(name=name, counselor_id=None, educator_id=None, educator_id_2=None)
    await _ask_pick_staff(message, state, "counselor")


async def _ask_pick_staff(message: Message, state: FSMContext, field: str):
    """Show inline list of active staff filtered by role for the given field."""
    role = _FIELD_ROLES[field]
    label = _FIELD_LABELS[field]
    async with async_session_factory() as session:
        staff_list = await get_all_active_staff(session)
    # filter by role
    filtered = [s for s in staff_list if s.role == role]

    await state.update_data(_pick_field=field)

    if not filtered:
        await message.answer(
            f"Нет сотрудников с ролью «{label}». Поле пропущено.",
        )
        await _advance_new_squad(message, state, field, staff_id=None)
        return

    kb = _staff_pick_kb(filtered, "squad_pick_staff", f"squad_skip_field")
    await message.answer(
        f"Выберите <b>{label}</b> для отряда:", reply_markup=kb, parse_mode="HTML"
    )
    # set appropriate FSM state
    state_map = {
        "counselor":  SquadNewFSM.waiting_counselor,
        "educator":   SquadNewFSM.waiting_educator,
        "educator_2": SquadNewFSM.waiting_educator_2,
    }
    await state.set_state(state_map[field])


@router.callback_query(
    F.data.startswith("squad_pick_staff:"),
    SquadNewFSM.waiting_counselor,
)
async def fsm_pick_counselor(callback: CallbackQuery, state: FSMContext):
    staff_id = int(callback.data.split(":")[1])
    await state.update_data(counselor_id=staff_id)
    await callback.message.delete()
    await _advance_new_squad(callback.message, state, "counselor", staff_id)
    await callback.answer()


@router.callback_query(
    F.data.startswith("squad_pick_staff:"),
    SquadNewFSM.waiting_educator,
)
async def fsm_pick_educator(callback: CallbackQuery, state: FSMContext):
    staff_id = int(callback.data.split(":")[1])
    await state.update_data(educator_id=staff_id)
    await callback.message.delete()
    await _advance_new_squad(callback.message, state, "educator", staff_id)
    await callback.answer()


@router.callback_query(
    F.data.startswith("squad_pick_staff:"),
    SquadNewFSM.waiting_educator_2,
)
async def fsm_pick_educator_2(callback: CallbackQuery, state: FSMContext):
    staff_id = int(callback.data.split(":")[1])
    await state.update_data(educator_id_2=staff_id)
    await callback.message.delete()
    await _finish_squad_creation(callback.message, state)
    await callback.answer()


@router.callback_query(
    F.data == "squad_skip_field",
    SquadNewFSM.waiting_counselor,
)
async def fsm_skip_counselor(callback: CallbackQuery, state: FSMContext):
    await callback.message.delete()
    await _advance_new_squad(callback.message, state, "counselor", staff_id=None)
    await callback.answer()


@router.callback_query(
    F.data == "squad_skip_field",
    SquadNewFSM.waiting_educator,
)
async def fsm_skip_educator(callback: CallbackQuery, state: FSMContext):
    await callback.message.delete()
    await _advance_new_squad(callback.message, state, "educator", staff_id=None)
    await callback.answer()


@router.callback_query(
    F.data == "squad_skip_field",
    SquadNewFSM.waiting_educator_2,
)
async def fsm_skip_educator_2(callback: CallbackQuery, state: FSMContext):
    await callback.message.delete()
    await _finish_squad_creation(callback.message, state)
    await callback.answer()


async def _advance_new_squad(message: Message, state: FSMContext, done_field: str, staff_id):
    """Move to the next step in new-squad creation."""
    next_field = {"counselor": "educator", "educator": "educator_2"}.get(done_field)
    if next_field:
        await _ask_pick_staff(message, state, next_field)
    else:
        await _finish_squad_creation(message, state)


async def _finish_squad_creation(message: Message, state: FSMContext):
    data = await state.get_data()
    async with async_session_factory() as session:
        squad = await create_squad(
            session,
            name=data["name"],
            counselor_id=data.get("counselor_id"),
            educator_id=data.get("educator_id"),
            educator_id_2=data.get("educator_id_2"),
        )
        squad = await get_squad_by_id(session, squad.id)
    await state.clear()
    await message.answer(
        f"✅ Отряд создан!\n\n{_squad_text(squad)}",
        reply_markup=squad_item_kb(squad.id),
        parse_mode="HTML",
    )


# ── Редактирование отряда ─────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("squad_edit:"))
async def cb_squad_edit(callback: CallbackQuery, staff: Staff | None = None):
    if staff is None or staff.role not in _ADMIN_ROLES:
        await callback.answer("⛔ Нет прав", show_alert=True)
        return
    squad_id = int(callback.data.split(":")[1])
    await callback.message.edit_text(
        "✏️ Выберите поле для редактирования:",
        reply_markup=squad_edit_field_kb(squad_id),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("squad_field:"))
async def cb_squad_field(callback: CallbackQuery, state: FSMContext, staff: Staff | None = None):
    if staff is None or staff.role not in _ADMIN_ROLES:
        await callback.answer("⛔ Нет прав", show_alert=True)
        return
    _, squad_id_str, field = callback.data.split(":")
    squad_id = int(squad_id_str)
    await state.update_data(squad_id=squad_id, field=field)

    if field == "name":
        await callback.message.edit_text(
            "Введите новое <b>название</b> отряда:", reply_markup=cancel_kb(), parse_mode="HTML"
        )
        await state.set_state(SquadEditFSM.waiting_value)
    else:
        # Show staff picker for the role
        role = _FIELD_ROLES.get(field, StaffRole.counselor)
        label = _FIELD_LABELS.get(field, field)
        async with async_session_factory() as session:
            staff_list = await get_all_active_staff(session)
        filtered = [s for s in staff_list if s.role == role]

        if not filtered:
            await callback.answer(f"Нет сотрудников с ролью «{label}»", show_alert=True)
            return

        kb = _staff_pick_kb(filtered, "squad_edit_pick", f"squad_edit_skip:{squad_id}")
        await callback.message.edit_text(
            f"Выберите <b>{label}</b>:", reply_markup=kb, parse_mode="HTML"
        )
        await state.set_state(SquadEditFSM.waiting_value)

    await callback.answer()


@router.callback_query(F.data.startswith("squad_edit_pick:"), SquadEditFSM.waiting_value)
async def cb_squad_edit_pick(callback: CallbackQuery, state: FSMContext):
    staff_id = int(callback.data.split(":")[1])
    data = await state.get_data()
    field = data["field"]
    squad_id = data["squad_id"]

    field_map = {
        "counselor":  "counselor_id",
        "educator":   "educator_id",
        "educator_2": "educator_id_2",
    }
    async with async_session_factory() as session:
        await update_squad(session, squad_id, **{field_map[field]: staff_id})
        squad = await get_squad_by_id(session, squad_id)

    await state.clear()
    await callback.message.edit_text(
        f"✅ Обновлено.\n\n{_squad_text(squad)}",
        reply_markup=squad_item_kb(squad_id), parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("squad_edit_skip:"), SquadEditFSM.waiting_value)
async def cb_squad_edit_skip(callback: CallbackQuery, state: FSMContext):
    squad_id = int(callback.data.split(":")[1])
    data = await state.get_data()
    field = data["field"]
    field_map = {
        "counselor":  "counselor_id",
        "educator":   "educator_id",
        "educator_2": "educator_id_2",
    }
    async with async_session_factory() as session:
        await update_squad(session, squad_id, **{field_map[field]: None})
        squad = await get_squad_by_id(session, squad_id)

    await state.clear()
    await callback.message.edit_text(
        f"✅ Поле очищено.\n\n{_squad_text(squad)}",
        reply_markup=squad_item_kb(squad_id), parse_mode="HTML",
    )
    await callback.answer()


@router.message(SquadEditFSM.waiting_value)
async def fsm_squad_edit_name(message: Message, state: FSMContext):
    data = await state.get_data()
    if data.get("field") != "name":
        return
    squad_id = data["squad_id"]
    async with async_session_factory() as session:
        await update_squad(session, squad_id, name=message.text.strip())
        squad = await get_squad_by_id(session, squad_id)
    await state.clear()
    await message.answer(
        f"✅ Название изменено.\n\n{_squad_text(squad)}",
        reply_markup=squad_item_kb(squad_id), parse_mode="HTML",
    )


# ── Удаление отряда ───────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("squad_del_confirm:"))
async def cb_squad_del_confirm(callback: CallbackQuery, staff: Staff | None = None):
    if staff is None or staff.role not in _ADMIN_ROLES:
        await callback.answer("⛔ Нет прав", show_alert=True)
        return
    squad_id = int(callback.data.split(":")[1])
    await callback.message.edit_text(
        "❗ Удалить отряд? Это действие нельзя отменить.",
        reply_markup=confirm_kb(f"squad_del:{squad_id}", f"squad_view:{squad_id}"),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("squad_del:"))
async def cb_squad_del(callback: CallbackQuery, staff: Staff | None = None):
    if staff is None or staff.role not in _ADMIN_ROLES:
        await callback.answer("⛔ Нет прав", show_alert=True)
        return
    squad_id = int(callback.data.split(":")[1])
    async with async_session_factory() as session:
        squad = await get_squad_by_id(session, squad_id)
        if squad:
            name = squad.name
            await session.delete(squad)
            await session.commit()
    await callback.message.edit_text(
        f"🗑 Отряд <b>{name}</b> удалён.", reply_markup=squads_menu(), parse_mode="HTML",
    )
    await callback.answer()


# ── Найти замену ──────────────────────────────────────────────────────────────

@router.callback_query(F.data == "find_replacement")
async def cb_find_replacement(callback: CallbackQuery, staff: Staff | None = None):
    if staff is None or staff.role not in _ADMIN_ROLES:
        await callback.answer("⛔ Нет прав", show_alert=True)
        return
    await callback.message.edit_text(
        "🔍 <b>Найти замену</b>\n\nВыберите должность:",
        reply_markup=find_replacement_role_kb(), parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("replacement_role:"))
async def cb_replacement_results(callback: CallbackQuery, staff: Staff | None = None):
    if staff is None or staff.role not in _ADMIN_ROLES:
        await callback.answer("⛔ Нет прав", show_alert=True)
        return
    role_value = callback.data.split(":")[1]
    role = StaffRole(role_value)
    async with async_session_factory() as session:
        free = await get_free_staff_by_role(session, role)

    role_label = ROLE_LABELS[role]
    if not free:
        text = f"🔍 <b>{role_label}</b>\n\nСвободных сотрудников нет."
    else:
        lines = [f"🔍 <b>Свободные {role_label.lower()}и:</b>\n"]
        for s in free:
            lines.append(f"• {s.full_name}")
        text = "\n".join(lines)

    kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="◀️ Назад", callback_data="find_replacement")]]
    )
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()
