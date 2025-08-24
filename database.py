import mysql.connector
from mysql.connector import Error
import logging
from contextlib import contextmanager
from typing import List, Dict, Any, Optional
import datetime
import json

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
                collation='utf8mb4_unicode_ci',
                autocommit=True
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
            # Таблица пользователей
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY,
                username VARCHAR(255) NULL,
                first_name VARCHAR(255) NULL,
                last_name VARCHAR(255) NULL,
                level INT DEFAULT 0,
                reputation INT DEFAULT 0,
                is_banned BOOLEAN DEFAULT FALSE,
                ban_reason TEXT NULL,
                ban_expires_at TIMESTAMP NULL,
                ban_count INT DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                INDEX idx_level (level),
                INDEX idx_reputation (reputation),
                INDEX idx_is_banned (is_banned)
            )
            """,
            
            # Статистика пользователей
            """
            CREATE TABLE IF NOT EXISTS user_statistics (
                user_id BIGINT PRIMARY KEY,
                total_messages INT DEFAULT 0,
                approved_messages INT DEFAULT 0,
                rejected_messages INT DEFAULT 0,
                total_moderation_time BIGINT DEFAULT 0,
                avg_moderation_time FLOAT DEFAULT 0,
                success_rate FLOAT DEFAULT 0,
                last_activity TIMESTAMP NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
            )
            """,
            
            # Статистика модераторов
            """
            CREATE TABLE IF NOT EXISTS moderator_stats (
                moderator_id BIGINT PRIMARY KEY,
                approved INT DEFAULT 0,
                rejected INT DEFAULT 0,
                reviewed INT DEFAULT 0,
                warnings INT DEFAULT 0,
                avg_moderation_time FLOAT DEFAULT 0,
                efficiency FLOAT DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                FOREIGN KEY (moderator_id) REFERENCES users(user_id) ON DELETE CASCADE
            )
            """,
            
            # Сообщения в очереди
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
                moderated_at TIMESTAMP NULL,
                moderation_time INT DEFAULT 0,
                expires_at TIMESTAMP NULL,
                status ENUM('pending', 'approved', 'rejected') DEFAULT 'pending',
                FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
                INDEX idx_user_id (user_id),
                INDEX idx_status (status),
                INDEX idx_created_at (created_at)
            )
            """,
            
            # Наказания
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
            
            # Системные настройки
            """
            CREATE TABLE IF NOT EXISTS system_settings (
                setting_key VARCHAR(50) PRIMARY KEY,
                setting_value TEXT,
                description VARCHAR(255),
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            )
            """,
            
            # Логи аудита
            """
            CREATE TABLE IF NOT EXISTS audit_logs (
                log_id INT AUTO_INCREMENT PRIMARY KEY,
                user_id BIGINT NULL,
                action_type VARCHAR(100) NOT NULL,
                action_details JSON,
                ip_address VARCHAR(45) NULL,
                user_agent TEXT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_action_type (action_type),
                INDEX idx_created_at (created_at),
                INDEX idx_user_id (user_id)
            )
            """,
            
            # Аналитика модерации
            """
            CREATE TABLE IF NOT EXISTS moderation_analytics (
                analytics_id INT AUTO_INCREMENT PRIMARY KEY,
                date DATE NOT NULL,
                total_messages INT DEFAULT 0,
                approved_count INT DEFAULT 0,
                rejected_count INT DEFAULT 0,
                avg_moderation_time FLOAT DEFAULT 0,
                moderator_performance JSON,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE KEY unique_date (date)
            )
            """,
            
            # Расширенные баны
            """
            CREATE TABLE IF NOT EXISTS advanced_bans (
                ban_id INT AUTO_INCREMENT PRIMARY KEY,
                user_id BIGINT,
                ban_type ENUM('account', 'ip', 'device') NOT NULL,
                identifier VARCHAR(255) NOT NULL,  # user_id, IP, или device_hash
                reason TEXT NOT NULL,
                duration INT DEFAULT 0,
                moderator_id BIGINT,
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP NULL,
                FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
                INDEX idx_identifier (identifier),
                INDEX idx_is_active (is_active),
                INDEX idx_expires_at (expires_at)
            )
            """
        ]
        
        with self.get_cursor() as cursor:
            for table_sql in tables:
                try:
                    cursor.execute(table_sql)
                except Error as e:
                    logger.error(f"Ошибка создания таблицы: {e}")
            
            logger.info("✅ Таблицы базы данных инициализированы")
    
    # ==================== МЕТОДЫ ДЛЯ СТАТИСТИКИ ПОЛЬЗОВАТЕЛЕЙ ====================
    
    def get_user_statistics(self, user_id: int) -> Dict[str, Any]:
        """Получить статистику пользователя"""
        with self.get_cursor() as cursor:
            cursor.execute("SELECT * FROM user_statistics WHERE user_id = %s", (user_id,))
            result = cursor.fetchone()
            return result or {
                'user_id': user_id,
                'total_messages': 0,
                'approved_messages': 0,
                'rejected_messages': 0,
                'avg_moderation_time': 0,
                'success_rate': 0
            }
    
    def update_user_statistics(self, user_id: int, approved: bool, moderation_time: int):
        """Обновить статистику пользователя"""
        with self.get_cursor() as cursor:
            # Получаем текущую статистику
            cursor.execute("SELECT * FROM user_statistics WHERE user_id = %s", (user_id,))
            stats = cursor.fetchone()
            
            if stats:
                total = stats['total_messages'] + 1
                approved_count = stats['approved_messages'] + (1 if approved else 0)
                rejected_count = stats['rejected_messages'] + (0 if approved else 1)
                total_time = stats['total_moderation_time'] + moderation_time
                avg_time = total_time / total if total > 0 else 0
                success_rate = (approved_count / total * 100) if total > 0 else 0
                
                cursor.execute("""
                    UPDATE user_statistics 
                    SET total_messages = %s, approved_messages = %s, rejected_messages = %s,
                        total_moderation_time = %s, avg_moderation_time = %s, success_rate = %s,
                        last_activity = NOW(), updated_at = NOW()
                    WHERE user_id = %s
                """, (total, approved_count, rejected_count, total_time, avg_time, success_rate, user_id))
            else:
                success_rate = 100 if approved else 0
                cursor.execute("""
                    INSERT INTO user_statistics 
                    (user_id, total_messages, approved_messages, rejected_messages, 
                     total_moderation_time, avg_moderation_time, success_rate, last_activity)
                    VALUES (%s, 1, %s, %s, %s, %s, %s, NOW())
                """, (user_id, 1 if approved else 0, 0 if approved else 1, 
                      moderation_time, moderation_time, success_rate))
    
    # ==================== МЕТОДЫ ДЛЯ АНАЛИТИКИ МОДЕРАЦИИ ====================
    
    def get_moderation_analytics(self, date: str = None) -> Dict[str, Any]:
        """Получить аналитику модерации за дату"""
        if date is None:
            date = datetime.datetime.now().strftime('%Y-%m-%d')
        
        with self.get_cursor() as cursor:
            cursor.execute("SELECT * FROM moderation_analytics WHERE date = %s", (date,))
            return cursor.fetchone()
    
    def update_moderation_analytics(self, approved: bool, moderation_time: int):
        """Обновить ежедневную аналитику модерации"""
        date = datetime.datetime.now().strftime('%Y-%m-%d')
        
        with self.get_cursor() as cursor:
            cursor.execute("SELECT * FROM moderation_analytics WHERE date = %s", (date,))
            analytics = cursor.fetchone()
            
            if analytics:
                total = analytics['total_messages'] + 1
                approved_count = analytics['approved_count'] + (1 if approved else 0)
                rejected_count = analytics['rejected_count'] + (0 if approved else 1)
                total_time = analytics['avg_moderation_time'] * analytics['total_messages'] + moderation_time
                avg_time = total_time / total
                
                cursor.execute("""
                    UPDATE moderation_analytics 
                    SET total_messages = %s, approved_count = %s, rejected_count = %s,
                        avg_moderation_time = %s, updated_at = NOW()
                    WHERE date = %s
                """, (total, approved_count, rejected_count, avg_time, date))
            else:
                cursor.execute("""
                    INSERT INTO moderation_analytics 
                    (date, total_messages, approved_count, rejected_count, avg_moderation_time)
                    VALUES (%s, 1, %s, %s, %s)
                """, (date, 1 if approved else 0, 0 if approved else 1, moderation_time))
    
    # ==================== МЕТОДЫ ДЛЯ РАСШИРЕННЫХ БАНОВ ====================
    
    def add_advanced_ban(self, ban_data: Dict[str, Any]) -> int:
        """Добавить расширенный бан"""
        with self.get_cursor() as cursor:
            cursor.execute("""
                INSERT INTO advanced_bans 
                (user_id, ban_type, identifier, reason, duration, moderator_id, expires_at)
                VALUES (%s, %s, %s, %s, %s, %s, DATE_ADD(NOW(), INTERVAL %s SECOND))
            """, (
                ban_data['user_id'],
                ban_data['ban_type'],
                ban_data['identifier'],
                ban_data['reason'],
                ban_data['duration'],
                ban_data['moderator_id'],
                ban_data['duration']
            ))
            return cursor.lastrowid
    
    def check_advanced_ban(self, identifier: str, ban_type: str) -> bool:
        """Проверить наличие активного бана"""
        with self.get_cursor() as cursor:
            cursor.execute("""
                SELECT COUNT(*) as count FROM advanced_bans 
                WHERE identifier = %s AND ban_type = %s AND is_active = TRUE 
                AND (expires_at IS NULL OR expires_at > NOW())
            """, (identifier, ban_type))
            result = cursor.fetchone()
            return result['count'] > 0 if result else False
    
    def get_active_bans(self) -> List[Dict[str, Any]]:
        """Получить список активных банов"""
        with self.get_cursor() as cursor:
            cursor.execute("""
                SELECT * FROM advanced_bans 
                WHERE is_active = TRUE AND (expires_at IS NULL OR expires_at > NOW())
            """)
            return cursor.fetchall()
    
    # ==================== МЕТОДЫ ДЛЯ АУДИТА И ЛОГИРОВАНИЯ ====================
    
    def add_audit_log(self, user_id: int, action_type: str, action_details: Dict[str, Any], 
                     ip_address: str = None, user_agent: str = None):
        """Добавить запись в лог аудита"""
        with self.get_cursor() as cursor:
            cursor.execute("""
                INSERT INTO audit_logs 
                (user_id, action_type, action_details, ip_address, user_agent)
                VALUES (%s, %s, %s, %s, %s)
            """, (user_id, action_type, json.dumps(action_details), ip_address, user_agent))
    
    def get_audit_logs(self, user_id: int = None, limit: int = 100) -> List[Dict[str, Any]]:
        """Получить логи аудита"""
        with self.get_cursor() as cursor:
            if user_id:
                cursor.execute("""
                    SELECT * FROM audit_logs 
                    WHERE user_id = %s 
                    ORDER BY created_at DESC 
                    LIMIT %s
                """, (user_id, limit))
            else:
                cursor.execute("""
                    SELECT * FROM audit_logs 
                    ORDER BY created_at DESC 
                    LIMIT %s
                """, (limit,))
            return cursor.fetchall()
    
    # ==================== БАЗОВЫЕ МЕТОДЫ (как ранее) ====================
    
    def get_user_level(self, user_id: int) -> int:
        with self.get_cursor() as cursor:
            cursor.execute("SELECT level FROM users WHERE user_id = %s", (user_id,))
            result = cursor.fetchone()
            return result['level'] if result else 0
    
    def set_user_level(self, user_id: int, level: int):
        with self.get_cursor() as cursor:
            cursor.execute("SELECT user_id FROM users WHERE user_id = %s", (user_id,))
            if cursor.fetchone():
                cursor.execute("UPDATE users SET level = %s WHERE user_id = %s", (level, user_id))
            else:
                cursor.execute("INSERT INTO users (user_id, level) VALUES (%s, %s)", (user_id, level))
    
    def get_all_user_levels(self) -> Dict[int, int]:
        with self.get_cursor() as cursor:
            cursor.execute("SELECT user_id, level FROM users")
            return {row['user_id']: row['level'] for row in cursor.fetchall()}
    
    def get_moderator_stats(self, moderator_id: int) -> Dict[str, int]:
        with self.get_cursor() as cursor:
            cursor.execute(
                "SELECT approved, rejected, reviewed, warnings, avg_moderation_time, efficiency FROM moderator_stats WHERE moderator_id = %s",
                (moderator_id,)
            )
            result = cursor.fetchone()
            return result or {'approved': 0, 'rejected': 0, 'reviewed': 0, 'warnings': 0, 'avg_moderation_time': 0, 'efficiency': 0}
    
    def update_moderator_stats(self, moderator_id: int, action: str, moderation_time: int = 0):
        with self.get_cursor() as cursor:
            cursor.execute("SELECT * FROM moderator_stats WHERE moderator_id = %s", (moderator_id,))
            stats = cursor.fetchone()
            
            if not stats:
                cursor.execute(
                    "INSERT INTO moderator_stats (moderator_id, approved, rejected, reviewed, warnings) VALUES (%s, 0, 0, 0, 0)",
                    (moderator_id,)
                )
                stats = {'approved': 0, 'rejected': 0, 'reviewed': 0, 'warnings': 0, 'avg_moderation_time': 0}
            
            reviewed = stats['reviewed'] + 1
            approved = stats['approved'] + (1 if action == 'approved' else 0)
            rejected = stats['rejected'] + (1 if action == 'rejected' else 0)
            warnings = stats['warnings'] + (1 if action == 'warning' else 0)
            
            # Обновляем среднее время модерации
            total_time = stats['avg_moderation_time'] * stats['reviewed'] + moderation_time
            avg_time = total_time / reviewed if reviewed > 0 else 0
            
            # Эффективность (процент одобренных от всех рассмотренных)
            efficiency = (approved / reviewed * 100) if reviewed > 0 else 0
            
            cursor.execute("""
                UPDATE moderator_stats 
                SET approved = %s, rejected = %s, reviewed = %s, warnings = %s,
                    avg_moderation_time = %s, efficiency = %s, updated_at = NOW()
                WHERE moderator_id = %s
            """, (approved, rejected, reviewed, warnings, avg_time, efficiency, moderator_id))
    
    def add_message(self, message_data: Dict[s
