import redis
import json
import pickle
from typing import Dict, Any, List, Optional, Union
from datetime import datetime, timedelta
import logging
import asyncio

logger = logging.getLogger(__name__)

class RedisStorage:
    def __init__(self, redis_url: str = "redis://localhost:6379/0"):
        try:
            self.redis = redis.from_url(redis_url, decode_responses=False)
            self.prefix = "anon_bot:"
            self.redis.ping()  # Проверка подключения
            logger.info("✅ Redis подключен успешно")
        except Exception as e:
            logger.error(f"❌ Ошибка подключения к Redis: {e}")
            raise
    
    def _key(self, name: str) -> str:
        return f"{self.prefix}{name}"
    
    # ==================== КЭШИРОВАНИЕ ДАННЫХ ====================
    
    def cache_get(self, key: str, default: Any = None) -> Any:
        """Получить данные из кэша"""
        try:
            data = self.redis.get(self._key(f"cache:{key}"))
            if data:
                return pickle.loads(data)
            return default
        except Exception as e:
            logger.error(f"❌ Redis cache get error: {e}")
            return default
    
    def cache_set(self, key: str, value: Any, ttl: int = 300) -> bool:
        """Установить данные в кэш"""
        try:
            serialized = pickle.dumps(value)
            if ttl > 0:
                self.redis.setex(self._key(f"cache:{key}"), ttl, serialized)
            else:
                self.redis.set(self._key(f"cache:{key}"), serialized)
            return True
        except Exception as e:
            logger.error(f"❌ Redis cache set error: {e}")
            return False
    
    def cache_delete(self, key: str) -> bool:
        """Удалить данные из кэша"""
        try:
            return self.redis.delete(self._key(f"cache:{key}")) > 0
        except Exception as e:
            logger.error(f"❌ Redis cache delete error: {e}")
            return False
    
    def cache_delete_pattern(self, pattern: str) -> int:
        """Удалить данные по шаблону"""
        try:
            keys = self.redis.keys(self._key(f"cache:{pattern}"))
            if keys:
                return self.redis.delete(*keys)
            return 0
        except Exception as e:
            logger.error(f"❌ Redis cache delete pattern error: {e}")
            return 0
    
    def cache_get_size(self) -> Dict[str, int]:
        """Получить размер кэша"""
        try:
            cache_keys = self.redis.keys(self._key("cache:*"))
            return {
                'total_keys': len(cache_keys),
                'memory_usage': self.redis.memory_usage(self._key("cache:") + "*") if cache_keys else 0
            }
        except Exception as e:
            logger.error(f"❌ Redis cache size error: {e}")
            return {'total_keys': 0, 'memory_usage': 0}
    
    # ==================== RATE LIMITING ====================
    
    def check_rate_limit(self, key: str, limit: int, period: int) -> bool:
        """Проверить rate limit"""
        try:
            redis_key = self._key(f"ratelimit:{key}")
            current = self.redis.llen(redis_key)
            
            if current >= limit:
                return False
            
            # Добавляем текущее время в список
            self.redis.rpush(redis_key, datetime.now().isoformat())
            # Устанавливаем время жизни для всего списка
            self.redis.expire(redis_key, period)
            return True
            
        except Exception as e:
            logger.error(f"❌ Redis rate limit error: {e}")
            return True
    
    def get_rate_limit_info(self, key: str) -> Dict[str, Any]:
        """Получить информацию о rate limit"""
        try:
            redis_key = self._key(f"ratelimit:{key}")
            requests = self.redis.lrange(redis_key, 0, -1)
            ttl = self.redis.ttl(redis_key)
            
            return {
                'current': len(requests),
                'requests': [req.decode('utf-8') for req in requests],
                'ttl': ttl,
                'limit_reached': len(requests) >= 5  # Пример лимита
            }
        except Exception as e:
            logger.error(f"❌ Redis rate limit info error: {e}")
            return {'current': 0, 'requests': [], 'ttl': -1, 'limit_reached': False}
    
    def clear_rate_limit(self, key: str) -> bool:
        """Очистить rate limit для ключа"""
        try:
            return self.redis.delete(self._key(f"ratelimit:{key}")) > 0
        except Exception as e:
            logger.error(f"❌ Redis rate limit clear error: {e}")
            return False
    
    # ==================== ОЧЕРЕДИ СООБЩЕНИЙ ====================
    
    def queue_push(self, queue_name: str, message: Dict[str, Any]) -> bool:
        """Добавить сообщение в очередь"""
        try:
            serialized = json.dumps(message, ensure_ascii=False)
            self.redis.rpush(self._key(f"queue:{queue_name}"), serialized)
            return True
        except Exception as e:
            logger.error(f"❌ Redis queue push error: {e}")
            return False
    
    def queue_pop(self, queue_name: str, timeout: int = 0) -> Optional[Dict[str, Any]]:
        """Извлечь сообщение из очереди"""
        try:
            if timeout > 0:
                result = self.redis.blpop(self._key(f"queue:{queue_name}"), timeout)
                if result:
                    _, data = result
                    return json.loads(data.decode('utf-8'))
                return None
            else:
                data = self.redis.lpop(self._key(f"queue:{queue_name}"))
                return json.loads(data.decode('utf-8')) if data else None
        except Exception as e:
            logger.error(f"❌ Redis queue pop error: {e}")
            return None
    
    def queue_bulk_pop(self, queue_name: str, count: int = 10) -> List[Dict[str, Any]]:
        """Извлечь несколько сообщений из очереди"""
        try:
            with self.redis.pipeline() as pipe:
                pipe.lrange(self._key(f"queue:{queue_name}"), 0, count - 1)
                pipe.ltrim(self._key(f"queue:{queue_name}"), count, -1)
                results = pipe.execute()
                
                if results[0]:
                    return [json.loads(item.decode('utf-8')) for item in results[0]]
                return []
        except Exception as e:
            logger.error(f"❌ Redis queue bulk pop error: {e}")
            return []
    
    def queue_length(self, queue_name: str) -> int:
        """Получить длину очереди"""
        try:
            return self.redis.llen(self._key(f"queue:{queue_name}"))
        except Exception as e:
            logger.error(f"❌ Redis queue length error: {e}")
            return 0
    
    def queue_clear(self, queue_name: str) -> bool:
        """Очистить очередь"""
        try:
            return self.redis.delete(self._key(f"queue:{queue_name}")) > 0
        except Exception as e:
            logger.error(f"❌ Redis queue clear error: {e}")
            return False
    
    def get_queue_info(self, queue_name: str) -> Dict[str, Any]:
        """Получить информацию об очереди"""
        try:
            length = self.queue_length(queue_name)
            return {
                'name': queue_name,
                'length': length,
                'memory_usage': self.redis.memory_usage(self._key(f"queue:{queue_name}")) if length > 0 else 0
            }
        except Exception as e:
            logger.error(f"❌ Redis queue info error: {e}")
            return {'name': queue_name, 'length': 0, 'memory_usage': 0}
    
    # ==================== СИСТЕМА БЛОКИРОВОК ====================
    
    def acquire_lock(self, lock_name: str, ttl: int = 10) -> bool:
        """Получить распределенную блокировку"""
        try:
            return self.redis.set(
                self._key(f"lock:{lock_name}"),
                "1",
                ex=ttl,
                nx=True
            )
        except Exception as e:
            logger.error(f"❌ Redis lock acquire error: {e}")
            return False
    
    def release_lock(self, lock_name: str) -> bool:
        """Освободить распределенную блокировку"""
        try:
            return self.redis.delete(self._key(f"lock:{lock_name}")) > 0
        except Exception as e:
            logger.error(f"❌ Redis lock release error: {e}")
            return False
    
    def check_lock(self, lock_name: str) -> bool:
        """Проверить наличие блокировки"""
        try:
            return self.redis.exists(self._key(f"lock:{lock_name}")) > 0
        except Exception as e:
            logger.error(f"❌ Redis lock check error: {e}")
            return False
    
    # ==================== СИСТЕМА СЕАНСОВ ====================
    
    def create_session(self, session_id: str, data: Dict[str, Any], ttl: int = 3600) -> bool:
        """Создать сессию"""
        try:
            return self.cache_set(f"session:{session_id}", data, ttl)
        except Exception as e:
            logger.error(f"❌ Redis session create error: {e}")
            return False
    
    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Получить сессию"""
        try:
            return self.cache_get(f"session:{session_id}")
        except Exception as e:
            logger.error(f"❌ Redis session get error: {e}")
            return None
    
    def delete_session(self, session_id: str) -> bool:
        """Удалить сессию"""
        try:
            return self.cache_delete(f"session:{session_id}")
        except Exception as e:
            logger.error(f"❌ Redis session delete error: {e}")
            return False
    
    def update_session_ttl(self, session_id: str, ttl: int = 3600) -> bool:
        """Обновить время жизни сессии"""
        try:
            data = self.get_session(session_id)
            if data:
                return self.create_session(session_id, data, ttl)
            return False
        except Exception as e:
            logger.error(f"❌ Redis session TTL update error: {e}")
            return False
    
    # ==================== СИСТЕМА УВЕДОМЛЕНИЙ ====================
    
    def add_notification(self, user_id: int, notification_type: str, data: Dict[str, Any], ttl: int = 86400) -> bool:
        """Добавить уведомление"""
        try:
            notification = {
                'id': str(datetime.now().timestamp()),
                'type': notification_type,
                'data': data,
                'created_at': datetime.now().isoformat(),
                'read': False
            }
            return self.cache_set(f"notifications:{user_id}:{notification['id']}", notification, ttl)
        except Exception as e:
            logger.error(f"❌ Redis notification add error: {e}")
            return False
    
    def get_user_notifications(self, user_id: int) -> List[Dict[str, Any]]:
        """Получить уведомления пользователя"""
        try:
            pattern = self._key(f"cache:notifications:{user_id}:*")
            keys = self.redis.keys(pattern)
            notifications = []
            
            for key in keys:
                data = self.redis.get(key)
                if data:
                    notifications.append(pickle.loads(data))
            
            return sorted(notifications, key=lambda x: x['created_at'], reverse=True)
        except Exception as e:
            logger.error(f"❌ Redis notifications get error: {e}")
            return []
    
    def mark_notification_read(self, user_id: int, notification_id: str) -> bool:
        """Пометить уведомление как прочитанное"""
        try:
            key = self._key(f"cache:notifications:{user_id}:{notification_id}")
            data = self.redis.get(key)
            if data:
                notification = pickle.loads(data)
                notification['read'] = True
                self.redis.set(key, pickle.dumps(notification))
                return True
            return False
        except Exception as e:
            logger.error(f"❌ Redis notification mark read error: {e}")
            return False
    
    def clear_notifications(self, user_id: int) -> int:
        """Очистить уведомления пользователя"""
        try:
            pattern = self._key(f"cache:notifications:{user_id}:*")
            keys = self.redis.keys(pattern)
            if keys:
                return self.redis.delete(*keys)
            return 0
        except Exception as e:
            logger.error(f"❌ Redis notifications clear error: {e}")
            return 0
    
    # ==================== СИСТЕМА МЕТРИК ====================
    
    def increment_counter(self, counter_name: str, value: int = 1) -> int:
        """Инкрементировать счетчик"""
        try:
            return self.redis.incrby(self._key(f"counter:{counter_name}"), value)
        except Exception as e:
            logger.error(f"❌ Redis counter increment error: {e}")
            return 0
    
    def get_counter(self, counter_name: str) -> int:
        """Получить значение счетчика"""
        try:
            value = self.redis.get(self._key(f"counter:{counter_name}"))
            return int(value) if value else 0
        except Exception as e:
            logger.error(f"❌ Redis counter get error: {e}")
            return 0
    
    def reset_counter(self, counter_name: str) -> bool:
        """Сбросить счетчик"""
        try:
            return self.redis.delete(self._key(f"counter:{counter_name}")) > 0
        except Exception as e:
            logger.error(f"❌ Redis counter reset error: {e}")
            return False
    
    def set_metric(self, metric_name: str, value: Any, ttl: int = 0) -> bool:
        """Установить метрику"""
        try:
            if ttl > 0:
                return self.cache_set(f"metric:{metric_name}", value, ttl)
            else:
                return self.cache_set(f"metric:{metric_name}", value)
        except Exception as e:
            logger.error(f"❌ Redis metric set error: {e}")
            return False
    
    def get_metric(self, metric_name: str, default: Any = None) -> Any:
        """Получить метрику"""
        try:
            return self.cache_get(f"metric:{metric_name}", default)
        except Exception as e:
            logger.error(f"❌ Redis metric get error: {e}")
            return default
    
    # ==================== СЛУЖЕБНЫЕ МЕТОДЫ ====================
    
    def get_info(self) -> Dict[str, Any]:
        """Получить информацию о Redis"""
        try:
            info = self.redis.info()
            return {
                'version': info.get('redis_version', 'unknown'),
                'uptime': info.get('uptime_in_seconds', 0),
                'memory_used': info.get('used_memory_human', '0'),
                'connected_clients': info.get('connected_clients', 0),
                'total_keys': self.redis.dbsize(),
                'hit_rate': info.get('keyspace_hits', 0) / max(1, info.get('keyspace_hits', 0) + info.get('keyspace_misses', 0))
            }
        except Exception as e:
            logger.error(f"❌ Redis info error: {e}")
            return {}
    
    def flush_all(self) -> bool:
        """Очистить всю базу Redis"""
        try:
            self.redis.flushall()
            logger.warning("🚨 Redis база полностью очищена")
            return True
        except Exception as e:
            logger.error(f"❌ Redis flush all error: {e}")
            return False
    
    def flush_pattern(self, pattern: str) -> int:
        """Очистить данные по шаблону"""
        try:
            keys = self.redis.keys(self._key(pattern))
            if keys:
                return self.redis.delete(*keys)
            return 0
        except Exception as e:
            logger.error(f"❌ Redis flush pattern error: {e}")
            return 0
    
    def health_check(self) -> bool:
        """Проверить здоровье Redis"""
        try:
            return self.redis.ping()
        except Exception as e:
            logger.error(f"❌ Redis health check error: {e}")
            return False
    
    def get_memory_info(self) -> Dict[str, Any]:
        """Получить информацию о памяти"""
        try:
            info = self.redis.info('memory')
            return {
                'used_memory': info.get('used_memory_human', '0'),
                'peak_memory': info.get('used_memory_peak_human', '0'),
                'fragmentation_ratio': info.get('mem_fragmentation_ratio', 0),
                'maxmemory': info.get('maxmemory_human', '0')
            }
        except Exception as e:
            logger.error(f"❌ Redis memory info error: {e}")
            return {}
    
    # ==================== АСИНХРОННЫЕ МЕТОДЫ ====================
    
    async def async_cache_get(self, key: str, default: Any = None) -> Any:
        """Асинхронно получить данные из кэша"""
        return await asyncio.get_event_loop().run_in_executor(
            None, self.cache_get, key, default
        )
    
    async def async_cache_set(self, key: str, value: Any, ttl: int = 300) -> bool:
        """Асинхронно установить данные в кэш"""
        return await asyncio.get_event_loop().run_in_executor(
            None, self.cache_set, key, value, ttl
        )
    
    async def async_queue_push(self, queue_name: str, message: Dict[str, Any]) -> bool:
        """Асинхронно добавить сообщение в очередь"""
        return await asyncio.get_event_loop().run_in_executor(
            None, self.queue_push, queue_name, message
        )
    
    async def async_queue_pop(self, queue_name: str, timeout: int = 0) -> Optional[Dict[str, Any]]:
        """Асинхронно извлечь сообщение из очереди"""
        return await asyncio.get_event_loop().run_in_executor(
            None, self.queue_pop, queue_name, timeout
        )

# Глобальный экземпляр Redis
redis_storage = RedisStorage()
