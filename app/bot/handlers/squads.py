from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.bot.keyboards import (
    cancel_kb,
    find_replacement_role_kb,
    skip_cancel_kb,
    squad_edit_field_kb,
    squad_item_kb,
    squads_menu,
    confirm_kb,
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
from sqlalchemy import delete

router = Router(name="squads")

_ADMIN_ROLES = {StaffRole.admin, StaffRole.senior_counselor}


def _squad_text(squad) -> str:
    counselor = squad.counselor.full_name if squad.counselor else "—"
    educator = squad.educator.full_name if squad.educator else "—"
    educator_2 = squad.educator_2.full_name if squad.educator_2 else "—"
    members_count = len([m for m in squad.members
                         if m.id not in {squad.counselor_id, squad.educator_id, squad.educator_id_2}])
    return (
        f"🏕 <b>{squad.name}</b>\n"
        f"Вожатый: {counselor}\n"
        f"Воспитатель 1: {educator}\n"
        f"Воспитатель 2: {educator_2}\n"
        f"Участников: {members_count}"
    )


# ── Список отрядов ────────────────────────────────────────────────────────────

@router.callback_query(F.data == "squad_list")
async def cb_squad_list(callback: CallbackQuery, staff: Staff | None = None):
    if staff is None or staff.role not in _ADMIN_ROLES:
        await callback.answer("⛔ Нет прав", show_alert=True)
        return
    async with async_session_factory() as session:
        squads = await get_all_squads(session)

    if not squads:
        await callback.message.edit_text(
            "🏕 <b>Отряды</b>\n\nОтрядов пока нет.",
            reply_markup=squads_menu(),
            parse_mode="HTML",
        )
        await callback.answer()
        return

    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
    rows = [[InlineKeyboardButton(text=f"🏕 {s.name}", callback_data=f"squad_view:{s.id}")] for s in squads]
    rows.append([InlineKeyboardButton(text="➕ Новый отряд", callback_data="squad_new")])
    rows.append([InlineKeyboardButton(text="🔍 Найти замену", callback_data="find_replacement")])
    kb = InlineKeyboardMarkup(inline_keyboard=rows)

    await callback.message.edit_text(
        f"🏕 <b>Отряды</b> ({len(squads)}):", reply_markup=kb, parse_mode="HTML"
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


# ── Новый отряд FSM ───────────────────────────────────────────────────────────

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
    await state.update_data(name=message.text.strip())
    await message.answer(
        "Введите <b>Telegram ID</b> вожатого (или /skip):",
        reply_markup=skip_cancel_kb("squad_skip_counselor"), parse_mode="HTML",
    )
    await state.set_state(SquadNewFSM.waiting_counselor)


@router.callback_query(SquadNewFSM.waiting_counselor, F.data == "squad_skip_counselor")
async def fsm_squad_skip_counselor(callback: CallbackQuery, state: FSMContext):
    await state.update_data(counselor_id=None)
    await callback.message.edit_text(
        "Введите <b>Telegram ID</b> воспитателя 1 (или пропустите):",
        reply_markup=skip_cancel_kb("squad_skip_educator"), parse_mode="HTML",
    )
    await state.set_state(SquadNewFSM.waiting_educator)
    await callback.answer()


@router.message(SquadNewFSM.waiting_counselor)
async def fsm_squad_counselor(message: Message, state: FSMContext):
    if not message.text.strip().isdigit():
        await message.answer("❌ Введите числовой Telegram ID:")
        return
    async with async_session_factory() as session:
        s = await get_staff_by_telegram_id(session, int(message.text.strip()))
    if not s:
        await message.answer("❌ Сотрудник с таким ID не найден. Попробуйте ещё раз:")
        return
    await state.update_data(counselor_id=s.id)
    await message.answer(
        f"Вожатый: <b>{s.full_name}</b> ✅\n\nВведите <b>Telegram ID</b> воспитателя 1 (или пропустите):",
        reply_markup=skip_cancel_kb("squad_skip_educator"), parse_mode="HTML",
    )
    await state.set_state(SquadNewFSM.waiting_educator)


@router.callback_query(SquadNewFSM.waiting_educator, F.data == "squad_skip_educator")
async def fsm_squad_skip_educator(callback: CallbackQuery, state: FSMContext):
    await state.update_data(educator_id=None)
    await callback.message.edit_text(
        "Введите <b>Telegram ID</b> воспитателя 2 (или пропустите):",
        reply_markup=skip_cancel_kb("squad_skip_educator_2"), parse_mode="HTML",
    )
    await state.set_state(SquadNewFSM.waiting_educator_2)
    await callback.answer()


@router.message(SquadNewFSM.waiting_educator)
async def fsm_squad_educator(message: Message, state: FSMContext):
    if not message.text.strip().isdigit():
        await message.answer("❌ Введите числовой Telegram ID:")
        return
    async with async_session_factory() as session:
        s = await get_staff_by_telegram_id(session, int(message.text.strip()))
    if not s:
        await message.answer("❌ Сотрудник с таким ID не найден. Попробуйте ещё раз:")
        return
    await state.update_data(educator_id=s.id)
    await message.answer(
        f"Воспитатель 1: <b>{s.full_name}</b> ✅\n\nВведите <b>Telegram ID</b> воспитателя 2 (или пропустите):",
        reply_markup=skip_cancel_kb("squad_skip_educator_2"), parse_mode="HTML",
    )
    await state.set_state(SquadNewFSM.waiting_educator_2)


@router.callback_query(SquadNewFSM.waiting_educator_2, F.data == "squad_skip_educator_2")
async def fsm_squad_skip_educator_2(callback: CallbackQuery, state: FSMContext):
    await state.update_data(educator_id_2=None)
    await _finish_squad_creation(callback.message, state)
    await callback.answer()


@router.message(SquadNewFSM.waiting_educator_2)
async def fsm_squad_educator_2(message: Message, state: FSMContext):
    if not message.text.strip().isdigit():
        await message.answer("❌ Введите числовой Telegram ID:")
        return
    async with async_session_factory() as session:
        s = await get_staff_by_telegram_id(session, int(message.text.strip()))
    if not s:
        await message.answer("❌ Сотрудник с таким ID не найден. Попробуйте ещё раз:")
        return
    await state.update_data(educator_id_2=s.id)
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
    await state.update_data(squad_id=int(squad_id_str), field=field)

    if field == "name":
        await callback.message.edit_text(
            "Введите новое <b>название</b> отряда:", reply_markup=cancel_kb(), parse_mode="HTML"
        )
    else:
        await callback.message.edit_text(
            "Введите <b>Telegram ID</b> нового сотрудника:", reply_markup=cancel_kb(), parse_mode="HTML"
        )
    await state.set_state(SquadEditFSM.waiting_value)
    await callback.answer()


@router.message(SquadEditFSM.waiting_value)
async def fsm_squad_edit_value(message: Message, state: FSMContext):
    data = await state.get_data()
    field = data["field"]
    squad_id = data["squad_id"]
    value_str = message.text.strip()

    if field == "name":
        async with async_session_factory() as session:
            await update_squad(session, squad_id, name=value_str)
        await state.clear()
        async with async_session_factory() as session:
            squad = await get_squad_by_id(session, squad_id)
        await message.answer(
            f"✅ Название изменено.\n\n{_squad_text(squad)}",
            reply_markup=squad_item_kb(squad_id), parse_mode="HTML",
        )
    else:
        if not value_str.isdigit():
            await message.answer("❌ Введите числовой Telegram ID:")
            return
        async with async_session_factory() as session:
            staff_obj = await get_staff_by_telegram_id(session, int(value_str))
        if not staff_obj:
            await message.answer("❌ Сотрудник не найден. Попробуйте ещё раз:")
            return
        kwargs = {field + "_id": staff_obj.id} if field != "name" else {"name": value_str}
        # counselor → counselor_id, educator → educator_id, educator_2 → educator_id_2
        field_map = {"counselor": "counselor_id", "educator": "educator_id", "educator_2": "educator_id_2"}
        update_kwargs = {field_map.get(field, field): staff_obj.id}
        async with async_session_factory() as session:
            await update_squad(session, squad_id, **update_kwargs)
        await state.clear()
        async with async_session_factory() as session:
            squad = await get_squad_by_id(session, squad_id)
        await message.answer(
            f"✅ Сотрудник обновлён.\n\n{_squad_text(squad)}",
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
    from app.db.models import Squad
    from app.db.base import async_session_factory
    async with async_session_factory() as session:
        squad = await get_squad_by_id(session, squad_id)
        if squad:
            name = squad.name
            await session.delete(squad)
            await session.commit()
    await callback.message.edit_text(
        f"🗑 Отряд <b>{name}</b> удалён.",
        reply_markup=squads_menu(),
        parse_mode="HTML",
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
        reply_markup=find_replacement_role_kb(),
        parse_mode="HTML",
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
            lines.append(f"• {s.full_name} — <code>{s.telegram_id}</code>")
        text = "\n".join(lines)

    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
    kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="◀️ Назад", callback_data="find_replacement")]]
    )
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()
