
from telegram_bot import app
from database import init_db
import os
from dotenv import load_dotenv

load_dotenv()

if __name__ == "__main__":
    init_db()
    print("Запуск Telegram-клиента...")
    print("Авторизуйтесь, если это первый запуск.")
    print(f"ИИ-модель: {os.getenv('OLLAMA_MODEL')}")
    # print(f"Целевой чат ID: {os.getenv('TARGET_CHAT_ID')}")
    app.run()