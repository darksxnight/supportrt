import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Основные настройки
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    MODERATOR_ID = int(os.getenv("MODERATOR_ID", 0))
    CHANNEL_ID = os.getenv("CHANNEL_ID")
    OWNER_ID = int(os.getenv("OWNER_ID", 0))
    
    # Каналы для логирования
    LOG_MODERATION_CHANNEL = os.getenv("LOG_MODERATION_CHANNEL", "@moderation_logs")
    LOG_PUNISHMENT_CHANNEL = os.getenv("LOG_PUNISHMENT_CHANNEL", "@punishment_logs") 
    OWNER_CHANNEL = os.getenv("OWNER_CHANNEL", "@owner_channel")
    MODERATION_CHAT = os.getenv("MODERATION_CHAT", "@moderation_chat")
    ERROR_CHANNEL = os.getenv("ERROR_CHANNEL", "@error_logs")
    
    # Настройки безопасности
    MAX_MESSAGES_PER_HOUR = int(os.getenv("MAX_MESSAGES_PER_HOUR", 5))
    MAX_MESSAGE_LENGTH = int(os.getenv("MAX_MESSAGE_LENGTH", 1000))
    
    # Настройки модeraции
    AUTO_MODERATION = os.getenv("AUTO_MODERATION", "False").lower() == "true"
    MODERATION_TIMEOUT = int(os.getenv("MODERATION_TIMEOUT", 300))
    
    # Настройки API и Webhooks
    API_HOST = os.getenv("API_HOST", "0.0.0.0")
    API_PORT = int(os.getenv("API_PORT", 8000))
    API_SECRET_KEY = os.getenv("API_SECRET_KEY", "your-secret-key-here")
    WEBHOOK_URL = os.getenv("WEBHOOK_URL", "")
    WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "webhook-secret-here")
    
    # Настройки наказаний
    DEFAULT_MUTE_DURATION = int(os.getenv("DEFAULT_MUTE_DURATION", 3600))
    DEFAULT_BAN_DURATION = int(os.getenv("DEFAULT_BAN_DURATION", 86400))
    
    @classmethod
    def validate(cls):
        errors = []
        
        if not cls.BOT_TOKEN:
            errors.append("BOT_TOKEN не установлен")
        if not cls.MODERATOR_ID:
            errors.append("MODERATOR_ID не установлен")
        if not cls.CHANNEL_ID:
            errors.append("CHANNEL_ID не установлен")
        if not cls.OWNER_ID:
            errors.append("OWNER_ID не установлен")
        
        if errors:
            raise ValueError(" | ".join(errors))
        
        if cls.MAX_MESSAGES_PER_HOUR <= 0:
            raise ValueError("MAX_MESSAGES_PER_HOUR должен быть больше 0")
        if cls.MAX_MESSAGE_LENGTH <= 0:
            raise ValueError("MAX_MESSAGE_LENGTH должен быть больше 0")