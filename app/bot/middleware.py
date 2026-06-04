import time
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject

from app.db.base import async_session_factory
from app.db.crud import get_staff_by_telegram_id
from app.db.models import StaffRole

# In-memory staff cache: {telegram_id: (staff_obj, expire_timestamp)}
_staff_cache: dict[int, tuple[Any, float]] = {}
_CACHE_TTL = 60.0  # seconds


def _cache_get(telegram_id: int):
    entry = _staff_cache.get(telegram_id)
    if entry and time.monotonic() < entry[1]:
        return entry[0]
    return None


def _cache_set(telegram_id: int, staff):
    _staff_cache[telegram_id] = (staff, time.monotonic() + _CACHE_TTL)


def invalidate_staff_cache(telegram_id: int):
    """Call this after updating a staff record so next request re-fetches."""
    _staff_cache.pop(telegram_id, None)


class StaffMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user = data.get("event_from_user")
        if user is None:
            return await handler(event, data)

        staff = _cache_get(user.id)

        if staff is None:
            async with async_session_factory() as session:
                staff = await get_staff_by_telegram_id(session, user.id)
            _cache_set(user.id, staff)

        data["staff"] = staff

        if staff is not None and not staff.is_active:
            if isinstance(event, Message):
                await event.answer("⛔ Ваш аккаунт деактивирован. Обратитесь к администратору.")
            return

        return await handler(event, data)


def require_role(*roles: StaffRole):
    def decorator(handler: Callable):
        async def wrapper(message: Message, staff=None, **kwargs):
            if staff is None:
                await message.answer("❌ Вы не зарегистрированы в системе.")
                return
            if staff.role not in roles:
                await message.answer("⛔ У вас нет прав для выполнения этой команды.")
                return
            return await handler(message, staff=staff, **kwargs)

        wrapper.__wrapped__ = handler
        return wrapper

    return decorator
