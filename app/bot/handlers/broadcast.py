"""Экстренная рассылка и объявления для admin."""
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from app.bot.keyboards import confirm_kb
from app.bot.states import AnnounceFSM, BroadcastFSM
from app.db.base import async_session_factory
from app.db.crud import (
    create_announcement,
    get_all_active_staff,
    get_announcement_reads,
    get_announcements,
    mark_announcement_read,
)
from app.db.models import Staff, StaffRole

router = Router(name="broadcast")
_ADMIN_ROLES = {StaffRole.admin, StaffRole.senior_counselor}


# ── /broadcast — экстренная рассылка ─────────────────────────────────────────

@router.message(Command("broadcast"))
async def cmd_broadcast(message: Message, state: FSMContext, staff: Staff | None = None):
    if staff is None or staff.role not in _ADMIN_ROLES:
        await message.answer("⛔ Нет прав.")
        return
    await message.answer("📢 <b>Экстренная рассылка</b>\n\nВведите текст сообщения:", parse_mode="HTML")
    await state.set_state(BroadcastFSM.waiting_text)


@router.message(BroadcastFSM.waiting_text)
async def broadcast_text(message: Message, state: FSMContext):
    await state.update_data(text=message.text)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Отправить всем", callback_data="broadcast_confirm")],
        [InlineKeyboardButton(text="✕ Отмена", callback_data="cancel_fsm")],
    ])
    await message.answer(
        f"📢 Рассылка всем сотрудникам:\n\n{message.text}\n\nПодтвердить?",
        reply_markup=kb,
    )
    await state.set_state(BroadcastFSM.confirm)


@router.callback_query(BroadcastFSM.confirm, F.data == "broadcast_confirm")
async def broadcast_confirm(callback: CallbackQuery, state: FSMContext, staff: Staff | None = None):
    data = await state.get_data()
    text = data["text"]
    await state.clear()

    async with async_session_factory() as session:
        all_staff = await get_all_active_staff(session)

    from app.bot.bot import get_bot
    bot = get_bot()
    sent = 0
    for s in all_staff:
        try:
            await bot.send_message(
                s.telegram_id,
                f"📢 <b>Экстренное сообщение</b>\n\n{text}",
                parse_mode="HTML",
            )
            sent += 1
        except Exception:
            pass

    await callback.message.edit_text(f"✅ Рассылка отправлена {sent} сотрудникам.")
    await callback.answer()


# ── /announce — объявления с подтверждением прочтения ────────────────────────

@router.message(Command("announce"))
async def cmd_announce(message: Message, state: FSMContext, staff: Staff | None = None):
    if staff is None or staff.role not in _ADMIN_ROLES:
        await message.answer("⛔ Нет прав.")
        return
    await message.answer("📣 <b>Новое объявление</b>\n\nВведите текст:", parse_mode="HTML")
    await state.set_state(AnnounceFSM.waiting_text)


@router.message(AnnounceFSM.waiting_text)
async def announce_text(message: Message, state: FSMContext):
    await state.update_data(text=message.text)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Опубликовать", callback_data="announce_confirm")],
        [InlineKeyboardButton(text="✕ Отмена", callback_data="cancel_fsm")],
    ])
    await message.answer(f"📣 Объявление:\n\n{message.text}\n\nОпубликовать?", reply_markup=kb)
    await state.set_state(AnnounceFSM.confirm)


@router.callback_query(AnnounceFSM.confirm, F.data == "announce_confirm")
async def announce_confirm(callback: CallbackQuery, state: FSMContext, staff: Staff | None = None):
    data = await state.get_data()
    text = data["text"]
    await state.clear()

    async with async_session_factory() as session:
        ann = await create_announcement(session, text=text, created_by=staff.id)
        all_staff = await get_all_active_staff(session)

    from app.bot.bot import get_bot
    bot = get_bot()
    sent = 0
    for s in all_staff:
        try:
            kb = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="✅ Прочитано", callback_data=f"ann_read:{ann.id}")
            ]])
            await bot.send_message(
                s.telegram_id,
                f"📣 <b>Объявление</b>\n\n{text}",
                reply_markup=kb,
                parse_mode="HTML",
            )
            sent += 1
        except Exception:
            pass

    await callback.message.edit_text(f"✅ Объявление опубликовано, отправлено {sent} сотрудникам.")
    await callback.answer()


@router.callback_query(F.data.startswith("ann_read:"))
async def ann_read(callback: CallbackQuery, staff: Staff | None = None):
    if staff is None:
        await callback.answer()
        return
    ann_id = int(callback.data.split(":")[1])
    async with async_session_factory() as session:
        await mark_announcement_read(session, ann_id, staff.id)
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await callback.answer("✅ Отмечено как прочитанное")


# ── ann_unread / ann_history callbacks ───────────────────────────────────────

@router.callback_query(F.data == "ann_unread")
async def cb_ann_unread(callback: CallbackQuery, staff: Staff | None = None):
    if staff is None:
        await callback.answer()
        return
    from app.db.models import AnnouncementRead
    from sqlalchemy import select as _select
    async with async_session_factory() as session:
        all_anns = await get_announcements(session, limit=50)
        reads_result = await session.execute(
            _select(AnnouncementRead).where(AnnouncementRead.staff_id == staff.id)
        )
        reads = list(reads_result.scalars().all())
    read_ids = {r.announcement_id for r in reads}
    unread = [a for a in all_anns if a.id not in read_ids]

    if not unread:
        await callback.message.edit_text("📣 Нет непрочитанных объявлений.")
        await callback.answer()
        return

    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
    rows = []
    for a in unread[:10]:
        preview = a.text[:40] + ("…" if len(a.text) > 40 else "")
        rows.append([InlineKeyboardButton(
            text=f"📣 {a.created_at.strftime('%d.%m')} {preview}",
            callback_data=f"ann_view:{a.id}",
        )])
    await callback.message.edit_text(
        f"📣 <b>Непрочитанные объявления</b> ({len(unread)}):",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("ann_history:"))
async def cb_ann_history(callback: CallbackQuery, staff: Staff | None = None):
    if staff is None:
        await callback.answer()
        return
    page = int(callback.data.split(":")[1])
    page_size = 8
    from app.db.models import AnnouncementRead
    from sqlalchemy import select as _select
    async with async_session_factory() as session:
        anns = await get_announcements(session, limit=page_size, offset=page * page_size)
        reads_result = await session.execute(
            _select(AnnouncementRead).where(AnnouncementRead.staff_id == staff.id)
        )
        reads = list(reads_result.scalars().all())
    read_ids = {r.announcement_id for r in reads}

    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
    rows = []
    for a in anns:
        mark = "✅" if a.id in read_ids else "📣"
        preview = a.text[:35] + ("…" if len(a.text) > 35 else "")
        rows.append([InlineKeyboardButton(
            text=f"{mark} {a.created_at.strftime('%d.%m')} {preview}",
            callback_data=f"ann_view:{a.id}",
        )])
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="◀️", callback_data=f"ann_history:{page - 1}"))
    if len(anns) == page_size:
        nav.append(InlineKeyboardButton(text="▶️", callback_data=f"ann_history:{page + 1}"))
    if nav:
        rows.append(nav)
    await callback.message.edit_text(
        f"📜 <b>История объявлений</b> (стр. {page + 1}):",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("ann_view:"))
async def cb_ann_view(callback: CallbackQuery, staff: Staff | None = None):
    if staff is None:
        await callback.answer()
        return
    ann_id = int(callback.data.split(":")[1])
    async with async_session_factory() as session:
        reads = await get_announcement_reads(session, ann_id)
        all_active_staff = await get_all_active_staff(session)
        anns = await get_announcements(session, limit=100)

    ann = next((a for a in anns if a.id == ann_id), None)
    if not ann:
        await callback.answer("Объявление не найдено", show_alert=True)
        return

    read_ids = {r.staff_id for r in reads}
    is_read = staff.id in read_ids

    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
    rows = []
    if not is_read:
        rows.append([InlineKeyboardButton(text="✅ Прочитано", callback_data=f"ann_read:{ann_id}")])
    if staff.role in _ADMIN_ROLES:
        read_pct = round(len(read_ids) / len(all_active_staff) * 100) if all_active_staff else 0
        stats_line = f"\n\n📊 Прочитали: {len(read_ids)}/{len(all_active_staff)} ({read_pct}%)"
        rows.append([InlineKeyboardButton(text="📊 Подробная статистика", callback_data=f"ann_stats:{ann_id}")])
    else:
        stats_line = ""

    text = (
        f"📣 <b>Объявление</b> от {ann.created_at.strftime('%d.%m.%Y %H:%M')}\n\n"
        f"{ann.text}{stats_line}"
    )
    await callback.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows) if rows else None,
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("ann_stats:"))
async def cb_ann_stats(callback: CallbackQuery, staff: Staff | None = None):
    if staff is None or staff.role not in _ADMIN_ROLES:
        await callback.answer("⛔ Нет прав", show_alert=True)
        return
    ann_id = int(callback.data.split(":")[1])
    async with async_session_factory() as session:
        reads = await get_announcement_reads(session, ann_id)
        all_active_staff = await get_all_active_staff(session)

    read_ids = {r.staff_id for r in reads}
    read_names = [s.full_name for s in all_active_staff if s.id in read_ids]
    unread_names = [s.full_name for s in all_active_staff if s.id not in read_ids]

    text = (
        f"📊 <b>Статистика объявления #{ann_id}</b>\n\n"
        f"✅ Прочитали ({len(read_names)}):\n"
        f"{chr(10).join('• ' + n for n in read_names) or '—'}\n\n"
        f"⏳ Не прочитали ({len(unread_names)}):\n"
        f"{chr(10).join('• ' + n for n in unread_names) or '—'}"
    )
    await callback.message.edit_text(text, parse_mode="HTML")
    await callback.answer()


# ── /announcements — список последних объявлений ─────────────────────────────

@router.message(Command("announcements"))
async def cmd_announcements(message: Message, staff: Staff | None = None):
    if staff is None:
        return
    async with async_session_factory() as session:
        anns = await get_announcements(session, limit=10)
    if not anns:
        await message.answer("📣 Объявлений нет.")
        return
    lines = ["📣 <b>Последние объявления:</b>\n"]
    for a in anns:
        lines.append(f"<b>{a.created_at.strftime('%d.%m %H:%M')}</b>\n{a.text[:100]}{'…' if len(a.text) > 100 else ''}")
    await message.answer("\n\n".join(lines), parse_mode="HTML")


# ── /announce_stats {id} — статистика прочтений ───────────────────────────────

@router.message(Command("announce_stats"))
async def cmd_announce_stats(message: Message, staff: Staff | None = None):
    if staff is None or staff.role not in _ADMIN_ROLES:
        return
    args = message.text.split(maxsplit=1)
    if len(args) < 2 or not args[1].strip().isdigit():
        await message.answer("Использование: /announce_stats <id>")
        return
    ann_id = int(args[1])
    async with async_session_factory() as session:
        reads = await get_announcement_reads(session, ann_id)
        all_staff = await get_all_active_staff(session)
    read_ids = {r.staff_id for r in reads}
    unread = [s for s in all_staff if s.id not in read_ids]
    read_names = [s.full_name for s in all_staff if s.id in read_ids]
    text = (
        f"📣 Объявление #{ann_id}\n\n"
        f"✅ Прочитали ({len(read_names)}): {', '.join(read_names) or '—'}\n\n"
        f"⏳ Не прочитали ({len(unread)}): {', '.join(s.full_name for s in unread) or '—'}"
    )
    await message.answer(text)
