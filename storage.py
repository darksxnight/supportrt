from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import logging
from database import db

logger = logging.getLogger(__name__)

# Глобальные переменные для кэширования
user_levels: Dict[int, int] = {}
moderator_stats: Dict[int, Dict[str, int]] = {}
pending_messages: Dict[int, Dict[str, Any]] = {}
punishments: Dict[int, List[Dict[str, Any]]] = {}
active_punishments: Dict[int, Dict[str, Any]] = {}
user_message_count: Dict[int, Dict[str, int]] = {}  # Для rate limiting

def init_punishment_system(bot):
    """Инициализация системы наказаний"""
    from punishment_system import PunishmentSystem
    return PunishmentSystem(bot)

# ==================== ОСНОВНЫЕ ФУНКЦИИ ДЛЯ РАБОТЫ С ДАННЫМИ ====================

def get_user_level(user_id: int) -> int:
    """Получить уровень пользователя из базы данных"""
    try:
        if user_id in user_levels:
            return user_levels[user_id]
        
        level = db.get_user_level(user_id)
        user_levels[user_id] = level  # Кэшируем
        return level
        
    except Exception as e:
        logger.error(f"❌ Ошибка получения уровня пользователя {user_id}: {e}")
        return 0

def set_user_level(user_id: int, level: int):
    """Установить уровень пользователя в базе данных"""
    try:
        db.set_user_level(user_id, level)
        user_levels[user_id] = level  # Обновляем кэш
        logger.info(f"✅ Уровень пользователя {user_id} установлен на {level}")
        
    except Exception as e:
        logger.error(f"❌ Ошибка установки уровня пользователя {user_id}: {e}")

def update_moderator_stats(moderator_id: int, action: str):
    """Обновить статистику модератора в базе данных"""
    try:
        db.update_moderator_stats(moderator_id, action)
        
        # Обновляем кэш
        if moderator_id not in moderator_stats:
            moderator_stats[moderator_id] = {'approved': 0, 'rejected': 0, 'reviewed': 0, 'warnings': 0}
        
        if action in moderator_stats[moderator_id]:
            moderator_stats[moderator_id][action] += 1
            moderator_stats[moderator_id]['reviewed'] += 1
            
        logger.debug(f"📊 Статистика модератора {moderator_id} обновлена: {action}")
        
    except Exception as e:
        logger.error(f"❌ Ошибка обновления статистики модератора {moderator_id}: {e}")

def add_message(message_data: Dict[str, Any]) -> int:
    """Добавить сообщение в очередь модерации"""
    try:
        message_id = db.add_message(message_data)
        pending_messages[message_id] = message_data  # Кэшируем
        logger.debug(f"📨 Сообщение {message_id} добавлено в очередь")
        return message_id
        
    except Exception as e:
        logger.error(f"❌ Ошибка добавления сообщения: {e}")
        return -1

def get_message(message_id: int) -> Optional[Dict[str, Any]]:
    """Получить сообщение из базы данных"""
    try:
        if message_id in pending_messages:
            return pending_messages[message_id]
        
        message = db.get_message(message_id)
        if message:
            pending_messages[message_id] = message  # Кэшируем
        return message
        
    except Exception as e:
        logger.error(f"❌ Ошибка получения сообщения {message_id}: {e}")
        return None

def delete_message(message_id: int):
    """Удалить сообщение из базы данных"""
    try:
        db.delete_message(message_id)
        pending_messages.pop(message_id, None)  # Удаляем из кэша
        logger.debug(f"🗑️ Сообщение {message_id} удалено")
        
    except Exception as e:
        logger.error(f"❌ Ошибка удаления сообщения {message_id}: {e}")

def get_punishments(user_id: int) -> Dict[str, int]:
    """Получить статистику наказаний пользователя"""
    try:
        punishments_list = db.get_punishments(user_id)
        result = {'mutes': 0, 'warnings': 0, 'bans': 0}
        
        for p in punishments_list:
            punishment_type = p['punishment_type']
            if punishment_type in result:
                result[punishment_type] = p['count']
                
        return result
        
    except Exception as e:
        logger.error(f"❌ Ошибка получения наказаний пользователя {user_id}: {e}")
        return {'mutes': 0, 'warnings': 0, 'bans': 0}

def can_send_message(user_id: int) -> bool:
    """Проверить, может ли пользователь отправить сообщение (rate limiting)"""
    try:
        now = datetime.now()
        hour_ago = now - timedelta(hours=1)
        
        # Получаем количество сообщений за последний час из базы
        # (это упрощенная реализация, лучше использовать Redis для rate limiting)
        from database import db
        with db.get_cursor() as cursor:
            cursor.execute("""
                SELECT COUNT(*) as count FROM pending_messages 
                WHERE user_id = %s AND created_at >= %s
            """, (user_id, hour_ago))
            result = cursor.fetchone()
            message_count = result['count'] if result else 0
        
        can_send = message_count < 5  # Максимум 5 сообщений в час
        
        if not can_send:
            logger.warning(f"🚫 Пользователь {user_id} превысил лимит сообщений: {message_count}/5")
            
        return can_send
        
    except Exception as e:
        logger.error(f"❌ Ошибка проверки лимита сообщений для {user_id}: {e}")
        return True  # В случае ошибки разрешаем отправку

# ==================== ФУНКЦИИ ДЛЯ РАБОТЫ С КЭШЕМ ====================

def load_initial_data():
    """Загрузка начальных данных из базы при запуске"""
    global user_levels, pending_messages
    
    try:
        # Загружаем пользователей
        user_levels.update(db.get_all_user_levels())
        logger.info(f"👥 Загружено {len(user_levels)} пользователей")
        
        # Загружаем сообщения в очереди
        pending_messages.update(db.get_all_pending_messages())
        logger.info(f"📨 Загружено {len(pending_messages)} сообщений в очереди")
        
        # Загружаем статистику модераторов
        # (нужно добавить соответствующий метод в database.py)
        moderators = [uid for uid, level in user_levels.items() if level >= 1]
        for mod_id in moderators:
            stats = db.get_moderator_stats(mod_id)
            moderator_stats[mod_id] = stats
        
        logger.info(f"📊 Загружена статистика для {len(moderator_stats)} модераторов")
        
    except Exception as e:
        logger.error(f"❌ Ошибка загрузки начальных данных: {e}")

def cleanup_old_data():
    """Очистка старых данных"""
    try:
        db.cleanup_old_data()
        
        # Также очищаем кэш от старых сообщений
        current_time = datetime.now()
        to_delete = []
        
        for msg_id, msg_data in pending_messages.items():
            if 'created_at' in msg_data:
                msg_time = datetime.fromisoformat(msg_data['created_at'].replace('Z', '+00:00'))
                if (current_time - msg_time).total_seconds() > 86400:  # 24 часа
                    to_delete.append(msg_id)
        
        for msg_id in to_delete:
            del pending_messages[msg_id]
        
        logger.info(f"🧹 Очистка данных: удалено {len(to_delete)} устаревших сообщений из кэша")
        
    except Exception as e:
        logger.error(f"❌ Ошибка очистки данных: {e}")

def clear_cache():
    """Очистка кэша"""
    global user_levels, moderator_stats, pending_messages, punishments, active_punishments
    user_levels.clear()
    moderator_stats.clear()
    pending_messages.clear()
    punishments.clear()
    active_punishments.clear()
    logger.info("🗑️ Кэш полностью очищен")

def get_cache_stats() -> Dict[str, int]:
    """Получить статистику кэша"""
    return {
        'users': len(user_levels),
        'moderators': len(moderator_stats),
        'pending_messages': len(pending_messages),
        'punishments': len(punishments),
        'active_punishments': len(active_punishments)
    }

# ==================== ДОПОЛНИТЕЛЬНЫЕ ФУНКЦИИ ====================

def get_user_info(user_id: int) -> Optional[Dict[str, Any]]:
    """Получить информацию о пользователе"""
    try:
        from database import db
        with db.get_cursor() as cursor:
            cursor.execute("SELECT * FROM users WHERE user_id = %s", (user_id,))
            return cursor.fetchone()
    except Exception as e:
        logger.error(f"❌ Ошибка получения информации о пользователе {user_id}: {e}")
        return None

def get_moderator_leaderboard(limit: int = 10) -> List[Dict[str, Any]]:
    """Получить таблицу лидеров модераторов"""
    try:
        from database import db
        with db.get_cursor() as cursor:
            cursor.execute("""
                SELECT moderator_id, approved, rejected, reviewed, warnings 
                FROM moderator_stats 
                ORDER BY reviewed DESC 
                LIMIT %s
            """, (limit,))
            return cursor.fetchall()
    except Exception as e:
        logger.error(f"❌ Ошибка получения таблицы лидеров: {e}")
        return []

def get_system_stats() -> Dict[str, Any]:
    """Получить системную статистику"""
    try:
        from database import db
        stats = {}
        
        with db.get_cursor() as cursor:
            # Общее количество пользователей
            cursor.execute("SELECT COUNT(*) as count FROM users")
            stats['total_users'] = cursor.fetchone()['count']
            
            # Количество модераторов
            cursor.execute("SELECT COUNT(*) as count FROM users WHERE level >= 1")
            stats['moderators'] = cursor.fetchone()['count']
            
            # Сообщения в очереди
            cursor.execute("SELECT COUNT(*) as count FROM pending_messages WHERE expires_at > NOW()")
            stats['pending_messages'] = cursor.fetchone()['count']
            
            # Статистика модерации
            cursor.execute("SELECT SUM(approved) as approved, SUM(rejected) as rejected, SUM(reviewed) as reviewed FROM moderator_stats")
            moderation_stats = cursor.fetchone()
            stats.update(moderation_stats)
            
        return stats
        
    except Exception as e:
        logger.error(f"❌ Ошибка получения системной статистики: {e}")
        return {}

# Инициализируем данные при импорте
if db and db.connection and db.connection.is_connected():
    load_initial_data()
