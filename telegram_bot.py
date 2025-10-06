
import os
from pyrogram import Client, filters
from dotenv import load_dotenv
from database import init_db, save_message_to_db
from ai_response import generate_ai_response

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

    msg_info = save_message_to_db(message)
    if not msg_info:
        return

    text_content = message.text or message.caption or ""
    if not text_content.strip():
        return

    print(f"Сообщение от {msg_info['chat_id']}: {text_content}")

    if message.chat.id == TARGET_CHAT_ID:
        print("Генерация ответа через ИИ...")
        ai_reply = generate_ai_response(message.from_user.id, text_content)
        if ai_reply:
            print(f"Предложенный ответ: {ai_reply}")
            # Отправка отключена пока
            # await client.send_message(message.chat.id, f"{ai_reply}")
        else:
            print("Не удалось сгенерировать ответ.")