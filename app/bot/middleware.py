from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject

from app.db.base import async_session_factory
from app.db.crud import get_staff_by_telegram_id
from app.db.models import StaffRole


class StaffMiddleware(BaseMiddleware):
    """Attaches Staff object to handler data. Blocks inactive staff."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user = data.get("event_from_user")
        if user is None:
            return await handler(event, data)

        async with async_session_factory() as session:
            staff = await get_staff_by_telegram_id(session, user.id)
            data["session"] = session
            data["staff"] = staff

            if staff is not None and not staff.is_active:
                if isinstance(event, Message):
                    await event.answer(
                        "⛔ Ваш аккаунт деактивирован. Обратитесь к администратору."
                    )
                return

            return await handler(event, data)


def require_role(*roles: StaffRole):
    """Decorator for handlers that restricts access by role."""

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
