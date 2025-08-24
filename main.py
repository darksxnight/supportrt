import logging
import asyncio
import sys
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.types import ErrorEvent

from config import Config
from storage import user_levels, set_user_level, init_punishment_system, load_initial_data, cleanup_old_data
from database import init_database, db
from filters import RateLimitFilter
from handlers import send_error_log

# Импорты команд
from commands import (
    cmd_start, cmd_pending, cmd_checkprofile, cmd_setlevel, 
    cmd_getid, cmd_help, cmd_stats, cmd_users, cmd_mods,
    cmd_settings, cmd_backup, cmd_status, cmd_emergency,
    cmd_reports, handle_cancel, handle_new_message, handle_admin_callback,
    register_commands  # Новая функция для регистрации команд
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
    """Фоновые задачи для обслуживания системы"""
    while True:
        try:
            # Очистка старых данных из базы
            cleanup_old_data()
            logger.info("✅ Фоновая очистка данных выполнена")
            
            # Проверка соединения с базой данных
            if db and not db.connection.is_connected():
                logger.warning("📡 Переподключение к MySQL...")
                db.connect()
            
            await asyncio.sleep(3600)  # Каждый час
        
        except Exception as e:
            logger.error(f"Ошибка в фоновой задаче: {e}")
            await asyncio.sleep(300)  # Ждем 5 минут при ошибке

async def database_health_check():
    """Проверка здоровья базы данных"""
    while True:
        try:
            if db and db.connection.is_connected():
                # Простая проверка запросом
                with db.get_cursor() as cursor:
                    cursor.execute("SELECT 1")
                    logger.debug("✅ Проверка базы данных: OK")
            else:
                logger.warning("❌ База данных не подключена")
                
            await asyncio.sleep(300)  # Проверка каждые 5 минут
            
        except Exception as e:
            logger.error(f"Ошибка проверки здоровья БД: {e}")
            await asyncio.sleep(60)

async def startup_tasks():
    """Задачи выполняемые при запуске бота"""
    logger.info("🚀 Выполнение задач запуска...")
    
    # Загрузка данных из базы
    try:
        load_initial_data()
        logger.info(f"✅ Загружено {len(user_levels)} пользователей")
    except Exception as e:
        logger.error(f"❌ Ошибка загрузки данных: {e}")
    
    # Установка уровней по умолчанию
    try:
        set_user_level(Config.MODERATOR_ID, 1)
        set_user_level(Config.OWNER_ID, 3)
        logger.info("✅ Уровни пользователей установлены")
    except Exception as e:
        logger.error(f"❌ Ошибка установки уровней: {e}")
    
    # Очистка старых данных
    try:
        cleanup_old_data()
        logger.info("✅ Очистка старых данных выполнена")
    except Exception as e:
        logger.error(f"❌ Ошибка очистки данных: {e}")

async def shutdown_tasks():
    """Задачи выполняемые при выключении бота"""
    logger.info("🛑 Выполнение задач выключения...")
    
    # Закрытие соединения с базой
    if db:
        db.disconnect()
        logger.info("✅ Соединение с базой данных закрыто")
    
    # Остановка системы наказаний
    if 'punishment_system' in globals():
        await punishment_system.stop()
        logger.info("✅ Система наказаний остановлена")

async def main():
    try:
        # Валидация конфигурации
        Config.validate()
        logger.info("✅ Конфигурация проверена")
        
        # Инициализация базы данных MySQL
        if not init_database(
            Config.MYSQL_HOST,
            Config.MYSQL_USER, 
            Config.MYSQL_PASSWORD,
            Config.MYSQL_DATABASE
        ):
            logger.error("❌ Не удалось подключиться к MySQL")
            return
        
        logger.info("✅ MySQL подключена успешно")
        
        # Инициализация Redis для FSM
        storage = RedisStorage.from_url('redis://localhost:6379/0')
        bot = Bot(token=Config.BOT_TOKEN)
        dp = Dispatcher(storage=storage)
        
        # Задачи при запуске
        await startup_tasks()
        
        # Инициализация систем
        punishment_system = init_punishment_system(bot)
        await punishment_system.start()
        logger.info("✅ Система наказаний запущена")
        
        # Регистрируем обработчики ошибок
        dp.errors.register(global_error_handler)
        
        # Регистрируем основные команды
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

        # Регистрируем дополнительные команды
        register_commands(dp)

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
        asyncio.create_task(database_health_check())
        
        logger.info("🤖 Бот запущен успешно!")
        logger.info(f"📊 Пользователей в памяти: {len(user_levels)}")
        logger.info(f"📨 Сообщений в очереди: {len(getattr(storage, 'pending_messages', {}))}")
        logger.info(f"🗄️  База данных: {Config.MYSQL_DATABASE} на {Config.MYSQL_HOST}")
        
        # Запускаем поллинг
        await dp.start_polling(bot)
        
    except Exception as e:
        logger.critical(f"❌ Не удалось запустить бота: {e}", exc_info=True)
        await shutdown_tasks()
        sys.exit(1)

if __name__ == "__main__":
    # Обработка graceful shutdown
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("🛑 Бот остановлен пользователем")
        asyncio.run(shutdown_tasks())
    except Exception as e:
        logger.critical(f"❌ Критическая ошибка: {e}", exc_info=True)
        asyncio.run(shutdown_tasks())
        sys.exit(1)
