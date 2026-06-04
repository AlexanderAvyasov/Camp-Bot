"""Кружки — расписание, участники, посещаемость."""
from datetime import date, datetime, time

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from app.bot.keyboards import cancel_kb
from app.bot.states import CircleAddFSM, CircleMemberFSM, CircleScheduleFSM
from app.db.base import async_session_factory
from app.db.crud import (
    add_circle_member,
    add_circle_schedule,
    create_circle,
    get_active_session,
    get_all_active_staff,
    get_child_by_id,
    get_circle_by_id,
    get_circle_members,
    get_circles,
    save_circle_attendance,
    search_children,
)
from app.db.models import Staff, StaffRole

router = Router(name="circles")
_ADMIN_ROLES = {StaffRole.admin, StaffRole.senior_counselor}

_DOW_LABELS = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]


def _circle_text(circle) -> str:
    leader = circle.leader.full_name if circle.leader else "—"
    schedule_lines = [
        f"  {_DOW_LABELS[s.day_of_week]} {s.time.strftime('%H:%M')}"
        for s in circle.schedule
    ]
    return (
        f"🧩 <b>{circle.name}</b>\n"
        f"Руководитель: {leader}\n"
        + ("Расписание:\n" + "\n".join(schedule_lines) if schedule_lines else "Расписания нет")
    )


# ── /circle_add — создать кружок ──────────────────────────────────────────────

@router.message(Command("circle_add"))
async def cmd_circle_add(message: Message, state: FSMContext, staff: Staff | None = None):
    if staff is None or staff.role not in _ADMIN_ROLES:
        await message.answer("⛔ Нет прав.")
        return
    await message.answer("🧩 <b>Новый кружок</b>\n\nВведите название:", parse_mode="HTML")
    await state.set_state(CircleAddFSM.waiting_name)


@router.message(CircleAddFSM.waiting_name)
async def circle_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text.strip())
    # Show list of circle_leaders
    async with async_session_factory() as session:
        all_staff = await get_all_active_staff(session)
    leaders = [s for s in all_staff if s.role == StaffRole.circle_leader]
    if not leaders:
        await message.answer("⚠️ Нет сотрудников с ролью «Руководитель кружка». Назначаю без руководителя.")
        await state.update_data(leader_id=None)
        await _finish_circle(message, state)
        return
    rows = [[InlineKeyboardButton(text=f"👤 {s.full_name}", callback_data=f"circle_leader:{s.id}")] for s in leaders]
    rows.append([InlineKeyboardButton(text="➡️ Без руководителя", callback_data="circle_leader:0")])
    await message.answer("Выберите руководителя:", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await state.set_state(CircleAddFSM.waiting_leader)


@router.callback_query(CircleAddFSM.waiting_leader, F.data.startswith("circle_leader:"))
async def circle_leader(callback: CallbackQuery, state: FSMContext):
    leader_id_s = callback.data.split(":")[1]
    leader_id = int(leader_id_s) if leader_id_s != "0" else None
    await state.update_data(leader_id=leader_id)
    await callback.message.delete()
    await _finish_circle(callback.message, state)
    await callback.answer()


async def _finish_circle(message: Message, state: FSMContext):
    data = await state.get_data()
    await state.clear()
    async with async_session_factory() as session:
        sess = await get_active_session(session)
        circle = await create_circle(session, data["name"], data.get("leader_id"), sess.id if sess else None)
    await message.answer(
        f"✅ Кружок <b>{circle.name}</b> создан (ID: {circle.id})\n"
        f"Расписание: /circle_schedule {circle.id}",
        parse_mode="HTML",
    )


# ── /circle_schedule {id} — добавить расписание ──────────────────────────────

@router.message(Command("circle_schedule"))
async def cmd_circle_schedule(message: Message, state: FSMContext, staff: Staff | None = None):
    if staff is None or staff.role not in _ADMIN_ROLES:
        return
    args = message.text.split(maxsplit=1)
    if len(args) < 2 or not args[1].strip().isdigit():
        await message.answer("Использование: /circle_schedule <id>")
        return
    await state.update_data(circle_id=int(args[1]))
    rows = [[InlineKeyboardButton(text=d, callback_data=f"csch_dow:{i}")] for i, d in enumerate(_DOW_LABELS)]
    await message.answer("Выберите день недели:", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await state.set_state(CircleScheduleFSM.waiting_day)


@router.callback_query(CircleScheduleFSM.waiting_day, F.data.startswith("csch_dow:"))
async def circle_sch_day(callback: CallbackQuery, state: FSMContext):
    dow = int(callback.data.split(":")[1])
    await state.update_data(dow=dow)
    await callback.message.edit_text("Введите время (формат: 14:30):")
    await state.set_state(CircleScheduleFSM.waiting_time)
    await callback.answer()


@router.message(CircleScheduleFSM.waiting_time)
async def circle_sch_time(message: Message, state: FSMContext):
    try:
        t = datetime.strptime(message.text.strip(), "%H:%M").time()
    except ValueError:
        await message.answer("❌ Формат: 14:30")
        return
    data = await state.get_data()
    await state.clear()
    async with async_session_factory() as session:
        await add_circle_schedule(session, data["circle_id"], data["dow"], t)
    await message.answer(f"✅ Расписание добавлено: {_DOW_LABELS[data['dow']]} {t.strftime('%H:%M')}")


# ── /circle_members {id} — добавить детей ────────────────────────────────────

@router.message(Command("circle_members"))
async def cmd_circle_members(message: Message, state: FSMContext, staff: Staff | None = None):
    if staff is None or staff.role not in _ADMIN_ROLES:
        return
    args = message.text.split(maxsplit=1)
    if len(args) < 2 or not args[1].strip().isdigit():
        await message.answer("Использование: /circle_members <id>")
        return
    circle_id = int(args[1])
    await state.update_data(circle_id=circle_id)
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Готово", callback_data="cm_done")
    ]])
    await message.answer("Введите имя ребёнка для добавления в кружок:", reply_markup=kb)
    await state.set_state(CircleMemberFSM.waiting_name)


@router.message(CircleMemberFSM.waiting_name)
async def circle_member_add(message: Message, state: FSMContext):
    data = await state.get_data()
    name = message.text.strip()
    async with async_session_factory() as session:
        children, _ = await search_children(session, search=name, limit=5)
    if not children:
        await message.answer("❌ Не найден. Попробуйте ещё раз:")
        return
    child = children[0]
    async with async_session_factory() as session:
        await add_circle_member(session, data["circle_id"], child.id)
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Готово", callback_data="cm_done")
    ]])
    await message.answer(f"✅ {child.full_name} добавлен в кружок. Ещё?", reply_markup=kb)


@router.callback_query(CircleMemberFSM.waiting_name, F.data == "cm_done")
async def circle_member_done(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("✅ Список участников сохранён.")
    await callback.answer()


# ── /my_circle — мой кружок (для руководителя) ───────────────────────────────

@router.message(Command("my_circle"))
async def cmd_my_circle(message: Message, staff: Staff | None = None):
    if staff is None:
        return
    async with async_session_factory() as session:
        circles = await get_circles(session, leader_id=staff.id)
    if not circles:
        await message.answer("У вас нет назначенных кружков.")
        return
    c = circles[0]
    async with async_session_factory() as session:
        members = await get_circle_members(session, c.id)
    lines = [_circle_text(c), f"\nУчастников: {len(members)}"]
    if members:
        lines.append("Список: " + ", ".join(m.child.full_name for m in members))
    lines.append(f"\nОтметить посещаемость: /attendance {c.id}")
    await message.answer("\n".join(lines), parse_mode="HTML")


# ── /attendance {circle_id} — отметка посещаемости ───────────────────────────

@router.message(Command("attendance"))
async def cmd_attendance(message: Message, staff: Staff | None = None):
    if staff is None:
        return
    args = message.text.split(maxsplit=1)
    if len(args) > 1 and args[1].strip().isdigit():
        circle_id = int(args[1])
    else:
        async with async_session_factory() as session:
            circles = await get_circles(session, leader_id=staff.id)
        if not circles:
            await message.answer("❌ Укажите ID кружка: /attendance <id>")
            return
        circle_id = circles[0].id

    async with async_session_factory() as session:
        circle = await get_circle_by_id(session, circle_id)
        members = await get_circle_members(session, circle_id)

    if not members:
        await message.answer("В кружке нет участников.")
        return

    today = date.today()
    rows = []
    for m in members:
        rows.append([
            InlineKeyboardButton(
                text=f"✅ {m.child.full_name}",
                callback_data=f"att:{circle_id}:{m.child_id}:{today}:1",
            ),
            InlineKeyboardButton(
                text="❌",
                callback_data=f"att:{circle_id}:{m.child_id}:{today}:0",
            ),
        ])
    rows.append([InlineKeyboardButton(text="💾 Сохранить", callback_data=f"att_save:{circle_id}")])
    await message.answer(
        f"📋 <b>Посещаемость — {circle.name}</b>\n{today.strftime('%d.%m.%Y')}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("att:"))
async def attendance_mark(callback: CallbackQuery):
    _, circle_id_s, child_id_s, date_s, present_s = callback.data.split(":")
    circle_id = int(circle_id_s)
    child_id = int(child_id_s)
    date_ = date.fromisoformat(date_s)
    present = bool(int(present_s))
    async with async_session_factory() as session:
        await save_circle_attendance(session, circle_id, child_id, date_, present)
    await callback.answer("✅" if present else "❌")


@router.callback_query(F.data.startswith("att_save:"))
async def attendance_save(callback: CallbackQuery):
    await callback.message.edit_text("✅ Посещаемость сохранена.")
    await callback.answer()
