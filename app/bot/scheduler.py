import logging
from datetime import date, datetime, timedelta, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.db.base import async_session_factory
from app.db.crud import (
    add_task_log,
    create_task,
    get_active_session,
    get_all_active_staff,
    get_birthdays_range,
    get_night_duties_active,
    get_overdue_tasks,
    get_pending_reminders,
    get_recurring_tasks,
    get_session_stats,
    get_staff_by_id,
    get_today_circles,
    mark_reminder_sent,
    update_task_status,
)
from app.bot.keyboards import task_action_kb
from app.db.models import StaffRole, TaskStatus

logger = logging.getLogger(__name__)

_bot = None
_admin_ids: list[int] = []
_ADMIN_ROLES = {StaffRole.admin, StaffRole.senior_counselor}


def setup_scheduler(bot, admin_telegram_ids: list[int]) -> AsyncIOScheduler:
    global _bot, _admin_ids
    _bot = bot
    _admin_ids = admin_telegram_ids

    scheduler = AsyncIOScheduler(timezone="Europe/Moscow")
    scheduler.add_job(check_overdue, "interval", minutes=10, id="overdue_check")
    scheduler.add_job(spawn_recurring, "cron", hour=0, minute=1, id="recurring_spawn")
    scheduler.add_job(morning_digest, "cron", hour=8, minute=0, id="morning_digest")
    scheduler.add_job(evening_report, "cron", hour=21, minute=0, id="evening_report")
    scheduler.add_job(send_pending_reminders, "interval", minutes=5, id="reminders")
    scheduler.add_job(birthday_check, "cron", hour=8, minute=5, id="birthday_check")
    scheduler.add_job(circle_reminders, "interval", minutes=15, id="circle_reminders")
    scheduler.add_job(duty_reminders, "interval", minutes=10, id="duty_reminders")
    scheduler.add_job(check_night_duties, "cron", hour=3, minute=0, id="night_duty_check")
    return scheduler


# ── Overdue tasks ─────────────────────────────────────────────────────────────

async def check_overdue():
    if _bot is None:
        return
    async with async_session_factory() as session:
        tasks = await get_overdue_tasks(session)
        for task in tasks:
            await update_task_status(session, task.id, task.created_by, TaskStatus.overdue, "auto overdue")
            if task.assigned_to:
                try:
                    assignee = await get_staff_by_id(session, task.assigned_to)
                    if assignee:
                        await _bot.send_message(
                            assignee.telegram_id,
                            f"⚠️ Задача просрочена!\n\n"
                            f"<b>{task.title}</b> (ID: {task.id})\n"
                            f"Дедлайн: {task.deadline.strftime('%d.%m.%Y %H:%M') if task.deadline else '—'}",
                            parse_mode="HTML",
                        )
                except Exception as e:
                    logger.warning("Failed to notify assignee: %s", e)
            for admin_tg_id in _admin_ids:
                try:
                    await _bot.send_message(
                        admin_tg_id,
                        f"⚠️ Задача просрочена!\n\n<b>{task.title}</b> (ID: {task.id})",
                        parse_mode="HTML",
                    )
                except Exception as e:
                    logger.warning("Failed to notify admin: %s", e)
    if tasks:
        logger.info("Marked %d tasks as overdue", len(tasks))


# ── Recurring tasks ───────────────────────────────────────────────────────────

async def spawn_recurring():
    if _bot is None:
        return
    async with async_session_factory() as session:
        templates = await get_recurring_tasks(session)
        for t in templates:
            new_task = await create_task(
                session,
                title=t.title,
                created_by=t.created_by,
                session_id=t.session_id,
                description=t.description,
                assigned_to=t.assigned_to,
                group_role=t.group_role,
                priority=t.priority,
                is_recurring=t.is_recurring,
                recurrence_type=t.recurrence_type,
                template_id=t.template_id,
            )
            await add_task_log(session, new_task.id, t.created_by, f"spawned from recurring task {t.id}")
            if new_task.assigned_to:
                try:
                    assignee = await get_staff_by_id(session, new_task.assigned_to)
                    if assignee:
                        from app.bot.handlers.tasks import _task_text
                        kb = task_action_kb(new_task.id, new_task.status, is_assignee=True)
                        await _bot.send_message(
                            assignee.telegram_id,
                            f"📋 Повторяющаяся задача!\n\n{_task_text(new_task)}",
                            reply_markup=kb,
                            parse_mode="HTML",
                        )
                except Exception as e:
                    logger.warning("Failed to notify for recurring task: %s", e)
    if templates:
        logger.info("Spawned %d recurring tasks", len(templates))


# ── Morning digest ────────────────────────────────────────────────────────────

async def morning_digest():
    if _bot is None:
        return
    async with async_session_factory() as session:
        sess = await get_active_session(session)
        if not sess:
            return
        all_staff = await get_all_active_staff(session)
        birthday_pairs = await get_birthdays_range(session)
        circles = await get_today_circles(session)

    today_str = date.today().strftime("%d.%m.%Y")
    lines = [f"☀️ <b>Доброе утро! {today_str}</b>"]
    today_birthdays = [c for d, c in birthday_pairs if d == date.today()]
    if today_birthdays:
        names = ", ".join(c.full_name for c in today_birthdays)
        lines.append(f"🎂 Именинники: {names}")
    if circles:
        lines.append(f"🧩 Кружков сегодня: {len(circles)}")

    text = "\n".join(lines)
    for s in all_staff:
        try:
            await _bot.send_message(s.telegram_id, text, parse_mode="HTML")
        except Exception:
            pass


# ── Evening report ────────────────────────────────────────────────────────────

async def evening_report():
    if _bot is None:
        return
    async with async_session_factory() as session:
        sess = await get_active_session(session)
        if not sess:
            return
        stats = await get_session_stats(session, sess.id)
        all_staff = await get_all_active_staff(session)

    done = stats["done_tasks"]
    total = stats["total_tasks"]
    pct = round(done / total * 100) if total else 0
    text = (
        f"🌙 <b>Итоги дня</b>\n\n"
        f"📋 Задачи: {done}/{total} ({pct}%)\n"
        f"🎉 Мероприятий: {stats['total_events']}\n"
        f"🚨 Инцидентов: {stats['total_incidents']}"
    )
    for s in all_staff:
        if s.role in _ADMIN_ROLES:
            try:
                await _bot.send_message(s.telegram_id, text, parse_mode="HTML")
            except Exception:
                pass


# ── Reminders ─────────────────────────────────────────────────────────────────

async def send_pending_reminders():
    if _bot is None:
        return
    async with async_session_factory() as session:
        reminders = await get_pending_reminders(session)
        for r in reminders:
            try:
                s = await get_staff_by_id(session, r.staff_id)
                if s:
                    await _bot.send_message(s.telegram_id, f"🔔 {r.text}", parse_mode="HTML")
                await mark_reminder_sent(session, r.id)
            except Exception as e:
                logger.warning("Reminder send failed: %s", e)


# ── Birthdays ─────────────────────────────────────────────────────────────────

async def birthday_check():
    if _bot is None:
        return
    async with async_session_factory() as session:
        birthday_pairs = await get_birthdays_range(session, 1)
        children = [c for d, c in birthday_pairs if d == date.today()]
        if not children:
            return
        all_staff = await get_all_active_staff(session)

    names = ", ".join(c.full_name for c in children)
    text = f"🎂 <b>Именинники сегодня:</b> {names}"
    for s in all_staff:
        if s.role in _ADMIN_ROLES:
            try:
                await _bot.send_message(s.telegram_id, text, parse_mode="HTML")
            except Exception:
                pass


# ── Circle reminders (15 min before) ─────────────────────────────────────────

async def circle_reminders():
    if _bot is None:
        return
    now = datetime.now()
    target = (now + timedelta(minutes=15)).time()
    target_dow = now.weekday()
    async with async_session_factory() as session:
        sess = await get_active_session(session)
        if not sess:
            return
        circles = await get_today_circles(session)

    for circle in circles:
        for sched in circle.schedule:
            if sched.day_of_week == target_dow:
                t = sched.time
                if abs((t.hour * 60 + t.minute) - (target.hour * 60 + target.minute)) <= 2:
                    if circle.leader:
                        try:
                            await _bot.send_message(
                                circle.leader.telegram_id,
                                f"🧩 Через 15 минут кружок <b>{circle.name}</b>!",
                                parse_mode="HTML",
                            )
                        except Exception:
                            pass


# ── Duty reminders (morning-of notification) ─────────────────────────────────

async def duty_reminders():
    if _bot is None:
        return
    from app.db.models import DutyStatus
    today = date.today()
    async with async_session_factory() as session:
        sess = await get_active_session(session)
        if not sess:
            return
        from app.db.crud import get_duties_by_date
        duties = await get_duties_by_date(session, today, sess.id)

    for duty in duties:
        if duty.status == DutyStatus.scheduled and duty.staff and duty.staff.telegram_id:
            try:
                from app.db.models import DUTY_TYPE_LABELS
                type_label = DUTY_TYPE_LABELS.get(duty.type, str(duty.type))
                await _bot.send_message(
                    duty.staff.telegram_id,
                    f"🔔 Напоминание: сегодня у вас дежурство <b>{type_label}</b>.",
                    parse_mode="HTML",
                )
            except Exception as e:
                logger.warning("Failed to send duty reminder: %s", e)


# ── Night duty missed checkpoint alert ───────────────────────────────────────

async def check_night_duties():
    if _bot is None:
        return
    async with async_session_factory() as session:
        duties = await get_night_duties_active(session)

    for duty in duties:
        last_cp = max(duty.checkpoints, key=lambda c: c.confirmed_at, default=None) if duty.checkpoints else None
        midnight = datetime.combine(date.today(), datetime.min.time()).replace(tzinfo=timezone.utc)
        if last_cp is None or last_cp.confirmed_at < midnight:
            for admin_tg_id in _admin_ids:
                try:
                    await _bot.send_message(
                        admin_tg_id,
                        f"⚠️ Ночное дежурство (ID: {duty.id}) — нет отметки с полуночи!",
                        parse_mode="HTML",
                    )
                except Exception as e:
                    logger.warning("Failed to alert night duty: %s", e)
