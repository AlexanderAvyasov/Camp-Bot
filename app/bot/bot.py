import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from app.bot.handlers import (
    admin, analytics, broadcast, children, checklists, circles,
    duties, events, incidents, menu, reports, sessions, squads, start, tasks,
)
from app.bot.middleware import StaffMiddleware
from app.bot.scheduler import setup_scheduler
from app.config import settings
from app.db.base import async_session_factory
from app.db.crud import get_all_active_staff
from app.db.models import StaffRole

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_bot_instance: Bot | None = None


def get_bot() -> Bot | None:
    return _bot_instance


async def _get_admin_telegram_ids() -> list[int]:
    async with async_session_factory() as session:
        all_staff = await get_all_active_staff(session)
        return [s.telegram_id for s in all_staff if s.role == StaffRole.admin]


async def main():
    global _bot_instance
    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    _bot_instance = bot
    dp = Dispatcher(storage=MemoryStorage())

    dp.message.middleware(StaffMiddleware())
    dp.callback_query.middleware(StaffMiddleware())

    dp.include_router(start.router)
    dp.include_router(menu.router)
    dp.include_router(admin.router)
    dp.include_router(sessions.router)
    dp.include_router(squads.router)
    dp.include_router(tasks.router)
    dp.include_router(events.router)
    dp.include_router(children.router)
    dp.include_router(broadcast.router)
    dp.include_router(incidents.router)
    dp.include_router(duties.router)
    dp.include_router(checklists.router)
    dp.include_router(analytics.router)
    dp.include_router(circles.router)
    dp.include_router(reports.router)

    admin_ids = await _get_admin_telegram_ids()
    scheduler = setup_scheduler(bot, admin_ids)
    scheduler.start()
    logger.info("Scheduler started with %d admin(s)", len(admin_ids))

    logger.info("Starting bot...")
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        scheduler.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
