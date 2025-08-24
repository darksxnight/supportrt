import datetime
from typing import Dict, List, Any, Optional
from redis_storage import redis_storage

# Теперь используем Redis вместо memory storage
user_levels = {}
moderator_stats = {}
pending_messages = {}
punishments = {}
active_punishments = {}

def init_punishment_system(bot):
    """Инициализация системы наказаний"""
    from punishment_system import PunishmentSystem
    return PunishmentSystem(bot)

# Обертки для совместимости
def get_user_level(user_id: int) -> int:
    return redis_storage.get_user_level(user_id)

def set_user_level(user_id: int, level: int):
    redis_storage.set_user_level(user_id, level)
    user_levels[user_id] = level  # Для обратной совместимости

def update_moderator_stats(moderator_id: int, action: str):
    redis_storage.update_moderator_stats(moderator_id, action)
    if moderator_id not in moderator_stats:
        moderator_stats[moderator_id] = {'approved': 0, 'rejected': 0, 'reviewed': 0, 'warnings': 0}
    moderator_stats[moderator_id][action] += 1
    moderator_stats[moderator_id]['reviewed'] += 1

def add_message(message_data: Dict[str, Any]) -> int:
    message_id = redis_storage.add_message(message_data)
    pending_messages[message_id] = message_data  # Для обратной совместимости
    return message_id

def get_message(message_id: int) -> Optional[Dict[str, Any]]:
    msg = redis_storage.get_message(message_id)
    if msg:
        pending_messages[message_id] = msg
    return msg

def delete_message(message_id: int):
    redis_storage.delete_message(message_id)
    pending_messages.pop(message_id, None)

def get_punishments(user_id: int) -> Dict[str, int]:
    punishments_list = redis_storage.get_punishments(user_id)
    result = {'mutes': 0, 'warnings': 0, 'bans': 0}
    for p in punishments_list:
        result[p['type'] + 's'] += 1
    return result

def can_send_message(user_id: int) -> bool:
    return redis_storage.check_rate_limit(user_id, 5, 3600)  # 5 сообщений в час

def load_initial_data():
    """Загрузка данных из Redis при старте"""
    global user_levels, moderator_stats
    user_levels = redis_storage.get_all_user_levels()
    
    # Загружаем статистику модераторов
    mod_keys = redis_storage.redis.keys(redis_storage._key("mod:*:stats"))
    for key in mod_keys:
        mod_id = int(key.split(":")[1])
        moderator_stats[mod_id] = redis_storage.get_moderator_stats(mod_id)
    
    # Загружаем pending messages
    pending_messages.update(redis_storage.get_all_pending_messages())

# Загружаем данные при импорте
load_initial_data()
