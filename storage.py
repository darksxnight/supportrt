import threading
import logging
import datetime
import asyncio
from typing import Dict, Any, Optional, List
from aiogram import Bot

logger = logging.getLogger(__name__)

class ThreadSafeDict:
    def __init__(self, name: str):
        self._data = {}
        self._lock = threading.RLock()
        self._name = name
    
    def get(self, key, default=None):
        with self._lock:
            return self._data.get(key, default)
    
    def set(self, key, value):
        with self._lock:
            self._data[key] = value
    
    def delete(self, key):
        with self._lock:
            if key in self._data:
                del self._data[key]
                return True
            return False
    
    def items(self):
        with self._lock:
            return list(self._data.items())
    
    def clear(self):
        with self._lock:
            self._data.clear()
    
    def __len__(self):
        with self._lock:
            return len(self._data)

pending_messages = ThreadSafeDict("pending_messages")
user_levels = ThreadSafeDict("user_levels")
moderator_stats = ThreadSafeDict("moderator_stats")
punishments = ThreadSafeDict("punishments")
user_last_message = ThreadSafeDict("user_last_message")
active_punishments = ThreadSafeDict("active_punishments")

class Punishment:
    def __init__(self, user_id: int, punishment_type: str, duration: int, 
                 reason: str, moderator_id: int, created_at: datetime.datetime = None):
        self.user_id = user_id
        self.type = punishment_type
        self.duration = duration
        self.reason = reason
        self.moderator_id = moderator_id
        self.created_at = created_at or datetime.datetime.now()
        self.expires_at = self.created_at + datetime.timedelta(seconds=duration)
    
    def is_expired(self) -> bool:
        return datetime.datetime.now() > self.expires_at
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'user_id': self.user_id,
            'type': self.type,
            'duration': self.duration,
            'reason': self.reason,
            'moderator_id': self.moderator_id,
            'created_at': self.created_at.isoformat(),
            'expires_at': self.expires_at.isoformat()
        }

class PunishmentSystem:
    def __init__(self, bot: Bot):
        self.bot = bot
        self.running = False
    
    async def start(self):
        self.running = True
        asyncio.create_task(self._punishment_checker())
        logger.info("Punishment system started")
    
    async def stop(self):
        self.running = False
        logger.info("Punishment system stopped")
    
    async def add_punishment(self, punishment: Punishment):
        active_punishments.set(punishment.user_id, punishment)
        logger.info(f"Punishment applied: {punishment.type} for user {punishment.user_id}")
    
    async def remove_punishment(self, user_id: int):
        punishment = active_punishments.get(user_id)
        if punishment:
            active_punishments.delete(user_id)
            logger.info(f"Punishment removed for user {user_id}")
    
    async def _punishment_checker(self):
        while self.running:
            try:
                current_time = datetime.datetime.now()
                expired_punishments = []
                
                for user_id, punishment in active_punishments.items():
                    if punishment.is_expired():
                        expired_punishments.append(user_id)
                
                for user_id in expired_punishments:
                    await self.remove_punishment(user_id)
                
                await asyncio.sleep(60)
            except Exception as e:
                logger.error(f"Punishment checker error: {e}")
                await asyncio.sleep(60)

punishment_system = None

def init_punishment_system(bot: Bot):
    global punishment_system
    punishment_system = PunishmentSystem(bot)
    return punishment_system

def add_message(message_data: Dict[str, Any]) -> int:
    message_id = len(pending_messages) + 1
    message_data['created_at'] = datetime.datetime.now().isoformat()
    pending_messages.set(message_id, message_data)
    logger.info(f"Message added: ID {message_id} from user {message_data.get('user_id')}")
    return message_id

def get_message(message_id: int) -> Optional[Dict[str, Any]]:
    message = pending_messages.get(message_id)
    if not message:
        logger.debug(f"Message not found: ID {message_id}")
    return message

def delete_message(message_id: int) -> bool:
    result = pending_messages.delete(message_id)
    if result:
        logger.info(f"Message deleted: ID {message_id}")
    else:
        logger.debug(f"Message already deleted: ID {message_id}")
    return result

def get_all_messages() -> Dict[int, Dict[str, Any]]:
    return {k: v for k, v in pending_messages.items()}

def set_user_level(user_id: int, level: int):
    user_levels.set(user_id, level)

def get_user_level(user_id: int) -> int:
    return user_levels.get(user_id, 0)

def update_moderator_stats(moderator_id: int, action: str):
    stats = moderator_stats.get(moderator_id, {'approved': 0, 'rejected': 0, 'reviewed': 0, 'warnings': 0})
    
    if action == 'approve':
        stats['approved'] += 1
        stats['reviewed'] += 1
    elif action == 'reject':
        stats['rejected'] += 1
        stats['reviewed'] += 1
    
    moderator_stats.set(moderator_id, stats)

def add_warning(moderator_id: int):
    stats = moderator_stats.get(moderator_id, {'approved': 0, 'rejected': 0, 'reviewed': 0, 'warnings': 0})
    stats['warnings'] += 1
    moderator_stats.set(moderator_id, stats)

def add_punishment(user_id: int, punishment_type: str, reason: str = ""):
    punish_data = punishments.get(user_id, {'mutes': 0, 'warnings': 0, 'bans': 0, 'reason': reason})
    
    if punishment_type == 'mute':
        punish_data['mutes'] += 1
    elif punishment_type == 'warning':
        punish_data['warnings'] += 1
    elif punishment_type == 'ban':
        punish_data['bans'] += 1
    
    punishments.set(user_id, punish_data)

def get_punishments(user_id: int) -> Dict[str, Any]:
    return punishments.get(user_id, {'mutes': 0, 'warnings': 0, 'bans': 0, 'reason': ''})

def can_send_message(user_id: int) -> bool:
    from config import Config
    last_message_time = user_last_message.get(user_id)
    
    if not last_message_time:
        user_last_message.set(user_id, datetime.datetime.now())
        return True
    
    time_diff = (datetime.datetime.now() - last_message_time).total_seconds()
    if time_diff < 3600 / Config.MAX_MESSAGES_PER_HOUR:
        return False
    
    user_last_message.set(user_id, datetime.datetime.now())
    return True