import mysql.connector
from mysql.connector import Error
import logging
from contextlib import contextmanager
from typing import List, Dict, Any, Optional
import datetime

logger = logging.getLogger(__name__)

class MySQLDatabase:
    def __init__(self, host: str, user: str, password: str, database: str):
        self.host = host
        self.user = user
        self.password = password
        self.database = database
        self.connection = None
        
    def connect(self):
        """Установка соединения с MySQL"""
        try:
            self.connection = mysql.connector.connect(
                host=self.host,
                user=self.user,
                password=self.password,
                database=self.database,
                charset='utf8mb4',
                collation='utf8mb4_unicode_ci'
            )
            logger.info("✅ Успешное подключение к MySQL")
            return True
        except Error as e:
            logger.error(f"❌ Ошибка подключения к MySQL: {e}")
            return False
    
    def disconnect(self):
        """Закрытие соединения"""
        if self.connection and self.connection.is_connected():
            self.connection.close()
            logger.info("✅ Соединение с MySQL закрыто")
    
    @contextmanager
    def get_cursor(self):
        """Контекстный менеджер для работы с курсором"""
        cursor = None
        try:
            if not self.connection or not self.connection.is_connected():
                self.connect()
            
            cursor = self.connection.cursor(dictionary=True)
            yield cursor
            self.connection.commit()
        except Error as e:
            logger.error(f"❌ Ошибка MySQL: {e}")
            if self.connection:
                self.connection.rollback()
            raise
        finally:
            if cursor:
                cursor.close()
    
    def initialize_database(self):
        """Инициализация таблиц в базе данных"""
        tables = [
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY,
                username VARCHAR(255) NULL,
                first_name VARCHAR(255) NULL,
                last_name VARCHAR(255) NULL,
                level INT DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                INDEX idx_level (level),
                INDEX idx_username (username)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS moderator_stats (
                moderator_id BIGINT PRIMARY KEY,
                approved INT DEFAULT 0,
                rejected INT DEFAULT 0,
                reviewed INT DEFAULT 0,
                warnings INT DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                FOREIGN KEY (moderator_id) REFERENCES users(user_id) ON DELETE CASCADE
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS pending_messages (
                message_id INT AUTO_INCREMENT PRIMARY KEY,
                user_id BIGINT,
                message_type ENUM('text', 'photo', 'video', 'voice', 'video_note', 'sticker', 'document') NOT NULL,
                content TEXT NULL,
                file_id VARCHAR(255) NULL,
                caption TEXT NULL,
                username VARCHAR(255) NULL,
                user_level INT DEFAULT 0,
                owner_message_id BIGINT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP NULL,
                FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
                INDEX idx_user_id (user_id),
                INDEX idx_created_at (created_at)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS punishments (
                punishment_id INT AUTO_INCREMENT PRIMARY KEY,
                user_id BIGINT,
                punishment_type ENUM('mute', 'warning', 'ban') NOT NULL,
                duration INT DEFAULT 0,
                reason TEXT,
                moderator_id BIGINT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP NULL,
                is_active BOOLEAN DEFAULT TRUE,
                FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
                FOREIGN KEY (moderator_id) REFERENCES users(user_id) ON DELETE SET NULL,
                INDEX idx_user_id (user_id),
                INDEX idx_expires_at (expires_at),
                INDEX idx_is_active (is_active)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS system_settings (
                setting_key VARCHAR(50) PRIMARY KEY,
                setting_value TEXT,
                description VARCHAR(255),
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS message_queue (
                queue_id INT AUTO_INCREMENT PRIMARY KEY,
                user_id BIGINT,
                message_data JSON,
                attempts INT DEFAULT 0,
                status ENUM('pending', 'processing', 'completed', 'failed') DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                processed_at TIMESTAMP NULL,
                FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
                INDEX idx_status (status),
                INDEX idx_created_at (created_at)
            )
            """
        ]
        
        with self.get_cursor() as cursor:
            for table_sql in tables:
                cursor.execute(table_sql)
            logger.info("✅ Таблицы базы данных инициализированы")
    
    # Методы для работы с пользователями
    def get_user_level(self, user_id: int) -> int:
        with self.get_cursor() as cursor:
            cursor.execute("SELECT level FROM users WHERE user_id = %s", (user_id,))
            result = cursor.fetchone()
            return result['level'] if result else 0
    
    def set_user_level(self, user_id: int, level: int):
        with self.get_cursor() as cursor:
            # Проверяем, существует ли пользователь
            cursor.execute("SELECT user_id FROM users WHERE user_id = %s", (user_id,))
            if cursor.fetchone():
                cursor.execute("UPDATE users SET level = %s WHERE user_id = %s", (level, user_id))
            else:
                cursor.execute("INSERT INTO users (user_id, level) VALUES (%s, %s)", (user_id, level))
    
    def get_all_user_levels(self) -> Dict[int, int]:
        with self.get_cursor() as cursor:
            cursor.execute("SELECT user_id, level FROM users")
            return {row['user_id']: row['level'] for row in cursor.fetchall()}
    
    # Методы для статистики модераторов
    def get_moderator_stats(self, moderator_id: int) -> Dict[str, int]:
        with self.get_cursor() as cursor:
            cursor.execute(
                "SELECT approved, rejected, reviewed, warnings FROM moderator_stats WHERE moderator_id = %s",
                (moderator_id,)
            )
            result = cursor.fetchone()
            return result or {'approved': 0, 'rejected': 0, 'reviewed': 0, 'warnings': 0}
    
    def update_moderator_stats(self, moderator_id: int, action: str):
        with self.get_cursor() as cursor:
            # Убедимся, что модератор существует в таблице
            cursor.execute("SELECT moderator_id FROM moderator_stats WHERE moderator_id = %s", (moderator_id,))
            if not cursor.fetchone():
                cursor.execute(
                    "INSERT INTO moderator_stats (moderator_id, approved, rejected, reviewed, warnings) VALUES (%s, 0, 0, 0, 0)",
                    (moderator_id,)
                )
            
            # Обновляем статистику
            if action in ['approved', 'rejected', 'reviewed', 'warnings']:
                cursor.execute(
                    f"UPDATE moderator_stats SET {action} = {action} + 1, reviewed = reviewed + 1 WHERE moderator_id = %s",
                    (moderator_id,)
                )
    
    # Методы для pending messages
    def add_message(self, message_data: Dict[str, Any]) -> int:
        with self.get_cursor() as cursor:
            cursor.execute("""
                INSERT INTO pending_messages 
                (user_id, message_type, content, file_id, caption, username, user_level, expires_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, DATE_ADD(NOW(), INTERVAL 24 HOUR))
            """, (
                message_data['user_id'],
                message_data['type'],
                message_data.get('content'),
                message_data.get('file_id'),
                message_data.get('caption'),
                message_data.get('username'),
                message_data.get('level', 0)
            ))
            return cursor.lastrowid
    
    def get_message(self, message_id: int) -> Optional[Dict[str, Any]]:
        with self.get_cursor() as cursor:
            cursor.execute("SELECT * FROM pending_messages WHERE message_id = %s", (message_id,))
            return cursor.fetchone()
    
    def delete_message(self, message_id: int):
        with self.get_cursor() as cursor:
            cursor.execute("DELETE FROM pending_messages WHERE message_id = %s", (message_id,))
    
    def get_all_pending_messages(self) -> Dict[int, Dict[str, Any]]:
        with self.get_cursor() as cursor:
            cursor.execute("SELECT * FROM pending_messages WHERE expires_at > NOW()")
            return {row['message_id']: row for row in cursor.fetchall()}
    
    # Методы для наказаний
    def add_punishment(self, user_id: int, punishment_data: Dict[str, Any]):
        with self.get_cursor() as cursor:
            cursor.execute("""
                INSERT INTO punishments 
                (user_id, punishment_type, duration, reason, moderator_id, expires_at)
                VALUES (%s, %s, %s, %s, %s, DATE_ADD(NOW(), INTERVAL %s SECOND))
            """, (
                user_id,
                punishment_data['type'],
                punishment_data['duration'],
                punishment_data['reason'],
                punishment_data['moderator_id'],
                punishment_data['duration']
            ))
    
    def get_punishments(self, user_id: int) -> List[Dict[str, Any]]:
        with self.get_cursor() as cursor:
            cursor.execute("""
                SELECT punishment_type, COUNT(*) as count 
                FROM punishments 
                WHERE user_id = %s 
                GROUP BY punishment_type
            """, (user_id,))
            return cursor.fetchall()
    
    # Методы для системных настроек
    def get_system_settings(self) -> Dict[str, Any]:
        with self.get_cursor() as cursor:
            cursor.execute("SELECT setting_key, setting_value FROM system_settings")
            return {row['setting_key']: row['setting_value'] for row in cursor.fetchall()}
    
    def update_system_setting(self, key: str, value: str):
        with self.get_cursor() as cursor:
            cursor.execute("""
                INSERT INTO system_settings (setting_key, setting_value) 
                VALUES (%s, %s)
                ON DUPLICATE KEY UPDATE setting_value = %s
            """, (key, value, value))
    
    # Очистка старых данных
    def cleanup_old_data(self):
        with self.get_cursor() as cursor:
            # Удаляем просроченные сообщения
            cursor.execute("DELETE FROM pending_messages WHERE expires_at <= NOW()")
            # Деактивируем просроченные наказания
            cursor.execute("UPDATE punishments SET is_active = FALSE WHERE expires_at <= NOW() AND is_active = TRUE")
            logger.info("✅ Очистка старых данных выполнена")

# Глобальный экземпляр базы данных
db = None

def init_database(host: str, user: str, password: str, database: str):
    """Инициализация базы данных"""
    global db
    db = MySQLDatabase(host, user, password, database)
    if db.connect():
        db.initialize_database()
        return True
    return False
