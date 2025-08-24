import redis
import json
import pickle
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

class RedisStorage:
    def __init__(self, redis_url: str = "redis://localhost:6379/0"):
        self.redis = redis.from_url(redis_url, decode_responses=True)
        self.prefix = "anon_bot:"
    
    def _key(self, name: str) -> str:
        return f"{self.prefix}{name}"
    
    # User levels
    def get_user_level(self, user_id: int) -> int:
        key = self._key(f"user:{user_id}:level")
        level = self.redis.get(key)
        return int(level) if level else 0
    
    def set_user_level(self, user_id: int, level: int):
        key = self._key(f"user:{user_id}:level")
        self.redis.set(key, level)
    
    def get_all_user_levels(self) -> Dict[int, int]:
        keys = self.redis.keys(self._key("user:*:level"))
        result = {}
        for key in keys:
            user_id = int(key.split(":")[1])
            level = int(self.redis.get(key))
            result[user_id] = level
        return result
    
    # Moderator stats
    def get_moderator_stats(self, moderator_id: int) -> Dict[str, int]:
        key = self._key(f"mod:{moderator_id}:stats")
        stats = self.redis.hgetall(key)
        return {k: int(v) for k, v in stats.items()} if stats else {
            'approved': 0, 'rejected': 0, 'reviewed': 0, 'warnings': 0
        }
    
    def update_moderator_stats(self, moderator_id: int, action: str):
        key = self._key(f"mod:{moderator_id}:stats")
        self.redis.hincrby(key, action, 1)
        self.redis.hincrby(key, 'reviewed', 1)
    
    # Pending messages
    def add_message(self, message_data: Dict[str, Any]) -> int:
        message_id = self.redis.incr(self._key("message_counter"))
        key = self._key(f"pending:{message_id}")
        self.redis.hset(key, mapping=message_data)
        self.redis.expire(key, 3600)  # 1 hour expiration
        return message_id
    
    def get_message(self, message_id: int) -> Optional[Dict[str, Any]]:
        key = self._key(f"pending:{message_id}")
        return self.redis.hgetall(key)
    
    def delete_message(self, message_id: int):
        key = self._key(f"pending:{message_id}")
        self.redis.delete(key)
    
    def get_all_pending_messages(self) -> Dict[int, Dict[str, Any]]:
        keys = self.redis.keys(self._key("pending:*"))
        result = {}
        for key in keys:
            message_id = int(key.split(":")[1])
            result[message_id] = self.redis.hgetall(key)
        return result
    
    # Punishments
    def add_punishment(self, user_id: int, punishment_data: Dict[str, Any]):
        key = self._key(f"punishments:{user_id}")
        self.redis.rpush(key, json.dumps(punishment_data))
    
    def get_punishments(self, user_id: int) -> List[Dict[str, Any]]:
        key = self._key(f"punishments:{user_id}")
        punishments = self.redis.lrange(key, 0, -1)
        return [json.loads(p) for p in punishments]
    
    # Rate limiting
    def check_rate_limit(self, user_id: int, limit: int, period: int) -> bool:
        key = self._key(f"ratelimit:{user_id}")
        current = self.redis.llen(key)
        
        if current >= limit:
            return False
        
        self.redis.rpush(key, datetime.now().isoformat())
        self.redis.expire(key, period)
        return True
    
    def cleanup_old_data(self):
        """Очистка старых данных"""
        # Автоматически выполняется через expire
        pass

# Глобальный экземпляр
redis_storage = RedisStorage()
