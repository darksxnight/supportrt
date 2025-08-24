import asyncio
import datetime
from typing import Dict, List
from aiogram import Bot
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)

@dataclass
class Punishment:
    user_id: int
    punishment_type: str  # 'mute', 'warning', 'ban'
    duration: int  # seconds
    reason: str
    moderator_id: int
    created_at: datetime.datetime
    expires_at: datetime.datetime

class PunishmentSystem:
    def __init__(self, bot: Bot):
        self.bot = bot
        self.active_punishments: Dict[int, Punishment] = {}
        self.task = None
    
    async def add_punishment(self, punishment: Punishment):
        self.active_punishments[punishment.user_id] = punishment
        
        if punishment.punishment_type == 'mute':
            await self.apply_mute(punishment)
        elif punishment.punishment_type == 'ban':
            await self.apply_ban(punishment)
        
        # Сохраняем в Redis
        from redis_storage import redis_storage
        redis_storage.add_punishment(punishment.user_id, {
            'type': punishment.punishment_type,
            'duration': punishment.duration,
            'reason': punishment.reason,
            'moderator_id': punishment.moderator_id,
            'created_at': punishment.created_at.isoformat(),
            'expires_at': punishment.expires_at.isoformat()
        })
    
    async def apply_mute(self, punishment: Punishment):
        try:
            # Здесь реализация заглушки пользователя
            logger.info(f"User {punishment.user_id} muted for {punishment.duration} seconds")
        except Exception as e:
            logger.error(f"Error applying mute: {e}")
    
    async def apply_ban(self, punishment: Punishment):
        try:
            # Здесь реализация бана пользователя
            logger.info(f"User {punishment.user_id} banned for {punishment.duration} seconds")
        except Exception as e:
            logger.error(f"Error applying ban: {e}")
    
    async def remove_punishment(self, user_id: int):
        if user_id in self.active_punishments:
            punishment = self.active_punishments[user_id]
            
            if punishment.punishment_type == 'mute':
                await self.remove_mute(punishment)
            elif punishment.punishment_type == 'ban':
                await self.remove_ban(punishment)
            
            del self.active_punishments[user_id]
    
    async def check_expired_punishments(self):
        now = datetime.datetime.now()
        expired = []
        
        for user_id, punishment in self.active_punishments.items():
            if now >= punishment.expires_at:
                expired.append(user_id)
        
        for user_id in expired:
            await self.remove_punishment(user_id)
            logger.info(f"Punishment expired for user {user_id}")
    
    async def start(self):
        """Запуск фоновой задачи проверки наказаний"""
        self.task = asyncio.create_task(self._background_check())
    
    async def _background_check(self):
        while True:
            try:
                await self.check_expired_punishments()
                await asyncio.sleep(60)  # Проверка каждую минуту
            except Exception as e:
                logger.error(f"Error in punishment background check: {e}")
                await asyncio.sleep(60)
    
    async def stop(self):
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
