from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
import logging
import time
import hashlib
import uuid
from database import db
from redis_storage import RedisStorage

logger = logging.getLogger(__name__)

# Инициализация Redis
redis_storage = RedisStorage()

# Глобальные переменные для кэширования
user_levels: Dict[int, int] = {}
moderator_stats: Dict[int, Dict[str, int]] = {}
pending_messages: Dict[int, Dict[str, Any]] = {}
user_statistics: Dict[int, Dict[str, Any]] = {}

def init_punishment_system(bot):
    """Инициализация системы наказаний"""
    from punishment_system import PunishmentSystem
    return PunishmentSystem(bot)

# ==================== ОСНОВНЫЕ ФУНКЦИИ С REDIS КЭШИРОВАНИЕМ ====================

def get_user_level(user_id: int) -> int:
    """Получить уровень пользователя с кэшированием в Redis"""
    cache_key = f"user_level:{user_id}"
    
    # Пробуем получить из Redis кэша
    cached_level = redis_storage.cache_get(cache_key)
    if cached_level is not None:
        return cached_level
    
    # Пробуем получить из memory кэша
    if user_id in user_levels:
        redis_storage.cache_set(cache_key, user_levels[user_id], 3600)  # Кэш на 1 час
        return user_levels[user_id]
    
    # Получаем из базы данных
    try:
        level = db.get_user_level(user_id)
        user_levels[user_id] = level
        redis_storage.cache_set(cache_key, level, 3600)
        return level
    except Exception as e:
        logger.error(f"❌ Ошибка получения уровня пользователя {user_id}: {e}")
        return 0

def set_user_level(user_id: int, level: int):
    """Установить уровень пользователя с обновлением кэшей"""
    try:
        db.set_user_level(user_id, level)
        user_levels[user_id] = level
        
        # Обновляем Redis кэш
        cache_key = f"user_level:{user_id}"
        redis_storage.cache_set(cache_key, level, 3600)
        
        # Логируем действие
        db.add_audit_log(
            user_id=0,  # system
            action_type="user_level_change",
            action_details={"user_id": user_id, "new_level": level, "old_level": user_levels.get(user_id, 0)}
        )
        
        logger.info(f"✅ Уровень пользователя {user_id} установлен на {level}")
        
    except Exception as e:
        logger.error(f"❌ Ошибка установки уровня пользователя {user_id}: {e}")

def update_moderator_stats(moderator_id: int, action: str, moderation_time: int = 0):
    """Обновить статистику модератора с кэшированием"""
    try:
        db.update_moderator_stats(moderator_id, action, moderation_time)
        
        # Обновляем memory кэш
        if moderator_id not in moderator_stats:
            moderator_stats[moderator_id] = {'approved': 0, 'rejected': 0, 'reviewed': 0, 'warnings': 0}
        
        if action in moderator_stats[moderator_id]:
            moderator_stats[moderator_id][action] += 1
            moderator_stats[moderator_id]['reviewed'] += 1
        
        # Инвалидируем Redis кэш
        redis_storage.cache_delete(f"mod_stats:{moderator_id}")
        
        # Обновляем аналитику модерации
        db.update_moderation_analytics(action == 'approved', moderation_time)
        
    except Exception as e:
        logger.error(f"❌ Ошибка обновления статистики модератора {moderator_id}: {e}")

def add_message(message_data: Dict[str, Any]) -> int:
    """Добавить сообщение в очередь с кэшированием"""
    try:
        message_id = db.add_message(message_data)
        pending_messages[message_id] = message_data
        
        # Кэшируем в Redis
        redis_storage.cache_set(f"message:{message_id}", message_data, 1800)  # 30 минут
        
        # Логируем создание сообщения
        db.add_audit_log(
            user_id=message_data['user_id'],
            action_type="message_created",
            action_details={"message_id": message_id, "type": message_data['type']}
        )
        
        logger.debug(f"📨 Сообщение {message_id} добавлено в очередь")
        return message_id
        
    except Exception as e:
        logger.error(f"❌ Ошибка добавления сообщения: {e}")
        return -1

def get_message(message_id: int) -> Optional[Dict[str, Any]]:
    """Получить сообщение с кэшированием"""
    try:
        # Пробуем получить из memory кэша
        if message_id in pending_messages:
            return pending_messages[message_id]
        
        # Пробуем получить из Redis кэша
        cached_message = redis_storage.cache_get(f"message:{message_id}")
        if cached_message:
            pending_messages[message_id] = cached_message
            return cached_message
        
        # Получаем из базы данных
        message = db.get_message(message_id)
        if message:
            pending_messages[message_id] = message
            redis_storage.cache_set(f"message:{message_id}", message, 1800)
        
        return message
        
    except Exception as e:
        logger.error(f"❌ Ошибка получения сообщения {message_id}: {e}")
        return None

def update_message_status(message_id: int, approved: bool, moderation_time: int):
    """Обновить статус сообщения и обновить статистику"""
    try:
        message = get_message(message_id)
        if not message:
            return
        
        db.update_message_status(message_id, approved, moderation_time)
        
        # Обновляем статистику пользователя
        db.update_user_statistics(message['user_id'], approved, moderation_time)
        
        # Удаляем из кэшей
        pending_messages.pop(message_id, None)
        redis_storage.cache_delete(f"message:{message_id}")
        
        # Логируем модерацию
        db.add_audit_log(
            user_id=0,  # system
            action_type="message_moderated",
            action_details={
                "message_id": message_id, 
                "approved": approved, 
                "moderation_time": moderation_time,
                "user_id": message['user_id']
            }
        )
        
    except Exception as e:
        logger.error(f"❌ Ошибка обновления статуса сообщения {message_id}: {e}")

def delete_message(message_id: int):
    """Удалить сообщение с очисткой кэшей"""
    try:
        db.delete_message(message_id)
        pending_messages.pop(message_id, None)
        redis_storage.cache_delete(f"message:{message_id}")
        logger.debug(f"🗑️ Сообщение {message_id} удалено")
        
    except Exception as e:
        logger.error(f"❌ Ошибка удаления сообщения {message_id}: {e}")

# ==================== ПЕРСОНАЛЬНАЯ СТАТИСТИКА ПОЛЬЗОВАТЕЛЕЙ ====================

def get_user_statistics(user_id: int) -> Dict[str, Any]:
    """Получить подробную статистику пользователя"""
    cache_key = f"user_stats:{user_id}"
    
    # Пробуем получить из Redis кэша
    cached_stats = redis_storage.cache_get(cache_key)
    if cached_stats:
        return cached_stats
    
    # Пробуем получить из memory кэша
    if user_id in user_statistics:
        redis_storage.cache_set(cache_key, user_statistics[user_id], 300)  # 5 минут
        return user_statistics[user_id]
    
    # Получаем из базы данных
    try:
        stats = db.get_user_statistics(user_id)
        user_statistics[user_id] = stats
        redis_storage.cache_set(cache_key, stats, 300)
        return stats
    except Exception as e:
        logger.error(f"❌ Ошибка получения статистики пользователя {user_id}: {e}")
        return {
            'user_id': user_id,
            'total_messages': 0,
            'approved_messages': 0,
            'rejected_messages': 0,
            'avg_moderation_time': 0,
            'success_rate': 0
        }

def get_detailed_user_stats(user_id: int) -> Dict[str, Any]:
    """Получить расширенную статистику пользователя"""
    base_stats = get_user_statistics(user_id)
    
    # Дополнительные расчеты
    try:
        with db.get_cursor() as cursor:
            # Активность по дням
            cursor.execute("""
                SELECT DATE(created_at) as date, COUNT(*) as count 
                FROM pending_messages 
                WHERE user_id = %s 
                GROUP BY DATE(created_at) 
                ORDER BY date DESC 
                LIMIT 7
            """, (user_id,))
            daily_activity = cursor.fetchall()
            
            # Распределение по типам сообщений
            cursor.execute("""
                SELECT message_type, COUNT(*) as count 
                FROM pending_messages 
                WHERE user_id = %s 
                GROUP BY message_type
            """, (user_id,))
            message_types = cursor.fetchall()
            
            # Время модерации по percentiles
            cursor.execute("""
                SELECT 
                    AVG(moderation_time) as avg_time,
                    MIN(moderation_time) as min_time,
                    MAX(moderation_time) as max_time,
                    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY moderation_time) as median_time
                FROM pending_messages 
                WHERE user_id = %s AND moderation_time > 0
            """, (user_id,))
            time_stats = cursor.fetchone() or {}
            
        return {
            **base_stats,
            'daily_activity': daily_activity,
            'message_types': message_types,
            'time_stats': time_stats,
            'user_rank': calculate_user_rank(user_id),
            'performance_score': calculate_performance_score(base_stats)
        }
        
    except Exception as e:
        logger.error(f"❌ Ошибка получения детальной статистики пользователя {user_id}: {e}")
        return base_stats

def calculate_user_rank(user_id: int) -> int:
    """Рассчитать ранг пользователя среди всех"""
    try:
        with db.get_cursor() as cursor:
            cursor.execute("""
                SELECT user_id, success_rate, total_messages,
                       RANK() OVER (ORDER BY success_rate DESC, total_messages DESC) as user_rank
                FROM user_statistics 
                WHERE total_messages >= 5
            """)
            ranks = {row['user_id']: row['user_rank'] for row in cursor.fetchall()}
            return ranks.get(user_id, 0)
    except Exception as e:
        logger.error(f"❌ Ошибка расчета ранга пользователя {user_id}: {e}")
        return 0

def calculate_performance_score(stats: Dict[str, Any]) -> float:
    """Рассчитать общий score производительности пользователя"""
    try:
        if stats['total_messages'] == 0:
            return 0.0
        
        # Весовые коэффициенты
        success_weight = 0.6
        activity_weight = 0.3
        speed_weight = 0.1
        
        # Нормализованные значения
        success_score = min(stats['success_rate'] / 100, 1.0)
        activity_score = min(stats['total_messages'] / 50, 1.0)  # макс 50 сообщений
        speed_score = 1.0 - min(stats['avg_moderation_time'] / 3600, 1.0)  # макс 1 час
        
        return round((
            success_score * success_weight +
            activity_score * activity_weight +
            speed_score * speed_weight
        ) * 100, 1)
        
    except Exception as e:
        logger.error(f"❌ Ошибка расчета performance score: {e}")
        return 0.0

# ==================== РАСШИРЕННАЯ СИСТЕМА БАНОВ ====================

def add_advanced_ban(user_id: int, ban_type: str, identifier: str, 
                    reason: str, duration: int, moderator_id: int) -> bool:
    """Добавить расширенный бан"""
    try:
        ban_data = {
            'user_id': user_id,
            'ban_type': ban_type,
            'identifier': identifier,
            'reason': reason,
            'duration': duration,
            'moderator_id': moderator_id
        }
        
        ban_id = db.add_advanced_ban(ban_data)
        
        # Обновляем статус пользователя
        if ban_type == 'account':
            with db.get_cursor() as cursor:
                cursor.execute("""
                    UPDATE users 
                    SET is_banned = TRUE, ban_reason = %s, 
                        ban_expires_at = DATE_ADD(NOW(), INTERVAL %s SECOND),
                        ban_count = ban_count + 1
                    WHERE user_id = %s
                """, (reason, duration, user_id))
        
        # Кэшируем бан в Redis для быстрой проверки
        redis_storage.cache_set(
            f"ban:{ban_type}:{identifier}", 
            {'banned': True, 'expires_at': datetime.now() + timedelta(seconds=duration)},
            duration
        )
        
        # Логируем бан
        db.add_audit_log(
            user_id=moderator_id,
            action_type="user_banned",
            action_details={
                "user_id": user_id,
                "ban_type": ban_type,
                "reason": reason,
                "duration": duration,
                "ban_id": ban_id
            }
        )
        
        logger.info(f"🚫 Пользователь {user_id} забанен по {ban_type}: {reason}")
        return True
        
    except Exception as e:
        logger.error(f"❌ Ошибка добавления бана: {e}")
        return False

def check_advanced_ban(identifier: str, ban_type: str) -> bool:
    """Проверить наличие активного бана"""
    # Сначала проверяем Redis кэш
    cache_key = f"ban:{ban_type}:{identifier}"
    cached_ban = redis_storage.cache_get(cache_key)
    if cached_ban and cached_ban['banned']:
        return True
    
    # Затем проверяем базу данных
    try:
        return db.check_advanced_ban(identifier, ban_type)
    except Exception as e:
        logger.error(f"❌ Ошибка проверки бана: {e}")
        return False

def get_user_bans(user_id: int) -> List[Dict[str, Any]]:
    """Получить историю банов пользователя"""
    try:
        with db.get_cursor() as cursor:
            cursor.execute("""
                SELECT * FROM advanced_bans 
                WHERE user_id = %s 
                ORDER BY created_at DESC
            """, (user_id,))
            return cursor.fetchall()
    except Exception as e:
        logger.error(f"❌ Ошибка получения банов пользователя {user_id}: {e}")
        return []

# ==================== АУДИТ И ЛОГИРОВАНИЕ ====================

def add_audit_log(user_id: int, action_type: str, action_details: Dict[str, Any],
                 ip_address: str = None, user_agent: str = None):
    """Добавить запись в лог аудита"""
    try:
        db.add_audit_log(user_id, action_type, action_details, ip_address, user_agent)
        
        # Также пишем в Redis для real-time мониторинга
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'user_id': user_id,
            'action_type': action_type,
            'action_details': action_details
        }
        
        redis_storage.queue_push("audit_logs", log_entry)
        
    except Exception as e:
        logger.error(f"❌ Ошибка добавления лога аудита: {e}")

def get_audit_logs(user_id: int = None, limit: int = 100) -> List[Dict[str, Any]]:
    """Получить логи аудита"""
    try:
        return db.get_audit_logs(user_id, limit)
    except Exception as e:
        logger.error(f"❌ Ошибка получения логов аудита: {e}")
        return []

# ==================== АНАЛИТИКА МОДЕРАЦИИ ====================

def get_moderation_analytics(date: str = None) -> Dict[str, Any]:
    """Получить аналитику модерации"""
    cache_key = f"mod_analytics:{date or 'today'}"
    
    cached_analytics = redis_storage.cache_get(cache_key)
    if cached_analytics:
        return cached_analytics
    
    try:
        analytics = db.get_moderation_analytics(date)
        redis_storage.cache_set(cache_key, analytics, 300)  # 5 минут
        return analytics
    except Exception as e:
        logger.error(f"❌ Ошибка получения аналитики модерации: {e}")
        return {
            'date': date or datetime.now().strftime('%Y-%m-%d'),
            'total_messages': 0,
            'approved_count': 0,
            'rejected_count': 0,
            'avg_moderation_time': 0
        }

def get_moderation_leaderboard(limit: int = 10) -> List[Dict[str, Any]]:
    """Получить таблицу лидеров модераторов"""
    cache_key = f"mod_leaderboard:{limit}"
    
    cached_leaderboard = redis_storage.cache_get(cache_key)
    if cached_leaderboard:
        return cached_leaderboard
    
    try:
        with db.get_cursor() as cursor:
            cursor.execute("""
                SELECT m.moderator_id, u.username, 
                       m.approved, m.rejected, m.reviewed, 
                       m.avg_moderation_time, m.efficiency,
                       RANK() OVER (ORDER BY m.efficiency DESC, m.reviewed DESC) as rank
                FROM moderator_stats m
                LEFT JOIN users u ON m.moderator_id = u.user_id
                WHERE m.reviewed > 0
                ORDER BY m.efficiency DESC, m.reviewed DESC
                LIMIT %s
            """, (limit,))
            
            leaderboard = cursor.fetchall()
            redis_storage.cache_set(cache_key, leaderboard, 600)  # 10 минут
            return leaderboard
            
    except Exception as e:
        logger.error(f"❌ Ошибка получения таблицы лидеров: {e}")
        return []

def get_daily_moderation_stats(days: int = 7) -> List[Dict[str, Any]]:
    """Получить статистику модерации за несколько дней"""
    cache_key = f"daily_mod_stats:{days}"
    
    cached_stats = redis_storage.cache_get(cache_key)
    if cached_stats:
        return cached_stats
    
    try:
        with db.get_cursor() as cursor:
            cursor.execute("""
                SELECT date, total_messages, approved_count, rejected_count,
                       avg_moderation_time,
                       ROUND((approved_count / total_messages * 100), 1) as approval_rate
                FROM moderation_analytics
                WHERE date >= DATE_SUB(CURDATE(), INTERVAL %s DAY)
                ORDER BY date DESC
            """, (days,))
            
            stats = cursor.fetchall()
            redis_storage.cache_set(cache_key, stats, 1800)  # 30 минут
            return stats
            
    except Exception as e:
        logger.error(f"❌ Ошибка получения ежедневной статистики: {e}")
        return []

# ==================== СИСТЕМНЫЕ ФУНКЦИИ ====================

def load_initial_data():
    """Загрузка начальных данных из базы при запуске"""
    global user_levels, pending_messages, user_statistics
    
    try:
        # Загружаем пользователей
        user_levels.update(db.get_all_user_levels())
        logger.info(f"👥 Загружено {len(user_levels)} пользователей")
        
        # Загружаем сообщения в очереди
        pending_messages.update(db.get_all_pending_messages())
        logger.info(f"📨 Загружено {len(pending_messages)} сообщений в очереди")
        
        # Pre-cache активных банов в Redis
        pre_cache_active_bans()
        
        logger.info("✅ Начальные данные загружены в кэш")
        
    except Exception as e:
        logger.error(f"❌ Ошибка загрузки начальных данных: {e}")

def pre_cache_active_bans():
    """Предварительное кэширование активных банов в Redis"""
    try:
        active_bans = db.get_active_bans()
        for ban in active_bans:
            cache_key = f"ban:{ban['ban_type']}:{ban['identifier']}"
            expires_in = (ban['expires_at'] - datetime.now()).total_seconds() if ban['expires_at'] else 3600
            
            redis_storage.cache_set(
                cache_key,
                {'banned': True, 'expires_at': ban['expires_at'].isoformat() if ban['expires_at'] else None},
                max(60, int(expires_in))
            )
        
        logger.info(f"✅ Загружено {len(active_bans)} активных банов в кэш")
        
    except Exception as e:
        logger.error(f"❌ Ошибка предварительного кэширования банов: {e}")

def cleanup_old_data():
    """Очистка старых данных"""
    try:
        db.cleanup_old_data()
        
        # Также очищаем memory кэш от старых сообщений
        curr
