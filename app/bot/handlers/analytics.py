"""Аналитика: оценки мероприятий, статистика задач."""
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from app.bot.keyboards import cancel_kb
from app.bot.states import RateEventFSM
from app.db.base import async_session_factory
from app.db.crud import (
    get_active_session,
    get_all_active_staff,
    get_event_ratings,
    get_session_stats,
    get_staff_task_stats,
    save_event_rating,
)
from app.db.models import STATUS_LABELS, TaskStatus, Staff, StaffRole

router = Router(name="analytics")
_ADMIN_ROLES = {StaffRole.admin, StaffRole.senior_counselor}


def _rating_kb(event_id: int) -> InlineKeyboardMarkup:
    stars = ["⭐", "⭐⭐", "⭐⭐⭐", "⭐⭐⭐⭐", "⭐⭐⭐⭐⭐"]
    rows = [[InlineKeyboardButton(text=s, callback_data=f"rate:{event_id}:{i+1}")] for i, s in enumerate(stars)]
    rows.append([InlineKeyboardButton(text="✕ Отмена", callback_data="cancel_fsm")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ── /rate_event {event_id} ────────────────────────────────────────────────────

@router.message(Command("rate_event"))
async def cmd_rate_event(message: Message, state: FSMContext, staff: Staff | None = None):
    if staff is None:
        return
    args = message.text.split(maxsplit=1)
    if len(args) < 2 or not args[1].strip().isdigit():
        await message.answer("Использование: /rate_event <id>")
        return
    event_id = int(args[1])
    await state.update_data(event_id=event_id)
    await message.answer(
        "⭐ Оцените мероприятие:",
        reply_markup=_rating_kb(event_id),
    )
    await state.set_state(RateEventFSM.waiting_rating)


@router.callback_query(RateEventFSM.waiting_rating, F.data.startswith("rate:"))
async def rate_chosen(callback: CallbackQuery, state: FSMContext):
    _, event_id_s, rating_s = callback.data.split(":")
    await state.update_data(event_id=int(event_id_s), rating=int(rating_s))
    await callback.message.edit_text(
        "Напишите комментарий (или отправьте «-» чтобы пропустить):"
    )
    await state.set_state(RateEventFSM.waiting_comment)
    await callback.answer()


@router.message(RateEventFSM.waiting_comment)
async def rate_comment(message: Message, state: FSMContext, staff: Staff | None = None):
    data = await state.get_data()
    await state.clear()
    comment = message.text.strip() if message.text.strip() != "-" else None
    async with async_session_factory() as session:
        await save_event_rating(session, data["event_id"], staff.id, data["rating"], comment)
    stars = "⭐" * data["rating"]
    await message.answer(f"✅ Оценка сохранена: {stars}")


# ── /stats_staff {имя} ────────────────────────────────────────────────────────

@router.message(Command("stats_staff"))
async def cmd_stats_staff(message: Message, staff: Staff | None = None):
    if staff is None or staff.role not in _ADMIN_ROLES:
        return
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("Использование: /stats_staff <часть имени>")
        return
    name = args[1].strip()
    async with async_session_factory() as session:
        all_staff = await get_all_active_staff(session)
        target = next((s for s in all_staff if name.lower() in s.full_name.lower()), None)
        if not target:
            await message.answer(f"❌ Сотрудник «{name}» не найден.")
            return
        sess = await get_active_session(session)
        stats = await get_staff_task_stats(session, target.id, sess.id if sess else None)

    lines = [f"📊 <b>Статистика: {target.full_name}</b>\n"]
    total = sum(stats.values())
    for status, count in stats.items():
        label = STATUS_LABELS.get(TaskStatus(status), status)
        lines.append(f"{label}: {count}")
    lines.append(f"\nВсего задач: {total}")
    await message.answer("\n".join(lines), parse_mode="HTML")


# ── /stats_session — сводка по смене ─────────────────────────────────────────

@router.message(Command("stats_session"))
async def cmd_stats_session(message: Message, staff: Staff | None = None):
    if staff is None or staff.role not in _ADMIN_ROLES:
        return
    async with async_session_factory() as session:
        sess = await get_active_session(session)
        if not sess:
            await message.answer("❌ Нет активной смены.")
            return
        stats = await get_session_stats(session, sess.id)

    done = stats["done_tasks"]
    total = stats["total_tasks"]
    pct = round(done / total * 100) if total else 0
    text = (
        f"📊 <b>Аналитика смены «{sess.name}»</b>\n\n"
        f"📋 Задачи: {done}/{total} выполнено ({pct}%)\n"
        f"🎉 Мероприятий: {stats['total_events']}\n"
        f"🚨 Инцидентов: {stats['total_incidents']}"
    )
    await message.answer(text, parse_mode="HTML")


# ── Статистика оценок мероприятия ─────────────────────────────────────────────

@router.message(Command("event_ratings"))
async def cmd_event_ratings(message: Message, staff: Staff | None = None):
    if staff is None or staff.role not in _ADMIN_ROLES:
        return
    args = message.text.split(maxsplit=1)
    if len(args) < 2 or not args[1].strip().isdigit():
        await message.answer("Использование: /event_ratings <id>")
        return
    event_id = int(args[1])
    async with async_session_factory() as session:
        ratings = await get_event_ratings(session, event_id)
    if not ratings:
        await message.answer("Оценок нет.")
        return
    avg = sum(r.rating for r in ratings) / len(ratings)
    lines = [f"⭐ <b>Оценки мероприятия #{event_id}</b> (средняя: {avg:.1f})\n"]
    for r in ratings:
        stars = "⭐" * r.rating
        comment = f" — {r.comment}" if r.comment else ""
        lines.append(f"{r.staff.full_name}: {stars}{comment}")
    await message.answer("\n".join(lines), parse_mode="HTML")
