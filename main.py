import logging
import asyncio
import sys
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.types import ErrorEvent

from config import Config
from storage import user_levels, set_user_level, init_punishment_system, load_initial_data
from filters import RateLimitFilter
from handlers import send_error_log

# Импорты команд
from commands import (
    cmd_start, cmd_pending, cmd_checkprofile, cmd_setlevel, 
    cmd_getid, cmd_help, cmd_stats, cmd_users, cmd_mods,
    cmd_settings, cmd_backup, cmd_status, cmd_emergency,
    cmd_reports, handle_cancel, handle_new_message, handle_admin_callback
)

from handlers import (
    handle_text_message, handle_photo_message, handle_video_message,
    handle_voice_message, handle_video_note_message, handle_sticker_message,
    handle_document_message, handle_moderation, handle_punishment_callback,
    handle_punishment_reason, PunishmentStates
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

async def global_error_handler(event: ErrorEvent):
    logger.error(f"Global error: {event.exception}", exc_info=event.exception)
    await send_error_log("Global Error", str(event.exception))

async def background_tasks():
    """Фоновые задачи"""
    while True:
        try:
            # Здесь можно добавить периодические задачи
            # например, очистку кэша, проверку здоровья и т.д.
            await asyncio.sleep(300)  # Каждые 5 минут
        except Exception as e:
            logger.error(f"Background task error: {e}")
            await asyncio.sleep(60)

async def main():
    try:
        Config.validate()
        
        # Используем Redis вместо MemoryStorage
        storage = RedisStorage.from_url('redis://localhost:6379/0')
        bot = Bot(token=Config.BOT_TOKEN)
        dp = Dispatcher(storage=storage)
        
        # Загружаем данные из Redis
        load_initial_data()
        
        # Инициализируем системы
        punishment_system = init_punishment_system(bot)
        await punishment_system.start()
        
        # Устанавливаем уровни пользователей
        set_user_level(Config.MODERATOR_ID, 1)
        set_user_level(Config.OWNER_ID, 3)
        
        # Регистрируем обработчики
        dp.errors.register(global_error_handler)
        
        # Команды
        dp.message.register(cmd_start, Command("start"))
        dp.message.register(cmd_pending, Command("pending"))
        dp.message.register(cmd_checkprofile, Command("checkprofile"))
        dp.message.register(cmd_setlevel, Command("setlevel"))
        dp.message.register(cmd_getid, Command("getid"))
        dp.message.register(cmd_help, Command("help"))
        dp.message.register(cmd_stats, Command("stats"))
        dp.message.register(cmd_users, Command("users"))
        dp.message.register(cmd_mods, Command("mods"))
        dp.message.register(cmd_settings, Command("settings"))
        dp.message.register(cmd_backup, Command("backup"))
        dp.message.register(cmd_status, Command("status"))
        dp.message.register(cmd_emergency, Command("emergency"))
        dp.message.register(cmd_reports, Command("reports"))

        # Обработчики сообщений
        dp.message.register(handle_cancel, F.text == "✖️ Отменить")
        dp.message.register(handle_new_message, F.text == "✍️ Написать анонимное сообщение")

        # Обработчики контента с rate limiting
        rate_limit = RateLimitFilter(limit=5, period=60)
        dp.message.register(handle_text_message, F.text & rate_limit)
        dp.message.register(handle_photo_message, F.photo & rate_limit)
        dp.message.register(handle_video_message, F.video & rate_limit)
        dp.message.register(handle_voice_message, F.voice & rate_limit)
        dp.message.register(handle_video_note_message, F.video_note & rate_limit)
        dp.message.register(handle_sticker_message, F.sticker & rate_limit)
        dp.message.register(handle_document_message, F.document & rate_limit)

        # Обработчики callback'ов
        dp.callback_query.register(handle_moderation, F.data.startswith("approve_") | F.data.startswith("reject_"))
        dp.callback_query.register(handle_punishment_callback, F.data.startswith("mute_") | F.data.startswith("warn_") | F.data.startswith("ban_"))
        dp.callback_query.register(handle_admin_callback, F.data.startswith("users_") | F.data.startswith("mods_") | 
                                  F.data.startswith("setting_") | F.data.startswith("backup_") | 
                                  F.data.startswith("emergency_") | F.data.startswith("report_"))

        dp.message.register(handle_punishment_reason, PunishmentStates.waiting_for_reason)

        # Запускаем фоновые задачи
        asyncio.create_task(background_tasks())
        
        logger.info("Бот запущен успешно!")
        logger.info(f"Используется Redis storage")
        
        await dp.start_polling(bot)
        
    except Exception as e:
        logger.critical(f"Failed to start bot: {e}")
        if 'punishment_system' in locals():
            await punishment_system.stop()
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
