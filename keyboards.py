from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton

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