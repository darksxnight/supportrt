import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # ==================== ОСНОВНЫЕ НАСТРОЙКИ БОТА ====================
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    MODERATOR_ID = int(os.getenv("MODERATOR_ID", 0))
    CHANNEL_ID = os.getenv("CHANNEL_ID")
    OWNER_ID = int(os.getenv("OWNER_ID", 0))
    
    # ==================== НАСТРОЙКИ MYSQL DATABASE ====================
    MYSQL_HOST = os.getenv("MYSQL_HOST", "localhost")
    MYSQL_USER = os.getenv("MYSQL_USER", "root")
    MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "")
    MYSQL_DATABASE = os.getenv("MYSQL_DATABASE", "anon_bot")
    MYSQL_PORT = int(os.getenv("MYSQL_PORT", 3306))
    MYSQL_POOL_SIZE = int(os.getenv("MYSQL_POOL_SIZE", 10))
    MYSQL_MAX_OVERFLOW = int(os.getenv("MYSQL_MAX_OVERFLOW", 20))
    MYSQL_POOL_RECYCLE = int(os.getenv("MYSQL_POOL_RECYCLE", 3600))
    
    # ==================== КАНАЛЫ ДЛЯ ЛОГИРОВАНИЯ ====================
    LOG_MODERATION_CHANNEL = os.getenv("LOG_MODERATION_CHANNEL", "@moderation_logs")
    LOG_PUNISHMENT_CHANNEL = os.getenv("LOG_PUNISHMENT_CHANNEL", "@punishment_logs") 
    OWNER_CHANNEL = os.getenv("OWNER_CHANNEL", "@owner_channel")
    MODERATION_CHAT = os.getenv("MODERATION_CHAT", "@moderation_chat")
    ERROR_CHANNEL = os.getenv("ERROR_CHANNEL", "@error_logs")
    ADMIN_NOTIFICATIONS_CHANNEL = os.getenv("ADMIN_NOTIFICATIONS_CHANNEL", "@admin_notifications")
    
    # ==================== НАСТРОЙКИ БЕЗОПАСНОСТИ ====================
    MAX_MESSAGES_PER_HOUR = int(os.getenv("MAX_MESSAGES_PER_HOUR", 5))
    MAX_MESSAGE_LENGTH = int(os.getenv("MAX_MESSAGE_LENGTH", 1000))
    MAX_PHOTO_SIZE = int(os.getenv("MAX_PHOTO_SIZE", 10 * 1024 * 1024))  # 10MB
    MAX_VIDEO_SIZE = int(os.getenv("MAX_VIDEO_SIZE", 20 * 1024 * 1024))  # 20MB
    
    # ==================== НАСТРОЙКИ МОДЕРАЦИИ ====================
    AUTO_MODERATION = os.getenv("AUTO_MODERATION", "False").lower() == "true"
    MODERATION_TIMEOUT = int(os.getenv("MODERATION_TIMEOUT", 300))  # 5 минут
    MODERATION_QUEUE_LIMIT = int(os.getenv("MODERATION_QUEUE_LIMIT", 100))
    MESSAGE_EXPIRY_HOURS = int(os.getenv("MESSAGE_EXPIRY_HOURS", 24))
    
    # ==================== НАСТРОЙКИ НАКАЗАНИЙ ====================
    DEFAULT_MUTE_DURATION = int(os.getenv("DEFAULT_MUTE_DURATION", 3600))  # 1 час
    DEFAULT_BAN_DURATION = int(os.getenv("DEFAULT_BAN_DURATION", 86400))   # 24 часа
    MAX_WARNINGS_BEFORE_BAN = int(os.getenv("MAX_WARNINGS_BEFORE_BAN", 3))
    PUNISHMENT_ESCALATION_FACTOR = float(os.getenv("PUNISHMENT_ESCALATION_FACTOR", 2.0))
    
    # ==================== НАСТРОЙКИ API И WEBHOOKS ====================
    API_HOST = os.getenv("API_HOST", "0.0.0.0")
    API_PORT = int(os.getenv("API_PORT", 8000))
    API_SECRET_KEY = os.getenv("API_SECRET_KEY", "your-secret-key-here")
    WEBHOOK_URL = os.getenv("WEBHOOK_URL", "")
    WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "webhook-secret-here")
    WEBHOOK_PATH = os.getenv("WEBHOOK_PATH", "/webhook")
    
    # ==================== НАСТРОЙКИ КЭШИРОВАНИЯ ====================
    CACHE_ENABLED = os.getenv("CACHE_ENABLED", "True").lower() == "true"
    CACHE_TTL = int(os.getenv("CACHE_TTL", 300))  # 5 минут
    USER_CACHE_SIZE = int(os.getenv("USER_CACHE_SIZE", 1000))
    MESSAGE_CACHE_SIZE = int(os.getenv("MESSAGE_CACHE_SIZE", 500))
    
    # ==================== НАСТРОЙКИ УВЕДОМЛЕНИЙ ====================
    NOTIFICATIONS_ENABLED = os.getenv("NOTIFICATIONS_ENABLED", "True").lower() == "true"
    NOTIFY_ON_NEW_USER = os.getenv("NOTIFY_ON_NEW_USER", "True").lower() == "true"
    NOTIFY_ON_MODERATION = os.getenv("NOTIFY_ON_MODERATION", "True").lower() == "true"
    NOTIFY_ON_ERROR = os.getenv("NOTIFY_ON_ERROR", "True").lower() == "true"
    
    # ==================== НАСТРОЙКИ ОЧЕРЕДЕЙ ====================
    QUEUE_PROCESSING_ENABLED = os.getenv("QUEUE_PROCESSING_ENABLED", "True").lower() == "true"
    QUEUE_PROCESSING_INTERVAL = int(os.getenv("QUEUE_PROCESSING_INTERVAL", 60))  # 60 секунд
    MAX_QUEUE_RETRIES = int(os.getenv("MAX_QUEUE_RETRIES", 3))
    
    # ==================== НАСТРОЙКИ СИСТЕМЫ ====================
    DEBUG = os.getenv("DEBUG", "False").lower() == "true"
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    TIMEZONE = os.getenv("TIMEZONE", "Europe/Moscow")
    LANGUAGE = os.getenv("LANGUAGE", "ru")
    
    # ==================== НАСТРОЙКИ РЕЗЕРВНОГО КОПИРОВАНИЯ ====================
    BACKUP_ENABLED = os.getenv("BACKUP_ENABLED", "True").lower() == "true"
    BACKUP_INTERVAL = int(os.getenv("BACKUP_INTERVAL", 86400))  # 24 часа
    BACKUP_RETENTION_DAYS = int(os.getenv("BACKUP_RETENTION_DAYS", 7))
    BACKUP_PATH = os.getenv("BACKUP_PATH", "./backups")
    
    # ==================== НАСТРОЙКИ ЧЕРНОГО СПИСКА ====================
    BLACKLIST_ENABLED = os.getenv("BLACKLIST_ENABLED", "True").lower() == "true"
    BLACKLIST_WORDS = os.getenv("BLACKLIST_WORDS", "спам,оскорбление,реклама,мошенничество").split(',')
    BLACKLIST_LINKS = os.getenv("BLACKLIST_LINKS", "").split(',')
    
    # ==================== НАСТРОЙКИ СТАТИСТИКИ ====================
    STATS_ENABLED = os.getenv("STATS_ENABLED", "True").lower() == "true"
    STATS_UPDATE_INTERVAL = int(os.getenv("STATS_UPDATE_INTERVAL", 300))  # 5 минут
    STATS_RETENTION_DAYS = int(os.getenv("STATS_RETENTION_DAYS", 30))
    
    # ==================== URL ДЛЯ ПОДКЛЮЧЕНИЯ К MYSQL ====================
    @classmethod
    def get_mysql_url(cls) -> str:
        """Получить URL для подключения к MySQL"""
        return f"mysql+mysqlconnector://{cls.MYSQL_USER}:{cls.MYSQL_PASSWORD}@{cls.MYSQL_HOST}:{cls.MYSQL_PORT}/{cls.MYSQL_DATABASE}"
    
    @classmethod
    def get_mysql_connection_dict(cls) -> dict:
        """Получить параметры подключения в виде словаря"""
        return {
            'host': cls.MYSQL_HOST,
            'user': cls.MYSQL_USER,
            'password': cls.MYSQL_PASSWORD,
            'database': cls.MYSQL_DATABASE,
            'port': cls.MYSQL_PORT,
            'charset': 'utf8mb4',
            'collation': 'utf8mb4_unicode_ci',
            'autocommit': True
        }
    
    @classmethod
    def validate(cls):
        """Проверка обязательных настроек"""
        errors = []
        
        # Проверка основных настроек
        if not cls.BOT_TOKEN:
            errors.append("BOT_TOKEN не установлен")
        if not cls.MODERATOR_ID:
            errors.append("MODERATOR_ID не установлен")
        if not cls.CHANNEL_ID:
            errors.append("CHANNEL_ID не установлен")
        if not cls.OWNER_ID:
            errors.append("OWNER_ID не установлен")
        
        # Проверка настроек MySQL
        if not cls.MYSQL_HOST:
            errors.append("MYSQL_HOST не установлен")
        if not cls.MYSQL_USER:
            errors.append("MYSQL_USER не установлен")
        if not cls.MYSQL_DATABASE:
            errors.append("MYSQL_DATABASE не установлен")
        
        # Проверка числовых значений
        if cls.MAX_MESSAGES_PER_HOUR <= 0:
            errors.append("MAX_MESSAGES_PER_HOUR должен быть больше 0")
        if cls.MAX_MESSAGE_LENGTH <= 0:
            errors.append("MAX_MESSAGE_LENGTH должен быть больше 0")
        if cls.MYSQL_PORT <= 0:
            errors.append("MYSQL_PORT должен быть положительным числом")
        if cls.DEFAULT_MUTE_DURATION < 0:
            errors.append("DEFAULT_MUTE_DURATION не может быть отрицательным")
        if cls.DEFAULT_BAN_DURATION < 0:
            errors.append("DEFAULT_BAN_DURATION не может быть отрицательным")
        
        if errors:
            raise ValueError(" | ".join(errors))
    
    @classmethod
    def get_all_settings(cls) -> dict:
        """Получить все настройки в виде словаря (без паролей)"""
        settings = {}
        for attr in dir(cls):
            if not attr.startswith('_') and not callable(getattr(cls, attr)):
                value = getattr(cls, attr)
                # Скрываем чувствительные данные
                if any(sensitive in attr.lower() for sensitive in ['password', 'token', 'secret']):
                    value = '***HIDDEN***' if value else None
                settings[attr] = value
        return settings
    
    @classmethod
    def get_database_info(cls) -> dict:
        """Получить информацию о базе данных"""
        return {
            'host': cls.MYSQL_HOST,
            'database': cls.MYSQL_DATABASE,
            'port': cls.MYSQL_PORT,
            'user': cls.MYSQL_USER,
            'pool_size': cls.MYSQL_POOL_SIZE,
            'max_overflow': cls.MYSQL_MAX_OVERFLOW
        }

# Создаем экземпляр конфигурации
config = Config()

# Проверяем настройки при импорте
try:
    Config.validate()
except ValueError as e:
    print(f"❌ Ошибка конфигурации: {e}")
    print("⚠️  Проверьте файл .env и настройки окружения")
    raise
