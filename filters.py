from aiogram.filters import BaseFilter
from aiogram.types import Message, CallbackQuery
from datetime import datetime, timedelta
from functools import wraps
import asyncio
import logging

logger = logging.getLogger(__name__)

class RateLimitFilter(BaseFilter):
    def __init__(self, limit: int = 5, period: int = 60):
        self.limit = limit
        self.period = period
        self.user_messages = {}

    async def __call__(self, message: Message) -> bool:
        user_id = message.from_user.id
        now = datetime.now()
        
        if user_id not in self.user_messages:
            self.user_messages[user_id] = []
        
        # Удаляем старые сообщения
        self.user_messages[user_id] = [
            ts for ts in self.user_messages[user_id] 
            if now - ts < timedelta(seconds=self.period)
        ]
        
        if len(self.user_messages[user_id]) >= self.limit:
            await message.answer("🚫 Слишком много запросов. Подождите немного.")
            return False
        
        self.user_messages[user_id].append(now)
        return True

def require_level(required_level: int):
    def decorator(func):
        @wraps(func)
        async def wrapper(message: Message, *args, **kwargs):
            from storage import get_user_level
            user_level = get_user_level(message.from_user.id)
            if user_level < required_level:
                await message.answer("❌ Недостаточно прав")
                return
            return await func(message, *args, **kwargs)
        return wrapper
    return decorator

def require_level_callback(required_level: int):
    def decorator(func):
        @wraps(func)
        async def wrapper(callback: CallbackQuery, *args, **kwargs):
            from storage import get_user_level
            user_level = get_user_level(callback.from_user.id)
            if user_level < required_level:
                await callback.answer("❌ Недостаточно прав", show_alert=True)
                return
            return await func(callback, *args, **kwargs)
        return wrapper
    return decorator
