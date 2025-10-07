import asyncio
import threading
import time
from backend.integrations.telegram_wrapper import app
from backend.database import init_db
from backend.integrations.email_reader import fetch_unread_emails
import os
from dotenv import load_dotenv

load_dotenv()

def email_worker():
    """Фоновый поток для проверки почты"""
    while True:
        try:
            fetch_unread_emails()
        except Exception as e:
            print(f"⚠️ Ошибка в email_worker: {e}")
        time.sleep(60)  # проверка каждую минуту

if __name__ == "__main__":
    init_db()
    
    # Запуск фонового потока для почты
    email_thread = threading.Thread(target=email_worker, daemon=True)
    email_thread.start()

    print("Запуск агрегатора...")
    print("Telegram: включён")
    print("Email: проверка каждые 60 сек")
    print(f"ИИ-модель: {os.getenv('OLLAMA_MODEL')}")
    
    app.run()