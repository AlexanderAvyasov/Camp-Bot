import logging
from datetime import datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.db.base import async_session_factory
from app.db.crud import (
    add_task_log,
    create_task,
    get_overdue_tasks,
    get_recurring_tasks,
    get_staff_by_id,
    update_task_status,
)
from app.db.models import TaskStatus

logger = logging.getLogger(__name__)

_bot = None
_admin_ids: list[int] = []


def setup_scheduler(bot, admin_telegram_ids: list[int]) -> AsyncIOScheduler:
    global _bot, _admin_ids
    _bot = bot
    _admin_ids = admin_telegram_ids

    scheduler = AsyncIOScheduler(timezone="UTC")
    scheduler.add_job(check_overdue, "interval", minutes=10, id="overdue_check")
    scheduler.add_job(spawn_recurring, "cron", hour=0, minute=1, id="recurring_spawn")
    return scheduler


async def check_overdue():
    if _bot is None:
        return
    async with async_session_factory() as session:
        tasks = await get_overdue_tasks(session)
        for task in tasks:
            await update_task_status(session, task.id, task.created_by, TaskStatus.overdue, "auto overdue")
            # Notify assignee
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
            # Notify admins
            for admin_tg_id in _admin_ids:
                try:
                    await _bot.send_message(
                        admin_tg_id,
                        f"⚠️ Задача просрочена!\n\n"
                        f"<b>{task.title}</b> (ID: {task.id})",
                        parse_mode="HTML",
                    )
                except Exception as e:
                    logger.warning("Failed to notify admin: %s", e)

    if tasks:
        logger.info("Marked %d tasks as overdue", len(tasks))


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
                        from app.bot.handlers.tasks import _task_text, _task_inline_kb
                        kb = _task_inline_kb(new_task.id, is_assignee=True)
                        await _bot.send_message(
                            assignee.telegram_id,
                            f"📋 Повторяющаяся задача!\n\n"
                            f"{_task_text(new_task, show_assignee=False)}",
                            reply_markup=kb,
                            parse_mode="HTML",
                        )
                except Exception as e:
                    logger.warning("Failed to notify for recurring task: %s", e)
    if templates:
        logger.info("Spawned %d recurring tasks", len(templates))
