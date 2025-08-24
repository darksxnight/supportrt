import logging
import datetime
import traceback
from aiogram import types, F
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramForbiddenError

from config import Config
from storage import (
    add_message, get_message, delete_message, user_levels, 
    update_moderator_stats, add_warning, add_punishment, can_send_message,
    get_user_level, update_message_status
)
from keyboards import create_moderation_keyboard
from commands import get_cancel_keyboard, get_start_keyboard, check_command_access

logger = logging.getLogger(__name__)

class PunishmentStates(StatesGroup):
    waiting_for_reason = State()

def error_handler(func):
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            logger.error(f"Error in {func.__name__}: {e}\n{traceback.format_exc()}")
            await send_error_log(f"Error in {func.__name__}", str(e), traceback.format_exc())
            
            try:
                message = None
                for arg in args:
                    if isinstance(arg, (types.Message, types.CallbackQuery)):
                        message = arg
                        break
                
                if message and hasattr(message, 'answer'):
                    if isinstance(message, types.CallbackQuery):
                        await message.answer("❌ Произошла ошибка. Попробуйте позже.", show_alert=True)
                    else:
                        await message.answer("❌ Произошла ошибка. Попробуйте позже.")
            except:
                pass
            
    return wrapper

async def send_error_log(context: str, error: str, traceback_info: str = ""):
    try:
        error_message = f"🚨 ОШИБКА: {context}\n\n"
        error_message += f"❌ {error}\n\n"
        error_message += f"⏰ {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        
        if traceback_info:
            traceback_preview = traceback_info[:1000] + "..." if len(traceback_info) > 1000 else traceback_info
            error_message += f"\n\n🔍 Traceback:\n{traceback_preview}"
        
        await types.Bot.get_current().send_message(Config.ERROR_CHANNEL, error_message)
    except Exception as e:
        logger.error(f"Failed to send error log: {e}")

@error_handler
async def handle_permission_error(event: types.ErrorEvent):
    """Обработчик ошибок прав доступа"""
    if isinstance(event.exception, TelegramForbiddenError):
        # Бот не имеет прав в этом чате
        try:
            if hasattr(event.update, 'message') and event.update.message:
                await event.update.message.answer(
                    "❌ У меня нет прав администратора в этом чате. "
                    "Пожалуйста, предоставьте необходимые права или используйте команды в личных сообщениях."
                )
        except:
            pass
        return True
    return False

@error_handler
async def send_moderation_log(moderator_username: str, moderator_id: int, message_content: str, message_id: int, user_username: str, approved: bool):
    try:
        status_emoji = "✅" if approved else "❌"
        status_text = "одобрено" if approved else "отклонено"
        
        if len(message_content) > 500:
            message_content = message_content[:500] + "..."
        
        log_message = f"⚙️ Новый лог {status_emoji}\n\n"
        log_message += f"👩‍💻 Модератор: @{moderator_username}\n"
        log_message += f"📩 Анонимное сообщение: {message_content}\n"
        log_message += f"📊 Статус: {status_text}\n"
        log_message += f"⏰ {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        
        await types.Bot.get_current().send_message(Config.LOG_MODERATION_CHANNEL, log_message)
        logger.info(f"Moderation log: {status_text} by @{moderator_username} for message {message_id}")
    except Exception as e:
        logger.error(f"Failed to send moderation log: {e}")

@error_handler
async def send_punishment_log(moderator_username: str, moderator_id: int, target_username: str, target_id: int, punishment_type: str, reason: str):
    try:
        log_message = f"⚖️ 🎯 Наказание выдано\n\n"
        log_message += f"Модератор: @{moderator_username}\n"
        log_message += f"ID наказавшего: {moderator_id}\n"
        log_message += f"ID наказанного: {target_id}\n"
        log_message += f"Вид нарушения: {punishment_type}\n"
        log_message += f"Причина нарушения: {reason}\n"
        log_message += f"⏰ {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        
        await types.Bot.get_current().send_message(Config.LOG_PUNISHMENT_CHANNEL, log_message)
        logger.info(f"Punishment: {punishment_type} by @{moderator_username} for {target_id}")
    except Exception as e:
        logger.error(f"Failed to send punishment log: {e}")

@error_handler
async def send_to_owner_channel(message: types.Message, message_id: int, content_type: str):
    try:
        owner_text = f"📬 Отправитель: @{message.from_user.username or 'без username'}\n\n"
        
        if content_type == "text":
            if len(message.text) > Config.MAX_MESSAGE_LENGTH:
                owner_text += f"📝 Сообщение ({len(message.text)} символов):\n"
                owner_text += f"{message.text[:200]}..."
            else:
                owner_text += f"{message.text}"
        elif content_type == "photo":
            owner_text += f"📷 Фото"
            if message.caption:
                owner_text += f"\n\n{message.caption}"
        
        msg = None
        if content_type == "text":
            msg = await message.bot.send_message(Config.OWNER_CHANNEL, owner_text)
        elif content_type == "photo":
            msg = await message.bot.send_photo(Config.OWNER_CHANNEL, message.photo[-1].file_id, caption=owner_text)
        
        return msg.message_id if msg else None
        
    except Exception as e:
        logger.error(f"Ошибка отправки в канал владельца: {e}")
        return None

@error_handler
async def update_owner_channel_message(message_id: int, approved: bool, owner_message_id: int = None):
    try:
        status_emoji = "✅" if approved else "❌"
        
        if owner_message_id:
            try:
                current_message = await types.Bot.get_current().get_message(Config.OWNER_CHANNEL, owner_message_id)
                current_text = current_message.text or current_message.caption or ""
                
                updated_text = f"{status_emoji} {current_text}"
                
                if current_message.text:
                    await types.Bot.get_current().edit_message_text(
                        chat_id=Config.OWNER_CHANNEL,
                        message_id=owner_message_id,
                        text=updated_text
                    )
                else:
                    await types.Bot.get_current().edit_message_caption(
                        chat_id=Config.OWNER_CHANNEL,
                        message_id=owner_message_id,
                        caption=updated_text
                    )
                    
            except Exception as e:
                logger.error(f"Ошибка редактирования сообщения: {e}")
                await types.Bot.get_current().send_message(
                    Config.OWNER_CHANNEL,
                    f"{status_emoji} Сообщение ID: {message_id} {'одобрено' if approved else 'отклонено'}"
                )
        else:
            await types.Bot.get_current().send_message(
                Config.OWNER_CHANNEL,
                f"{status_emoji} Сообщение ID: {message_id} {'одобрено' if approved else 'отклонено'}"
            )
        
    except Exception as e:
        logger.error(f"Ошибка обновления канала владельца: {e}")

@error_handler
async def send_to_moderator(message: types.Message, message_id: int, content_type: str):
    try:
        if not await check_command_access(message):
            return
        
        if not can_send_message(message.from_user.id):
            await message.answer("❌ Слишком много сообщений. Подождите немного.", reply_markup=get_cancel_keyboard())
            return
        
        moderators = [uid for uid, level in user_levels.items() if level >= 1]
        
        if not moderators:
            await message.answer("❌ Нет активных модераторов для проверки")
            return
        
        success = False
        for moderator_id in moderators:
            try:
                if content_type == "text":
                    if len(message.text) > Config.MAX_MESSAGE_LENGTH:
                        mod_text = f"📨 Сообщение для модерации ({len(message.text)} символов):\n\n"
                        mod_text += f"{message.text[:500]}..."
                    else:
                        mod_text = f"📨 Сообщение для модерации:\n\n{message.text}"
                    
                    await message.bot.send_message(
                        moderator_id, 
                        mod_text,
                        reply_markup=create_moderation_keyboard(message_id)
                    )
                    success = True
                
                elif content_type == "photo":
                    await message.bot.send_photo(
                        moderator_id, 
                        message.photo[-1].file_id,
                        caption=message.caption or "",
                        reply_markup=create_moderation_keyboard(message_id)
                    )
                    success = True
                    
            except Exception as e:
                logger.warning(f"Не удалось отправить модератору {moderator_id}: {e}")
        
        if not success:
            await message.answer("❌ Не удалось отправить сообщение на модерацию. Попробуйте позже.", reply_markup=get_cancel_keyboard())
            return
        
        user_level = get_user_level(message.from_user.id)
        if user_level == 0:
            owner_message_id = await send_to_owner_channel(message, message_id, content_type)
            message_data = get_message(message_id)
            if message_data and owner_message_id:
                message_data['owner_message_id'] = owner_message_id
        
        await message.answer("✅ Ваше сообщение отправлено на модерацию. Ожидайте решения!", reply_markup=types.ReplyKeyboardRemove())
        
    except Exception as e:
        logger.error(f"Ошибка отправки модератору: {e}")
        await message.answer("❌ Произошла ошибка. Попробуйте позже.", reply_markup=get_cancel_keyboard())

@error_handler
async def handle_text_message(message: types.Message):
    from commands import handle_buttons
    if await handle_buttons(message):
        return
    
    if not await check_command_access(message):
        return
    
    if len(message.text) > Config.MAX_MESSAGE_LENGTH:
        await message.answer(f"❌ Сообщение слишком длинное. Максимум {Config.MAX_MESSAGE_LENGTH} символов.", reply_markup=get_cancel_keyboard())
        return
    
    user_id = message.from_user.id
    user_level = get_user_level(user_id)
    
    message_data = {
        'user_id': user_id,
        'type': 'text',
        'content': message.text,
        'username': message.from_user.username,
        'level': user_level
    }
    
    message_id = add_message(message_data)
    await send_to_moderator(message, message_id, "text")

@error_handler
async def handle_photo_message(message: types.Message):
    from commands import handle_buttons
    if await handle_buttons(message):
        return
    
    if not await check_command_access(message):
        return
    
    user_id = message.from_user.id
    user_level = get_user_level(user_id)
    
    message_data = {
        'user_id': user_id,
        'type': 'photo',
        'file_id': message.photo[-1].file_id,
        'caption': message.caption,
        'username': message.from_user.username,
        'level': user_level
    }
    
    message_id = add_message(message_data)
    await send_to_moderator(message, message_id, "photo")

@error_handler
async def handle_video_message(message: types.Message):
    from commands import handle_buttons
    if await handle_buttons(message):
        return
    
    if not await check_command_access(message):
        return
    
    user_id = message.from_user.id
    user_level = get_user_level(user_id)
    
    message_data = {
        'user_id': user_id,
        'type': 'video',
        'file_id': message.video.file_id,
        'caption': message.caption,
        'username': message.from_user.username,
        'level': user_level
    }
    
    message_id = add_message(message_data)
    await send_to_moderator(message, message_id, "video")

@error_handler
async def handle_voice_message(message: types.Message):
    from commands import handle_buttons
    if await handle_buttons(message):
        return
    
    if not await check_command_access(message):
        return
    
    user_id = message.from_user.id
    user_level = get_user_level(user_id)
    
    message_data = {
        'user_id': user_id,
        'type': 'voice',
        'file_id': message.voice.file_id,
        'username': message.from_user.username,
        'level': user_level
    }
    
    message_id = add_message(message_data)
    await send_to_moderator(message, message_id, "voice")

@error_handler
async def handle_video_note_message(message: types.Message):
    from commands import handle_buttons
    if await handle_buttons(message):
        return
    
    if not await check_command_access(message):
        return
    
    user_id = message.from_user.id
    user_level = get_user_level(user_id)
    
    message_data = {
        'user_id': user_id,
        'type': 'video_note',
        'file_id': message.video_note.file_id,
        'username': message.from_user.username,
        'level': user_level
    }
    
    message_id = add_message(message_data)
    await send_to_moderator(message, message_id, "video_note")

@error_handler
async def handle_sticker_message(message: types.Message):
    from commands import handle_buttons
    if await handle_buttons(message):
        return
    
    if not await check_command_access(message):
        return
    
    user_id = message.from_user.id
    user_level = get_user_level(user_id)
    
    message_data = {
        'user_id': user_id,
        'type': 'sticker',
        'file_id': message.sticker.file_id,
        'emoji': message.sticker.emoji,
        'username': message.from_user.username,
        'level': user_level
    }
    
    message_id = add_message(message_data)
    await send_to_moderator(message, message_id, "sticker")

@error_handler
async def handle_document_message(message: types.Message):
    from commands import handle_buttons
    if await handle_buttons(message):
        return
    
    if not await check_command_access(message):
        return
    
    user_id = message.from_user.id
    user_level = get_user_level(user_id)
    
    message_data = {
        'user_id': user_id,
        'type': 'document',
        'file_id': message.document.file_id,
        'caption': message.caption,
        'filename': message.document.file_name,
        'username': message.from_user.username,
        'level': user_level
    }
    
    message_id = add_message(message_data)
    await send_to_moderator(message, message_id, "document")

@error_handler
async def handle_moderation(callback: types.CallbackQuery):
    try:
        action, message_id = callback.data.split("_")
        message_id = int(message_id)
        
        message_data = get_message(message_id)
        if not message_data:
            await callback.answer("Сообщение уже обработано или не найдено")
            return
        
        moderator_id = callback.from_user.id
        moderator_level = get_user_level(moderator_id)
        moderator_username = callback.from_user.username or "неизвестно"
        
        if message_data['user_id'] == moderator_id:
            await callback.answer("❌ Вы не можете проверять свои сообщения")
            return
        
        if moderator_level < 1:
            await callback.answer("❌ У вас нет прав для модерации")
            return
        
        approved = action == "approve"
        moderation_time = 0  # Можно добавить расчет времени
        
        if approved:
            try:
                if message_data['type'] == 'text':
                    await callback.bot.send_message(
                        Config.CHANNEL_ID,
                        f"📨 Анонимное сообщение:\n\n{message_data['content']}"
                    )
                elif message_data['type'] == 'photo':
                    await callback.bot.send_photo(
                        Config.CHANNEL_ID,
                        message_data['file_id'],
                        caption=message_data.get('caption', '📨 Анонимное фото')
                    )
                
                update_moderator_stats(moderator_id, 'approve', moderation_time)
                message_content = message_data['content'] if message_data['type'] == 'text' else f"{message_data['type']} сообщение"
                await send_moderation_log(
                    moderator_username, moderator_id, message_content, 
                    message_id, message_data.get('username', 'без username'), True
                )
                
            except Exception as e:
                logger.error(f"Ошибка публикации: {e}")
                await callback.answer("Ошибка публикации")
                return
        else:
            update_moderator_stats(moderator_id, 'reject', moderation_time)
            message_content = message_data['content'] if message_data['type'] == 'text' else f"{message_data['type']} сообщение"
            await send_moderation_log(
                moderator_username, moderator_id, message_content,
                message_id, message_data.get('username', 'без username'), False
            )
        
        if message_data.get('level', 0) == 0:
            owner_message_id = message_data.get('owner_message_id')
            await update_owner_channel_message(message_id, approved, owner_message_id)
        
        from commands import get_start_keyboard
        status_text = "✅ Ваше сообщение прошло модерацию и опубликовано в канале!" if approved else "❌ Ваше сообщение не прошло модерацию и было отклонено."
        
        try:
            await callback.bot.send_message(
                message_data['user_id'],
                status_text,
                reply_markup=get_start_keyboard()
            )
        except Exception as e:
            logger.warning(f"Не удалось уведомить пользователя {message_data['user_id']}: {e}")
        
        update_message_status(message_id, approved, moderation_time)
        delete_message(message_id)
        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except:
            pass
        
        await callback.answer("Сообщение опубликовано" if approved else "Сообщение отклонено")
        
    except Exception as e:
        logger.error(f"Ошибка обработки модерации: {e}")
        await callback.answer("Произошла ошибка")

@error_handler
async def handle_punishment_callback(callback: types.CallbackQuery, state: FSMContext):
    try:
        action, target_id = callback.data.split("_")
        target_id = int(target_id)
        
        moderator_id = callback.from_user.id
        moderator_level = get_user_level(moderator_id)
        
        if moderator_level < 2:
            await callback.answer("❌ У вас нет прав для выдачи наказаний")
            return
        
        await state.update_data({
            'punishment_type': action,
            'target_id': target_id,
            'moderator_id': moderator_id
        })
        
        await callback.message.answer("📝 Укажите причину наказания:")
        await state.set_state(PunishmentStates.waiting_for_reason)
        await c
