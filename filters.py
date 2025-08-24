from aiogram.filters import BaseFilter
from aiogram.types import Message, ChatType, CallbackQuery
from typing import Union, Optional
import asyncio
from config import Config
from storage import get_user_level

class IsPrivateChat(BaseFilter):
    """Фильтр для проверки приватного чата"""
    async def __call__(self, message: Message) -> bool:
        return message.chat.type == ChatType.PRIVATE

class IsOwnerOrPrivate(BaseFilter):
    """Фильтр: либо владелец, либо приватный чат"""
    async def __call__(self, message: Message) -> bool:
        user_id = message.from_user.id
        user_level = get_user_level(user_id)
        
        # Владелец может писать везде
        if user_level == 3:  # Владелец
            return True
        
        # Остальные только в личных сообщениях
        return message.chat.type == ChatType.PRIVATE

class IsOwnerAndAdmin(BaseFilter):
    """Фильтр: владелец и бот является администратором"""
    async def __call__(self, message: Message) -> bool:
        user_id = message.from_user.id
        user_level = get_user_level(user_id)
        
        # Только владелец
        if user_level != 3:
            return False
        
        # Проверяем, что бот является администратором в этом чате
        try:
            chat_member = await message.bot.get_chat_member(
                message.chat.id, 
                message.bot.id
            )
            return chat_member.status in ['administrator', 'creator']
        except:
            return False

class IsOwnerAnywhere(BaseFilter):
    """Фильтр: владелец в любом чате"""
    async def __call__(self, message: Message) -> bool:
        user_id = message.from_user.id
        user_level = get_user_level(user_id)
        return user_level == 3  # Только владелец

class IsPrivateOrOwnerAdmin(BaseFilter):
    """Фильтр: либо приватный чат, либо владелец с правами администратора"""
    async def __call__(self, message: Message) -> bool:
        user_id = message.from_user.id
        user_level = get_user_level(user_id)
        
        # Все пользователи в личных сообщениях
        if message.chat.type == ChatType.PRIVATE:
            return True
        
        # Владелец с правами администратора
        if user_level == 3:
            try:
                chat_member = await message.bot.get_chat_member(
                    message.chat.id, 
                    message.bot.id
                )
                return chat_member.status in ['administrator', 'creator']
            except:
                return False
        
        return False

class IsModerator(BaseFilter):
    """Фильтр: модератор или выше"""
    async def __call__(self, message: Message) -> bool:
        user_id = message.from_user.id
        user_level = get_user_level(user_id)
        return user_level >= 1  # Модератор и выше

class IsTechModerator(BaseFilter):
    """Фильтр: технический модератор или выше"""
    async def ____call__(self, message: Message) -> bool:
        user_id = message.from_user.id
        user_level = get_user_level(user_id)
        return user_level >= 2  # Технический модератор и выше

class IsOwner(BaseFilter):
    """Фильтр: только владелец"""
    async def __call__(self, message: Message) -> bool:
        user_id = message.from_user.id
        user_level = get_user_level(user_id)
        return user_level == 3  # Только владелец

class RateLimitFilter(BaseFilter):
    def __init__(self, limit: int = 5, period: int = 60):
        self.limit = limit
        self.period = period
        self.user_messages = {}

    async def __call__(self, message: Message) -> bool:
        user_id = message.from_user.id
        now = asyncio.get_event_loop().time()
        
        if user_id not in self.user_messages:
            self.user_messages[user_id] = []
        
        # Удаляем старые сообщения
        self.user_messages[user_id] = [
            ts for ts in self.user_messages[user_id] 
            if now - ts < self.period
        ]
        
        if len(self.user_messages[user_id]) >= self.limit:
            await message.answer("🚫 Слишком много запросов. Подождите немного.")
            return False
        
        self.user_messages[user_id].append(now)
        return True

class CallbackOwnerFilter(BaseFilter):
    """Фильтр для callback'ов: только владелец"""
    async def __call__(self, callback: CallbackQuery) -> bool:
        user_id = callback.from_user.id
        user_level = get_user_level(user_id)
        return user_level == 3
