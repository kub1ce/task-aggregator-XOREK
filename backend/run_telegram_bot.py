# backend/run_telegram_bot.py
import os
import logging
from pyrogram import Client, filters
from dotenv import load_dotenv
# ИМПОРТИРУЕМ из database.py, где уже определён DB_PATH и функции
from database import init_db, save_message_to_db, Notification
from services.notification_processor import calculate_importance
from ai_response import generate_ai_response

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

load_dotenv()

API_ID = int(os.getenv("TELEGRAM_API_ID"))
API_HASH = os.getenv("TELEGRAM_API_HASH")
SESSION_NAME = os.getenv("SESSION_NAME", "my_session")
TARGET_CHAT_ID = int(os.getenv("TARGET_CHAT_ID", 0))

app = Client(SESSION_NAME, api_id=API_ID, api_hash=API_HASH)

@app.on_message(filters.private)
async def handle_private_message(client, message):
    if not message.from_user:
        return

    # --- КОНВЕРТАЦИЯ Pyrogram Message в нашу модель Notification (как в telegram_wrapper) ---
    from_user = message.from_user
    chat = message.chat

    first_name = from_user.first_name or ""
    last_name = from_user.last_name or ""
    full_name = f"{first_name} {last_name}".strip()

    if chat.title:
        chat_title = chat.title
    elif chat.first_name:
        chat_title = f"{chat.first_name} {chat.last_name or ''}".strip()
    else:
        chat_title = str(chat.id)

    text_content = message.text or message.caption or ""
    media_type = None
    if message.photo: media_type = "photo"
    elif message.document: media_type = "document"
    elif message.video: media_type = "video"
    elif message.voice: media_type = "voice"
    elif message.audio: media_type = "audio"
    elif message.sticker: media_type = "sticker"
    elif message.animation: media_type = "animation"

    msg_date = message.date.isoformat()

    notification = Notification(
        source='telegram',
        from_user_id=from_user.id,
        from_name=full_name,
        chat_id=chat.id,
        chat_title=chat_title,
        text_content=text_content,
        media_type=media_type,
        date=msg_date,
        message_id=str(message.id),
        raw_message=str(message)[:1000]
    )

    notification.importance = calculate_importance(notification)
    notification.status = 'unread'
    # --- КОНЕЦ КОНВЕРТАЦИИ ---

    # --- СОХРАНЕНИЕ ---
    notification_id = save_message_to_db(notification)
    if notification_id:
        logger.info(f"✅ Уведомление от {notification.from_name} (TG) сохранено в БД с ID {notification_id}")
        # Обработка ИИ ответа (только если сообщение не пустое)
        if text_content.strip():
            logger.info(f"Сообщение от {notification.from_user_id}: {text_content}")
            if notification.from_user_id == TARGET_CHAT_ID or notification.chat_id == TARGET_CHAT_ID: # Проверяем TARGET_CHAT_ID
                logger.info("Генерация ответа через ИИ...")
                ai_reply = generate_ai_response(notification.from_user_id, text_content)
                if ai_reply:
                    logger.info(f"Предложенный ответ: {ai_reply}")
                    # Отправка отключена пока
                    # await client.send_message(message.chat.id, f"{ai_reply}")
                else:
                    logger.error("Не удалось сгенерировать ответ.")
    else:
        logger.error(f"❌ Ошибка при сохранении уведомления от TG от {from_user.id}")

if __name__ == "__main__":
    # init_db() теперь использует DB_PATH из database.py и создаёт папку
    # init_db()
    logger.info("🤖 Запуск Telegram бота...")
    print("Запуск Telegram бота...")
    print("Telegram: включён")
    app.run()
