"""Инциденты — быстрый репорт, журнал."""
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup,
    Message, PhotoSize,
)

from app.bot.keyboards import cancel_kb
from app.bot.states import IncidentFSM
from app.db.base import async_session_factory
from app.db.crud import (
    create_incident,
    get_all_active_staff,
    get_active_session,
    get_incidents_all,
    get_incidents_today,
    search_children,
)
from app.db.models import Staff, StaffRole

router = Router(name="incidents")
_ADMIN_ROLES = {StaffRole.admin, StaffRole.senior_counselor}

_INCIDENT_TYPES = ["медицинский", "дисциплинарный", "имущественный", "другое"]


def _incident_types_kb() -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text=t.capitalize(), callback_data=f"inc_type:{t}")] for t in _INCIDENT_TYPES]
    rows.append([InlineKeyboardButton(text="✕ Отмена", callback_data="cancel_fsm")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _skip_cancel_kb(skip_cb: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➡️ Пропустить", callback_data=skip_cb)],
        [InlineKeyboardButton(text="✕ Отмена", callback_data="cancel_fsm")],
    ])


def _format_incident(inc) -> str:
    child = f"\nРебёнок: {inc.child.full_name}" if inc.child else ""
    return (
        f"🚨 <b>{inc.type.upper()}</b> | {inc.created_at.strftime('%d.%m %H:%M')}\n"
        f"Репортер: {inc.reporter.full_name}\n"
        f"Описание: {inc.description}{child}"
    )


# ── /incident — создать инцидент ──────────────────────────────────────────────

@router.message(Command("incident"))
async def cmd_incident(message: Message, state: FSMContext, staff: Staff | None = None):
    if staff is None:
        return
    await message.answer(
        "🚨 <b>Новый инцидент</b>\n\nВыберите тип:",
        reply_markup=_incident_types_kb(),
        parse_mode="HTML",
    )
    await state.set_state(IncidentFSM.waiting_type)


@router.callback_query(IncidentFSM.waiting_type, F.data.startswith("inc_type:"))
async def incident_type(callback: CallbackQuery, state: FSMContext):
    inc_type = callback.data.split(":")[1]
    await state.update_data(inc_type=inc_type)
    await callback.message.edit_text(
        f"Тип: <b>{inc_type}</b>\n\nОпишите инцидент подробно:",
        parse_mode="HTML",
    )
    await state.set_state(IncidentFSM.waiting_description)
    await callback.answer()


@router.message(IncidentFSM.waiting_description)
async def incident_description(message: Message, state: FSMContext):
    await state.update_data(description=message.text)
    await message.answer(
        "Укажите имя ребёнка (если связано) или пропустите:",
        reply_markup=_skip_cancel_kb("inc_skip_child"),
    )
    await state.set_state(IncidentFSM.waiting_child)


@router.callback_query(IncidentFSM.waiting_child, F.data == "inc_skip_child")
async def incident_skip_child(callback: CallbackQuery, state: FSMContext):
    await state.update_data(child_id=None)
    await callback.message.edit_text(
        "Прикрепите фото (или пропустите):",
        reply_markup=_skip_cancel_kb("inc_skip_photo"),
    )
    await state.set_state(IncidentFSM.waiting_photo)
    await callback.answer()


@router.message(IncidentFSM.waiting_child)
async def incident_child(message: Message, state: FSMContext):
    name = message.text.strip()
    async with async_session_factory() as session:
        children, _ = await search_children(session, search=name, limit=5)
    if not children:
        await message.answer("❌ Не найден. Введите ещё раз или пропустите:", reply_markup=_skip_cancel_kb("inc_skip_child"))
        return
    await state.update_data(child_id=children[0].id)
    await message.answer(
        f"Ребёнок: <b>{children[0].full_name}</b>\n\nПрикрепите фото или пропустите:",
        reply_markup=_skip_cancel_kb("inc_skip_photo"),
        parse_mode="HTML",
    )
    await state.set_state(IncidentFSM.waiting_photo)


@router.callback_query(IncidentFSM.waiting_photo, F.data == "inc_skip_photo")
async def incident_skip_photo(callback: CallbackQuery, state: FSMContext, staff: Staff | None = None):
    await state.update_data(photo_url=None)
    await _save_incident(callback.message, state, staff)
    await callback.answer()


@router.message(IncidentFSM.waiting_photo, F.photo)
async def incident_photo(message: Message, state: FSMContext, staff: Staff | None = None):
    photo: PhotoSize = message.photo[-1]
    await state.update_data(photo_url=photo.file_id)
    await _save_incident(message, state, staff)


@router.message(IncidentFSM.waiting_photo)
async def incident_photo_text(message: Message, state: FSMContext, staff: Staff | None = None):
    await state.update_data(photo_url=None)
    await _save_incident(message, state, staff)


async def _save_incident(message: Message, state: FSMContext, staff: Staff | None):
    data = await state.get_data()
    await state.clear()

    async with async_session_factory() as session:
        sess = await get_active_session(session)
        inc = await create_incident(
            session,
            type_=data["inc_type"],
            description=data["description"],
            reported_by=staff.id,
            session_id=sess.id if sess else None,
            child_id=data.get("child_id"),
            photo_url=data.get("photo_url"),
        )
        all_staff = await get_all_active_staff(session)

    from app.bot.bot import get_bot
    bot = get_bot()
    alert = (
        f"🚨 <b>ИНЦИДЕНТ</b>\n\n"
        f"Тип: <b>{inc.type}</b>\n"
        f"Кто: {staff.full_name}\n"
        f"Описание: {inc.description}"
    )
    for s in all_staff:
        if s.role in _ADMIN_ROLES or (inc.type == "медицинский" and s.role == StaffRole.senior_counselor):
            try:
                await bot.send_message(s.telegram_id, alert, parse_mode="HTML")
                if data.get("photo_url"):
                    await bot.send_photo(s.telegram_id, data["photo_url"])
            except Exception:
                pass

    await message.answer("✅ Инцидент зафиксирован и отправлен администраторам.", parse_mode="HTML")


# ── /incidents_today — сегодняшние инциденты ──────────────────────────────────

@router.message(Command("incidents_today"))
async def cmd_incidents_today(message: Message, staff: Staff | None = None):
    if staff is None or staff.role not in _ADMIN_ROLES:
        return
    async with async_session_factory() as session:
        sess = await get_active_session(session)
        incidents = await get_incidents_today(session, session_id=sess.id if sess else None)
    if not incidents:
        await message.answer("✅ Сегодня инцидентов нет.")
        return
    lines = [f"🚨 <b>Инциденты сегодня ({len(incidents)}):</b>\n"]
    for inc in incidents:
        lines.append(_format_incident(inc))
    await message.answer("\n\n".join(lines), parse_mode="HTML")


# ── /incidents_all — журнал инцидентов ────────────────────────────────────────

@router.message(Command("incidents_all"))
async def cmd_incidents_all(message: Message, staff: Staff | None = None):
    if staff is None or staff.role not in _ADMIN_ROLES:
        return
    async with async_session_factory() as session:
        sess = await get_active_session(session)
        incidents = await get_incidents_all(session, session_id=sess.id if sess else None, limit=20)
    if not incidents:
        await message.answer("📋 Журнал инцидентов пуст.")
        return
    lines = [f"📋 <b>Журнал инцидентов (последние 20):</b>\n"]
    for inc in incidents:
        lines.append(_format_incident(inc))
    await message.answer("\n\n".join(lines), parse_mode="HTML")
