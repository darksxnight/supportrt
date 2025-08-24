from aiogram import types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
import datetime
import json

from config import Config
from storage import pending_messages, user_levels, moderator_stats, get_punishments, punishments
from keyboards import create_moderation_keyboard, get_cancel_keyboard, get_start_keyboard, create_punishment_keyboard

system_settings = {
    'auto_moderation': False,
    'max_messages_per_hour': 5,
    'blacklist_words': ['спам', 'оскорбление', 'реклама'],
    'notifications_enabled': True
}

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
        await message.answer("📭 Нет сообщений в ожидании модерации")
        return
    
    for msg_id, msg_data in pending_messages.items():
        if msg_data['user_id'] == message.from_user.id:
            continue
            
        if msg_data['type'] == 'text':
            await message.answer(
                f"📨 Сообщение для модерации:\n\n{msg_data['content']}",
                reply_markup=create_moderation_keyboard(msg_id)
            )
        elif msg_data['type'] == 'photo':
            await message.answer_photo(
                msg_data['file_id'],
                caption=msg_data.get('caption', ''),
                reply_markup=create_moderation_keyboard(msg_id)
            )

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
    
    profile_text = f"🪪 Никнейм модератора: @{message.reply_to_message.from_user.username}\n"
    profile_text += f"ℹ️ Должность: {'Модератор' if target_level == 1 else 'Технический модератор' if target_level == 2 else 'Владелец'}\n"
    profile_text += f"❔ ID: {target_id}\n"
    profile_text += f"🟢 Одобренных сообщений: {stats['approved']}\n"
    profile_text += f"🔴 Отказанных сообщений: {stats['rejected']}\n"
    profile_text += f"📂 Рассмотренных сообщений: {stats['reviewed']}\n"
    profile_text += f"♦️ Предупреждений: {stats['warnings']}\n"
    
    if user_level >= 2:
        profile_text += f"📜 Выдано наказаний: {user_punishments['mutes']} заглушки, {user_punishments['warnings']} предупреждения, {user_punishments['bans']} блокировки\n"
    
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
        await message.answer(f"✅ Уровень пользователя {target_id} установлен на {level}")
        
    except ValueError:
        await message.answer("❌ Неверный формат команды")

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
        """
    
    elif user_level == 1:
        help_text = """
🤖 **Помощь по боту** - Уровень: Модератор

📋 **Доступные команды:**
/start - Начать работу с ботом  
/getid - Получить свой ID
/pending - Просмотр сообщений на модерации
/help - Показать эту справку
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
    total_messages = sum([stats['reviewed'] for stats in moderator_stats.values()])
    approved = sum([stats['approved'] for stats in moderator_stats.values()])
    rejected = sum([stats['rejected'] for stats in moderator_stats.values()])
    
    approval_rate = round((approved / total_messages * 100) if total_messages > 0 else 0, 1)
    rejection_rate = round((rejected / total_messages * 100) if total_messages > 0 else 0, 1)
    
    stats_text = f"📊 Статистика системы\n\n"
    stats_text += f"👥 Пользователи: {total_users}\n"
    stats_text += f"📨 Сообщений всего: {total_messages}\n"
    stats_text += f"✅ Одобренных: {approved} ({approval_rate}%)\n"
    stats_text += f"❌ Отклоненных: {rejected} ({rejection_rate}%)\n"
    stats_text += f"📂 В ожидании: {len(pending_messages)}\n\n"
    stats_text += f"⚡️ Активность:\n"
    stats_text += f"• Модераторов онлайн: {sum(1 for uid, level in user_levels.items() if level >= 1)}\n"
    stats_text += f"• Действий за сегодня: {total_messages}"
    
    await message.answer(stats_text)

async def cmd_users(message: types.Message):
    if user_levels.get(message.from_user.id, 0) != 3:
        await message.answer("❌ У вас нет прав для этой команды")
        return
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👥 Список пользователей", callback_data="users_list")],
        [InlineKeyboardButton(text="🔍 Поиск пользователя", callback_data="users_search")],
        [InlineKeyboardButton(text="📊 Статистика пользователей", callback_data="users_stats")]
    ])
    
    await message.answer("👥 Управление пользователями", reply_markup=keyboard)

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
        mods_text += f"{i}. ID: {mod_id} | Уровень: {user_levels[mod_id]}\n"
        mods_text += f"   ✅ {stats['approved']} | ❌ {stats['rejected']} | ⚠️ {stats['warnings']}\n\n"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Детальная статистика", callback_data="mods_detailed")],
        [InlineKeyboardButton(text="🛑 Заблокировать модератора", callback_data="mods_ban")],
        [InlineKeyboardButton(text="⚡️ Изменить уровень", callback_data="mods_level")]
    ])
    
    await message.answer(mods_text, reply_markup=keyboard)

async def cmd_settings(message: types.Message):
    if user_levels.get(message.from_user.id, 0) != 3:
        await message.answer("❌ У вас нет прав для этой команды")
        return
    
    settings_text = f"⚙️ Настройки системы\n\n"
    settings_text += f"Авто-модерация: {'✅' if system_settings['auto_moderation'] else '❌'}\n"
    settings_text += f"Макс. сообщений в час: {system_settings['max_messages_per_hour']}\n"
    settings_text += f"Черный список слов: {len(system_settings['blacklist_words'])} слов\n"
    settings_text += f"Уведомления: {'✅' if system_settings['notifications_enabled'] else '❌'}\n"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔧 Авто-модерация", callback_data="setting_auto_mod"),
            InlineKeyboardButton(text="📝 Лимит сообщений", callback_data="setting_msg_limit")
        ],
        [
            InlineKeyboardButton(text="🚫 Черный список", callback_data="setting_blacklist"),
            InlineKeyboardButton(text="🔔 Уведомления", callback_data="setting_notifications")
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
        'timestamp': datetime.datetime.now().isoformat()
    }
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💾 Создать backup", callback_data="backup_create")],
        [InlineKeyboardButton(text="📤 Экспорт в JSON", callback_data="backup_export")],
        [InlineKeyboardButton(text="📥 Восстановить", callback_data="backup_restore")]
    ])
    
    await message.answer("💾 Управление backup", reply_markup=keyboard)

async def cmd_status(message: types.Message):
    if user_levels.get(message.from_user.id, 0) != 3:
        await message.answer("❌ У вас нет прав для этой команда")
        return
    
    status_text = f"🖥️ Статус системы\n\n"
    status_text += f"Бот: ✅ Online\n"
    status_text += f"Пользователи: {len(user_levels)} в памяти\n"
    status_text += f"Сообщений в ожидании: {len(pending_messages)}\n"
    status_text += f"Логи: ✅ Активны\n\n"
    status_text += f"📈 Загрузка:\n"
    status_text += f"• Память: ~{len(str(user_levels)) + len(str(moderator_stats))} KB\n"
    status_text += f"• Время работы: {datetime.datetime.now().strftime('%H:%M:%S')}"
    
    await message.answer(status_text)

async def cmd_emergency(message: types.Message):
    if user_levels.get(message.from_user.id, 0) != 3:
        await message.answer("❌ У вас нет прав для этой команды")
        return
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛑 Остановить бота", callback_data="emergency_stop")],
        [InlineKeyboardButton(text="🧹 Очистить очередь", callback_data="emergency_clear")],
        [InlineKeyboardButton(text="🔕 Отключить уведомления", callback_data="emergency_mute")],
        [InlineKeyboardButton(text="📢 Рассылка пользователям", callback_data="emergency_broadcast")]
    ])
    
    await message.answer("🚨 Экстренные команды\n\nИспользуйте с осторожностью!", reply_markup=keyboard)

async def cmd_reports(message: types.Message):
    if user_levels.get(message.from_user.id, 0) != 3:
        await message.answer("❌ У вас нет прав для этой команды")
        return
    
    report_text = f"📈 Ежедневный отчет\n\n"
    report_text += f"📅 {datetime.datetime.now().strftime('%d %B %Y')}\n"
    report_text += "———————————————\n"
    report_text += f"📨 Сообщений: {sum([stats['reviewed'] for stats in moderator_stats.values()])}\n"
    report_text += f"✅ Одобрено: {sum([stats['approved'] for stats in moderator_stats.values()])}\n"
    report_text += f"❌ Отклонено: {sum([stats['rejected'] for stats in moderator_stats.values()])}\n"
    report_text += f"👥 Активных пользователей: {len(user_levels)}\n\n"
    
    top_mods = sorted(
        [(uid, stats['reviewed']) for uid, stats in moderator_stats.items()], 
        key=lambda x: x[1], 
        reverse=True
    )[:3]
    
    if top_mods:
        report_text += "🏆 Топ модераторов:\n"
        for i, (mod_id, actions) in enumerate(top_mods, 1):
            report_text += f"{i}. ID {mod_id} - {actions} действий\n"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Детальный отчет", callback_data="report_detailed")],
        [InlineKeyboardButton(text="📅 За период", callback_data="report_period")],
        [InlineKeyboardButton(text="📤 Экспорт в CSV", callback_data="report_export")]
    ])
    
    await message.answer(report_text, reply_markup=keyboard)

async def handle_admin_callback(callback: types.CallbackQuery):
    data = callback.data
    user_level = user_levels.get(callback.from_user.id, 0)
    
    if user_level != 3:
        await callback.answer("❌ Нет прав")
        return
    
    if data == "users_list":
        users_list = "\n".join([f"ID: {uid} | Уровень: {level}" for uid, level in user_levels.items()][:10])
        await callback.message.answer(f"👥 Последние 10 пользователей:\n\n{users_list}")
    
    elif data == "emergency_clear":
        pending_messages.clear()
        await callback.message.answer("✅ Очередь модерации очищена")
    
    elif data == "setting_auto_mod":
        system_settings['auto_moderation'] = not system_settings['auto_moderation']
        status = "включена" if system_settings['auto_moderation'] else "выключена"
        await callback.message.answer(f"✅ Авто-модерация {status}")
    
    await callback.answer()