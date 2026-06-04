"""Дежурства — генерация, просмотр, подтверждение."""
from datetime import date, datetime, timezone

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from app.db.base import async_session_factory
from app.db.crud import (
    duty_add_checkpoint,
    generate_duties,
    get_active_session,
    get_all_active_staff,
    get_duties_by_date,
    get_duties_by_staff,
    update_duty_status,
)
from app.db.models import DUTY_TYPE_LABELS, DutyStatus, Staff, StaffRole

router = Router(name="duties")
_ADMIN_ROLES = {StaffRole.admin, StaffRole.senior_counselor}


def _duty_text(duty) -> str:
    status_emoji = {"scheduled": "📅", "active": "🔄", "completed": "✅"}
    return (
        f"{status_emoji.get(duty.status.value, '?')} {DUTY_TYPE_LABELS[duty.type]} "
        f"— {duty.staff.full_name} ({duty.date.strftime('%d.%m')})"
    )


# ── /duty_generate — сгенерировать дежурства ──────────────────────────────────

@router.message(Command("duty_generate"))
async def cmd_duty_generate(message: Message, staff: Staff | None = None):
    if staff is None or staff.role not in _ADMIN_ROLES:
        await message.answer("⛔ Нет прав.")
        return
    async with async_session_factory() as session:
        sess = await get_active_session(session)
        if not sess:
            await message.answer("❌ Нет активной смены.")
            return
        count = await generate_duties(session, sess.id)
    await message.answer(f"✅ Создано {count} дежурств на смену.")


# ── /duty_view {date} — дежурства на дату ─────────────────────────────────────

@router.message(Command("duty_view"))
async def cmd_duty_view(message: Message, staff: Staff | None = None):
    if staff is None or staff.role not in _ADMIN_ROLES:
        return
    args = message.text.split(maxsplit=1)
    if len(args) > 1:
        try:
            from datetime import datetime
            dt = datetime.strptime(args[1].strip(), "%d.%m.%Y").date()
        except ValueError:
            await message.answer("❌ Формат даты: /duty_view 15.06.2026")
            return
    else:
        dt = date.today()

    async with async_session_factory() as session:
        sess = await get_active_session(session)
        duties = await get_duties_by_date(session, dt, sess.id if sess else 0)

    if not duties:
        await message.answer(f"📅 Дежурств на {dt.strftime('%d.%m.%Y')} нет.")
        return

    lines = [f"📅 <b>Дежурства {dt.strftime('%d.%m.%Y')}:</b>\n"]
    for d in duties:
        lines.append(_duty_text(d))
    await message.answer("\n".join(lines), parse_mode="HTML")


# ── /my_duty — мои предстоящие дежурства ─────────────────────────────────────

@router.message(Command("my_duty"))
async def cmd_my_duty(message: Message, staff: Staff | None = None):
    if staff is None:
        return
    async with async_session_factory() as session:
        duties = await get_duties_by_staff(session, staff.id)
    if not duties:
        await message.answer("📅 Предстоящих дежурств нет.")
        return
    lines = [f"📅 <b>Мои дежурства:</b>\n"]
    for d in duties[:10]:
        kb_part = f" [ID:{d.id}]"
        lines.append(_duty_text(d) + kb_part)
    lines.append("\nДля отметки: /duty_done <id>")
    await message.answer("\n".join(lines), parse_mode="HTML")


# ── /duty_done {id} — завершить дежурство ─────────────────────────────────────

@router.message(Command("duty_done"))
async def cmd_duty_done(message: Message, staff: Staff | None = None):
    if staff is None:
        return
    args = message.text.split(maxsplit=1)
    if len(args) < 2 or not args[1].strip().isdigit():
        await message.answer("Использование: /duty_done <id>")
        return
    duty_id = int(args[1])
    async with async_session_factory() as session:
        await update_duty_status(session, duty_id, DutyStatus.completed)
        await duty_add_checkpoint(session, duty_id, "Завершено")

    # Notify admins
    from app.bot.bot import get_bot
    bot = get_bot()
    async with async_session_factory() as session:
        admins = await get_all_active_staff(session)
    for s in admins:
        if s.role in _ADMIN_ROLES:
            try:
                await bot.send_message(
                    s.telegram_id,
                    f"✅ Дежурство ID:{duty_id} завершено сотрудником {staff.full_name}",
                )
            except Exception:
                pass
    await message.answer(f"✅ Дежурство #{duty_id} отмечено как завершённое.")


# ── /duty_alarm — тревога ─────────────────────────────────────────────────────

@router.message(Command("duty_alarm"))
async def cmd_duty_alarm(message: Message, staff: Staff | None = None):
    if staff is None:
        return
    from app.bot.bot import get_bot
    bot = get_bot()
    async with async_session_factory() as session:
        all_staff = await get_all_active_staff(session)
    sent = 0
    for s in all_staff:
        if s.role in _ADMIN_ROLES:
            try:
                await bot.send_message(
                    s.telegram_id,
                    f"🚨 <b>ТРЕВОГА НА ДЕЖУРСТВЕ!</b>\n\nСообщение от: {staff.full_name}",
                    parse_mode="HTML",
                )
                sent += 1
            except Exception:
                pass
    await message.answer(f"🚨 Тревога отправлена {sent} администраторам.")
