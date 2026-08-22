from typing import Any, Awaitable, Callable, Dict, MutableMapping, Optional
from datetime import datetime, timedelta
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery, TelegramObject
from aiogram.dispatcher.flags import get_flag
import asyncio

from bot.utils.logger import logger

class ThrottlingMiddleware(BaseMiddleware):
    """Мидлварь для ограничения частоты запросов"""
    
    def __init__(self, default_rate: float = 0.5):
        self.default_rate = default_rate
        self.users: Dict[int, datetime] = {}
        self.lock = asyncio.Lock()
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        user_id = self._get_user_id(event)
        if not user_id:
            return await handler(event, data)
        
        # Проверяем rate limit
        async with self.lock:
            now = datetime.now()
            if user_id in self.users:
                time_passed = (now - self.users[user_id]).total_seconds()
                if time_passed < self.default_rate:
                    logger.warning(f"Throttled user {user_id}")
                    if isinstance(event, CallbackQuery):
                        await event.answer("Слишком часто! Подождите секунду.", show_alert=True)
                    return
            self.users[user_id] = now
        
        return await handler(event, data)
    
    def _get_user_id(self, event: TelegramObject) -> Optional[int]:
        if isinstance(event, Message):
            return event.from_user.id
        elif isinstance(event, CallbackQuery):
            return event.from_user.id
        return None