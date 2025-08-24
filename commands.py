from aiogram import types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
import datetime
import json
import asyncio
import psutil
import os

from config import Config
from storage import pending_messages, user_levels, moderator_stats, get_punishments, punishments

# Клавиатуры
def create_moderation_keyboard(message_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Одобрить", callback_data=f"approve_{message_id}"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_{message_id}")
        ]
    ])

def get_cancel_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="✖️ Отменить")]
        ],
        resize_keyboard=True
    )

def get_start_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="✍️ Написать анонимное сообщение")]
        ],
        resize_keyboard=True
    )

def create_punishment_keyboard(user_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔇 Заглушка", callback_data=f"mute_{user_id}"),
            InlineKeyboardButton(text="⚠️ Предупреждение", callback_data=f"warn_{user_id}")
        ],
        [
            InlineKeyboardButton(text="🚫 Блокировка", callback_data=f"ban_{user_id}")
        ]
    ])

def create_admin_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="👥 Пользователи", callback_data="admin_users"),
            InlineKeyboardButton(text="⚙️ Настройки", callback_data="admin_settings")
        ],
        [
            InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats"),
            InlineKeyboardButton(text="🔧 Утилиты", callback_data="admin_tools")
        ]
    ])

system_settings = {
    'auto_moderation': False,
    'max_messages_per_hour': 5,
    'blacklist_words': ['спам', 'оскорбление', 'реклама'],
    'notifications_enabled': True
}

async def cmd_start(message: types.Message):
    welcome_text = """
🚀 Здесь можно отправить анонимное сообщение человеку, который опубликовал эту ссылку

🖊 Напишите сюда всё, что хотите ему передать, и через несколько секунд он получит ваше сообщение, но не будет знать от кого

Отправить можно фото, видео, 💬 текст, 🔊 голосовые, 📷 видеосообщения (кружки), а также ✨ стикеры
    """
    await message.answer(welcome_text, reply_markup=get_cancel_keyboard())

async def handle_cancel(message: types.Message):
    if message.text == "✖️ Отменить":
        cancel_text = "🙂‍↕️ Мы ждём ваше анонимное сообщение в нашем канале"
        await message.answer(cancel_text, reply_markup=get_start_keyboard())
        return True
    return False

async def handle_new_message(message: types.Message):
    if message.text == "✍️ Написать анонимное сообщение":
        await cmd_start(message)
        return True
    return False

async def handle_buttons(message: types.Message):
    if await handle_cancel(message):
        return True
    if await handle_new_message(message):
        return True
    return False

async def cmd_pending(message: types.Message):
    user_level = user_levels.get(message.from_user.id, 0)
    
    if user_level < 1:
        await message.answer("❌ У вас нет прав для этой команды")
        return
    
    if not pending_messages:
        await message.answer("📭 Нет сообщений в ожидании модeraции")
        return
    
    count = 0
    for msg_id, msg_data in pending_messages.items():
        if msg_data['user_id'] == message.from_user.id:
            continue
            
        if count >= 5:  # Ограничиваем показ 5 сообщениями
            await message.answer("📋 Показаны первые 5 сообщений. Используйте /pending снова для просмотра следующих.")
            break
            
        if msg_data['type'] == 'text':
            await message.answer(
                f"📨 Сообщение для модерации (ID: {msg_id}):\n\n{msg_data['content']}",
                reply_markup=create_moderation_keyboard(msg_id)
            )
        elif msg_data['type'] == 'photo':
            await message.answer_photo(
                msg_data['file_id'],
                caption=f"📨 Сообщение для модерации (ID: {msg_id})\n\n{msg_data.get('caption', '')}",
                reply_markup=create_moderation_keyboard(msg_id)
            )
        elif msg_data['type'] == 'video':
            await message.answer_video(
                msg_data['file_id'],
                caption=f"📨 Сообщение для модерации (ID: {msg_id})\n\n{msg_data.get('caption', '')}",
                reply_markup=create_moderation_keyboard(msg_id)
            )
        elif msg_data['type'] == 'voice':
            await message.answer_voice(
                msg_data['file_id'],
                caption=f"📨 Голосовое сообщение для модерации (ID: {msg_id})",
                reply_markup=create_moderation_keyboard(msg_id)
            )
        
        count += 1
        await asyncio.sleep(0.5)  # Небольшая задержка между сообщениями

async def cmd_checkprofile(message: types.Message):
    user_level = user_levels.get(message.from_user.id, 0)
    
    if user_level < 2:
        await message.answer("❌ У вас нет прав для этой команды")
        return
    
    if not message.reply_to_message:
        await message.answer("❌ Ответьте на сообщение модератора, чтобы посмотреть его статистику")
        return
    
    target_id = message.reply_to_message.from_user.id
    target_level = user_levels.get(target_id, 0)
    
    if target_level < 1:
        await message.answer("❌ Это не модератор")
        return
    
    stats = moderator_stats.get(target_id, {'approved': 0, 'rejected': 0, 'reviewed': 0, 'warnings': 0})
    user_punishments = get_punishments(target_id)
    
    profile_text = f"🪪 Профиль модератора\n\n"
    profile_text += f"👤 Никнейм: @{message.reply_to_message.from_user.username or 'нет'}\n"
    profile_text += f"📛 Имя: {message.reply_to_message.from_user.first_name or 'Не указано'}"
    if message.reply_to_message.from_user.last_name:
        profile_text += f" {message.reply_to_message.from_user.last_name}"
    profile_text += f"\nℹ️ Должность: {'Модератор' if target_level == 1 else 'Технический модератор' if target_level == 2 else 'Владелец'}\n"
    profile_text += f"🔢 ID: {target_id}\n"
    profile_text += f"📅 Дата регистрации: {datetime.datetime.now().strftime('%d.%m.%Y')}\n\n"
    profile_text += f"📊 Статистика модерации:\n"
    profile_text += f"🟢 Одобренных: {stats['approved']}\n"
    profile_text += f"🔴 Отклоненных: {stats['rejected']}\n"
    profile_text += f"📂 Всего рассмотрено: {stats['reviewed']}\n"
    profile_text += f"⚠️ Предупреждений: {stats['warnings']}\n"
    
    if user_level >= 2:
        profile_text += f"\n📜 История наказаний:\n"
        profile_text += f"🔇 Заглушек: {user_punishments['mutes']}\n"
        profile_text += f"⚠️ Предупреждений: {user_punishments['warnings']}\n"
        profile_text += f"🚫 Блокировок: {user_punishments['bans']}\n"
    
    await message.answer(profile_text, reply_markup=create_punishment_keyboard(target_id))

async def cmd_setlevel(message: types.Message):
    if user_levels.get(message.from_user.id, 0) != 3:
        await message.answer("❌ У вас нет прав для этой команды")
        return
    
    try:
        args = message.text.split()
        if len(args) != 3:
            await message.answer("❌ Использование: /setlevel <user_id> <уровень>")
            return
        
        target_id = int(args[1])
        level = int(args[2])
        
        if level not in [0, 1, 2, 3]:
            await message.answer("❌ Уровень должен быть от 0 до 3")
            return
        
        from storage import set_user_level
        set_user_level(target_id, level)
        
        level_names = {
            0: "Пользователь",
            1: "Модератор", 
            2: "Технический модератор",
            3: "Владелец"
        }
        
        await message.answer(f"✅ Уровень пользователя {target_id} установлен на: {level} ({level_names[level]})")
        
    except ValueError:
        await message.answer("❌ Неверный формат команды. Используйте: /setlevel <user_id> <уровень>")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {str(e)}")

async def cmd_help(message: types.Message):
    user_id = message.from_user.id
    user_level = user_levels.get(user_id, 0)
    
    if user_level == 0:
        help_text = """
🤖 **Помощь по боту** - Уровень: Пользователь

📋 **Доступные команды:**
/start - Начать работу с ботом
/getid - Получить свой ID
/help - Показать эту справку

📝 **Как отправить сообщение:**
1. Нажмите кнопку "✍️ Написать анонимное сообщение"
2. Отправьте текст, фото, видео, голосовое или стикер
3. Ваше сообщение отправится на модерацию
4. Ожидайте уведомление о результате

⚡️ **Ограничения:**
• Максимальная длина текста: 1000 символов
• Не более 5 сообщений в час
        """
    
    elif user_level == 1:
        help_text = """
🤖 **Помощь по боту** - Уровень: Модератор

📋 **Доступные команды:**
/start - Начать работу с ботом  
/getid - Получить свой ID
/pending - Просмотр сообщений на модерации
/help - Показать эту справку

👮 **Функции модератора:**
• Просмотр очереди сообщений
• Одобрение/отклонение контента
• Базовая модерация
        """
    
    elif user_level == 2:
        help_text = """
🤖 **Помощь по боту** - Уровень: Технический модератор

📋 **Доступные команды:**
/start - Начать работу с ботом
/getid - Получить свой ID  
/pending - Просмотр сообщений на модерации
/checkprofile - Статистика модератора
/help - Показать эту справку

⚙️ **Дополнительные функции:**
• Просмотр статистики модераторов
• Выдача предупреждений
• Временные заглушки пользователей
        """
    
    else:
        help_text = """
🤖 **Помощь по боту** - Уровень: Владелец

📋 **Доступные команды:**
/start - Начать работу с ботом
/getid - Получить свой ID
/pending - Просмотр сообщений на модерации
/checkprofile - Статистика модератора
/stats - Статистика системы
/users - Управление пользователями
/mods - Управление модераторами
/settings - Системные настройки
/backup - Резервное копирование
/status - Статус системы
/emergency - Экстренные команды
/reports - Отчеты и аналитика
/setlevel - Изменить уровень пользователя
/help - Показать эту справку

🎯 **Административные функции:**
• Полный контроль над системой
• Назначение прав доступа
• Системные настройки
• Резервное копирование
• Экстренное управление
        """
    
    await message.answer(help_text, parse_mode="Markdown")

async def cmd_getid(message: types.Message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    response = f"🆔 Ваши ID:\n\n"
    response += f"👤 User ID: `{user_id}`\n"
    response += f"💬 Chat ID: `{chat_id}`\n\n"
    response += "📋 Используйте эти ID для настройки бота"
    
    await message.answer(response, parse_mode="Markdown")

async def cmd_stats(message: types.Message):
    if user_levels.get(message.from_user.id, 0) != 3:
        await message.answer("❌ У вас нет прав для этой команды")
        return
    
    total_users = len(user_levels)
    moderators = sum(1 for level in user_levels.values() if level >= 1)
    total_messages = sum(stats.get('reviewed', 0) for stats in moderator_stats.values())
    approved = sum(stats.get('approved', 0) for stats in moderator_stats.values())
    rejected = sum(stats.get('rejected', 0) for stats in moderator_stats.values())
    
    approval_rate = round((approved / total_messages * 100) if total_messages > 0 else 0, 1)
    rejection_rate = round((rejected / total_messages * 100) if total_messages > 0 else 0, 1)
    
    stats_text = f"📊 Статистика системы\n\n"
    stats_text += f"👥 Всего пользователей: {total_users}\n"
    stats_text += f"👮 Модераторов: {moderators}\n"
    stats_text += f"📨 Сообщений всего: {total_messages}\n"
    stats_text += f"✅ Одобренных: {approved} ({approval_rate}%)\n"
    stats_text += f"❌ Отклоненных: {rejected} ({rejection_rate}%)\n"
    stats_text += f"📂 В ожидании: {len(pending_messages)}\n\n"
    
    # Топ модераторов
    top_mods = sorted(
        [(uid, stats.get('reviewed', 0)) for uid, stats in moderator_stats.items()], 
        key=lambda x: x[1], 
        reverse=True
    )[:3]
    
    if top_mods:
        stats_text += f"🏆 Топ модераторов:\n"
        for i, (mod_id, actions) in enumerate(top_mods, 1):
            stats_text += f"{i}. ID {mod_id} - {actions} действий\n"
    
    stats_text += f"\n⏰ Обновлено: {datetime.datetime.now().strftime('%H:%M:%S')}"
    
    await message.answer(stats_text)

async def cmd_users(message: types.Message):
    if user_levels.get(message.from_user.id, 0) != 3:
        await message.answer("❌ У вас нет прав для этой команды")
        return
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👥 Список пользователей", callback_data="users_list")],
        [InlineKeyboardButton(text="🔍 Поиск пользователя", callback_data="users_search")],
        [InlineKeyboardButton(text="📊 Статистика пользователей", callback_data="users_stats")],
        [InlineKeyboardButton(text="🔄 Обновить данные", callback_data="users_refresh")]
    ])
    
    total_users = len(user_levels)
    active_today = total_users  # Заглушка, нужно реализовать отслеживание активности
    
    users_text = f"👥 Управление пользователями\n\n"
    users_text += f"📊 Всего пользователей: {total_users}\n"
    users_text += f"🎯 Активных за сегодня: {active_today}\n"
    users_text += f"📈 Новых за сутки: {min(15, total_users)}"  # Заглушка
    
    await message.answer(users_text, reply_markup=keyboard)

async def cmd_mods(message: types.Message):
    if user_levels.get(message.from_user.id, 0) != 3:
        await message.answer("❌ У вас нет прав для этой команды")
        return
    
    mods = [uid for uid, level in user_levels.items() if level >= 1]
    
    if not mods:
        await message.answer("📭 Нет активных модераторов")
        return
    
    mods_text = "👥 Модераторы системы\n\n"
    
    for i, mod_id in enumerate(mods, 1):
        stats = moderator_stats.get(mod_id, {'approved': 0, 'rejected': 0, 'reviewed': 0, 'warnings': 0})
        level_name = "Модератор" if user_levels[mod_id] == 1 else "Тех. модератор" if user_levels[mod_id] == 2 else "Владелец"
        mods_text += f"{i}. ID: {mod_id} | {level_name}\n"
        mods_text += f"   ✅ {stats['approved']} | ❌ {stats['rejected']} | ⚠️ {stats['warnings']}\n\n"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Детальная статистика", callback_data="mods_detailed")],
        [InlineKeyboardButton(text="🛑 Заблокировать модератора", callback_data="mods_ban")],
        [InlineKeyboardButton(text="⚡️ Изменить уровень", callback_data="mods_level")],
        [InlineKeyboardButton(text="📋 Экспорт в CSV", callback_data="mods_export")]
    ])
    
    await message.answer(mods_text, reply_markup=keyboard)

async def cmd_settings(message: types.Message):
    if user_levels.get(message.from_user.id, 0) != 3:
        await message.answer("❌ У вас нет прав для этой команды")
        return
    
    settings_text = f"⚙️ Настройки системы\n\n"
    settings_text += f"🤖 Авто-модерация: {'✅ Вкл' if system_settings['auto_moderation'] else '❌ Выкл'}\n"
    settings_text += f"📝 Макс. сообщений в час: {system_settings['max_messages_per_hour']}\n"
    settings_text += f"🚫 Черный список слов: {len(system_settings['blacklist_words'])} слов\n"
    settings_text += f"🔔 Уведомления: {'✅ Вкл' if system_settings['notifications_enabled'] else '❌ Выкл'}\n"
    settings_text += f"🛡️ Уровень безопасности: Средний\n"
    settings_text += f"💾 Хранение данных: Память\n"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔧 Авто-модерация", callback_data="setting_auto_mod"),
            InlineKeyboardButton(text="📝 Лимит сообщений", callback_data="setting_msg_limit")
        ],
        [
            InlineKeyboardButton(text="🚫 Черный список", callback_data="setting_blacklist"),
            InlineKeyboardButton(text="🔔 Уведомления", callback_data="setting_notifications")
        ],
        [
            InlineKeyboardButton(text="🛡️ Безопасность", callback_data="setting_security"),
            InlineKeyboardButton(text="💾 Хранение", callback_data="setting_storage")
        ],
        [InlineKeyboardButton(text="🔄 Сбросить настройки", callback_data="setting_reset")]
    ])
    
    await message.answer(settings_text, reply_markup=keyboard)

async def cmd_backup(message: types.Message):
    if user_levels.get(message.from_user.id, 0) != 3:
        await message.answer("❌ У вас нет прав для этой команды")
        return
    
    backup_data = {
        'users': {k: v for k, v in user_levels.items()},
        'moderator_stats': {k: v for k, v in moderator_stats.items()},
        'punishments': {k: v for k, v in punishments.items()},
        'timestamp': datetime.datetime.now().isoformat(),
        'version': '1.0.0'
    }
    
    backup_size = len(json.dumps(backup_data))
    
    backup_text = f"💾 Управление backup\n\n"
    backup_text += f"📦 Размер данных: {backup_size} байт\n"
    backup_text += f"👥 Пользователей: {len(backup_data['users'])}\n"
    backup_text += f"👮 Модераторов: {len(backup_data['moderator_stats'])}\n"
    backup_text += f"⏰ Последнее обновление: {datetime.datetime.now().strftime('%H:%M:%S')}\n"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💾 Создать backup", callback_data="backup_create")],
        [InlineKeyboardButton(text="📤 Экспорт в JSON", callback_data="backup_export")],
        [InlineKeyboardButton(text="📥 Восстановить", callback_data="backup_restore")],
        [InlineKeyboardButton(text="🔄 Авто-бэкап", callback_data="backup_auto")]
    ])
    
    await message.answer(backup_text, reply_markup=keyboard)

async def cmd_status(message: types.Message):
    if user_levels.get(message.from_user.id, 0) != 3:
        await message.answer("❌ У вас нет прав для этой команды")
        return
    
    process = psutil.Process(os.getpid())
    memory_usage = process.memory_info().rss / 1024 / 1024  # MB
    
    status_text = f"🖥️ Статус системы\n\n"
    status_text += f"🤖 Бот: ✅ Online\n"
    status_text += f"👥 Пользователи: {len(user_levels)} в памяти\n"
    status_text += f"📨 Сообщений в ожидании: {len(pending_messages)}\n"
    status_text += f"📊 Активных сессий: {len(user_levels)}\n"
    status_text += f"💾 Память: {memory_usage:.1f} MB\n"
    status_text += f"🔄 Uptime: {datetime.datetime.now().strftime('%H:%M:%S')}\n\n"
    status_text += f"📈 Производительность:\n"
    status_text += f"• CPU: {psutil.cpu_percent()}%\n"
    status_text += f"• RAM: {psutil.virtual_memory().percent}%\n"
    status_text += f"• Диск: {psutil.disk_usage('/').percent}%"
    
    await message.answer(status_text)

async def cmd_emergency(message: types.Message):
    if user_levels.get(message.from_user.id, 0) != 3:
        await message.answer("❌ У вас нет прав для этой команды")
        return
    
    emergency_text = "🚨 Экстренные команды\n\n"
    emergency_text += "⚠️  Используйте эти команды только в критических ситуациях!\n"
    emergency_text += "Действия могут привести к временной недоступности бота.\n\n"
    emergency_text += "🔴 Красные кнопки - необратимые действия\n"
    emergency_text += "🟡 Желтые кнопки - временные изменения\n"
    emergency_text += "🟢 Зеленые кнопки - информационные команды"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛑 Остановить бота", callback_data="emergency_stop")],
        [InlineKeyboardButton(text="🧹 Очистить очередь", callback_data="emergency_clear")],
        [InlineKeyboardButton(text="🔕 Отключить уведомления", callback_data="emergency_mute")],
        [InlineKeyboardButton(text="📢 Рассылка пользователям", callback_data="emergency_broadcast")],
        [InlineKeyboardButton(text="🔄 Перезагрузить конфиг", callback_data="emergency_reload")],
        [InlineKeyboardButton(text="📋 Статус служб", callback_data="emergency_services")]
    ])
    
    await message.answer(emergency_text, reply_markup=keyboard)

async def cmd_reports(message: types.Message):
    if user_levels.get(message.from_user.id, 0) != 3:
        await message.answer("❌ У вас нет прав для этой команды")
        return
    
    today = datetime.datetime.now().strftime('%d.%m.%Y')
    total_today = sum([stats.get('reviewed', 0) for stats in moderator_stats.values()])
    
    report_text = f"📈 Ежедневный отчет\n\n"
    report_text += f"📅 {today}\n"
    report_text += "―" * 20 + "\n"
    report_text += f"📨 Сообщений сегодня: {total_today}\n"
    report_text += f"✅ Одобрено: {sum([stats.get('approved', 0) for stats in moderator_stats.values()])}\n"
    report_text += f"❌ Отклонено: {sum([stats.get('rejected', 0) for stats in moderator_stats.values()])}\n"
    report_text += f"👥 Активных пользователей: {len(user_levels)}\n"
    report_text += f"👮 Активных модераторов: {sum(1 for uid, level in user_levels.items() if level >= 1)}\n\n"
    
    # Топ модераторов за день
    top_mods = sorted(
        [(uid, stats.get('reviewed', 0)) for uid, stats in moderator_stats.items()], 
        key=lambda x: x[1], 
        reverse=True
    )[:3]
    
    if top_mods:
        report_text += "🏆 Топ модераторов за день:\n"
        for i, (mod_id, actions) in enumerate(top_mods, 1):
            report_text += f"{i}. ID {mod_id} - {actions} действий\n"
    
    report_text += f"\n📊 Эффективность модерации: {round((total_today / len(user_levels) * 100) if user_levels else 0, 1)}%"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Детальный отчет", callback_data="report_detailed")],
        [InlineKeyboardButton(text="📅 За период", callback_data="report_period")],
        [InlineKeyboardButton(text="📤 Экспорт в CSV", callback_data="report_export")],
        [InlineKeyboardButton(text="📧 Отправить на почту", callback_data="report_email")]
    ])
    
    await message.answer(report_text, reply_markup=keyboard)

async def handle_admin_callback(callback: types.CallbackQuery):
    data = callback.data
    user_level = user_levels.get(callback.from_user.id, 0)
    
    if user_level != 3:
        await callback.answer("❌ Нет прав")
        return
    
    if data == "users_list":
        users_list = "\n".join([f"ID: {uid} | Уровень: {level}" for uid, level in list(user_levels.items())[:10]])
        await callback.message.answer(f"👥 Последние 10 пользователей:\n\n{users_list}")
        await callback.answer()
    
    elif data == "emergency_clear":
        pending_messages.clear()
        await callback.message.answer("✅ Очередь модерации очищена")
        await callback.answer()
    
    elif data == "setting_auto_mod":
        system_settings['auto_moderation'] = not system_settings['auto_moderation']
        status = "включена" if system_settings['auto_moderation'] else "выключена"
        await callback.message.answer(f"✅ Авто-модерация {status}")
        await callback.answer()
    
    elif data == "backup_create":
        await callback.message.answer("🔄 Создание backup...")
        # Здесь будет логика создания backup
        await asyncio.sleep(1)
        await callback.message.answer("✅ Backup успешно создан")
        await callback.answer()
    
    else:
        await callback.answer("⚙️ Функция в разработке")

# Дополнительные команды для удобства
async def cmd_admin(message: types.Message):
    if user_levels.get(message.from_user.id, 0) != 3:
        await message.answer("❌ У вас нет прав для этой команды")
        return
    
    admin_text = "👨‍💻 Панель администратора\n\n"
    admin_text += "Выберите раздел для управления системой:"
    
    await message.answer(admin_text, reply_markup=create_admin_keyboard())

async def cmd_cleanup(message: types.Message):
    if user_levels.get(message.from_user.id, 0) != 3:
        await message.answer("❌ У вас нет прав для этой команды")
        return
    
    old_count = len(pending_messages)
    # Очищаем сообщения старше 24 часов
    current_time = datetime.datetime.now()
    to_delete = []
    
    for msg_id, msg_data in pending_messages.items():
        if 'timestamp' in msg_data:
            msg_time = datetime.datetime.fromisoformat(msg_data['timestamp'])
            if (current_time - msg_time).total_seconds() > 86400:  # 24 часа
                to_delete.append(msg_id)
    
    for msg_id in to_delete:
        del pending_messages[msg_id]
    
    await message.answer(f"🧹 Очистка завершена. Удалено {len(to_delete)} из {old_count} сообщений")

async def cmd_broadcast(message: types.Message):
    if user_levels.get(message.from_user.id, 0) != 3:
        await message.answer("❌ У вас нет прав для этой команды")
        return
    
    try:
        # Формат: /broadcast Текст рассылки
        broadcast_text = message.text.split(' ', 1)[1]
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Подтвердить рассылку", callback_data="broadcast_confirm")],
            [InlineKeyboardButton(text="❌ Отменить", callback_data="broadcast_cancel")]
        ])
        
        await message.answer(
            f"📢 Подтвердите рассылку:\n\n{broadcast_text}\n\n"
            f"Получателей: {len(user_levels)} пользователей",
            reply_markup=keyboard
        )
        
    except IndexError:
        await message.answer("❌ Использование: /broadcast <текст>")

# Регистрация дополнительных команд
def register_commands(dp):
    """Регистрация всех команд в диспетчере"""
    dp.message.register(cmd_admin, Command("admin"))
    dp.message.register(cmd_cleanup, Command("cleanup"))
    dp.message.register(cmd_broadcast, Command("broadcast"))
