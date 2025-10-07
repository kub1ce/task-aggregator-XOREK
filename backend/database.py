# backend/database.py
import sqlite3
from datetime import datetime
from models import Notification # Импортируем нашу модель
import threading # Импортируем threading
import os # Добавим импорт os

# Убедимся, что путь к БД относительный от папки backend/
# и папка database/ существует
# os.makedirs(os.path.dirname("./database/messages.db"), exist_ok=True) # Закомментим или удалим старую строку

DB_PATH = "./messages.db" # <-- ИСПРАВЛЕНО: Относительно папки, где запускается скрипт (backend/), внутри подпапки database/

# Создаём локальный объект для хранения соединения в каждом потоке
_local = threading.local()

def get_db_connection():
    """Возвращает соединение с БД для текущего потока."""
    # Проверяем, есть ли уже соединение для этого потока
    if not hasattr(_local, 'connection'):
        # Создаём папку database, если её нет (на всякий случай, хотя init_db должен это сделать)
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True) # <-- Убедимся, что папка создаётся для правильного пути
        # Создаём новое соединение для этого потока
        # check_same_thread=False позволяет использовать соединение из другого потока,
        # но мы используем threading.local, так что каждый поток имеет *своё* соединение.
        # Это безопасно, если каждый поток использует только своё соединение.
        _local.connection = sqlite3.connect(DB_PATH, check_same_thread=False, detect_types=sqlite3.PARSE_DECLTYPES)
    return _local.connection

def init_db():
    """Инициализирует структуру БД."""
    # Убедимся, что папка существует перед подключением
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True) # <-- Убедимся, что папка создаётся для правильного пути
    # Используем отдельное соединение для инициализации
    # Это может происходить в основном потоке при старте API или в run_telegram_bot.py
    conn = sqlite3.connect(DB_PATH, check_same_thread=False, detect_types=sqlite3.PARSE_DECLTYPES)
    try:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT NOT NULL,          -- 'telegram' или 'email'
                from_user_id INTEGER,          -- для Telegram
                from_email TEXT,               -- для email
                from_name TEXT,                -- имя отправителя (и для email, и для TG)
                chat_id INTEGER,               -- только для Telegram
                chat_title TEXT,               -- тема письма или название чата
                text_content TEXT,
                media_type TEXT,               -- для Telegram
                date TEXT,
                message_id TEXT,               -- для email — Message-ID, для TG — ID сообщения
                raw_message TEXT,
                importance TEXT DEFAULT 'medium', -- Важность
                status TEXT DEFAULT 'unread'      -- Статус
            )
        """)
        conn.commit()
        print("✅ Таблица messages инициализирована или уже существует.")
    except Exception as e:
        print(f"❌ Ошибка при инициализации БД: {e}")
    finally:
        conn.close()


def save_message_to_db(notification: Notification):
    """Сохраняет уведомление в БД. Возвращает ID нового уведомления."""
    try:
        # Используем соединение текущего потока
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO messages (
                source, from_user_id, from_email, from_name, chat_id, chat_title,
                text_content, media_type, date, message_id, raw_message, importance, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            notification.source, notification.from_user_id, notification.from_email,
            notification.from_name, notification.chat_id, notification.chat_title,
            notification.text_content, notification.media_type, notification.date,
            notification.message_id, notification.raw_message, notification.importance, notification.status
        ))
        conn.commit()
        return cursor.lastrowid # Возвращаем ID новой записи
    except Exception as e:
        print(f"save_message_to_db error: {e}")
        # Важно: Не вызывать conn.rollback() здесь, если conn.commit() не был вызван успешно,
        # иначе может возникнуть дополнительная ошибка. Логируем и возвращаем None.
        return None

def get_notifications(limit=50, offset=0, status='unread', importance=None):
    """Получает список уведомлений с фильтрацией."""
    conn = get_db_connection()
    cursor = conn.cursor()
    query = "SELECT * FROM messages WHERE status = ?"
    params = [status]
    if importance:
        query += " AND importance = ?"
        params.append(importance)
    query += " ORDER BY date DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    cursor.execute(query, params)
    rows = cursor.fetchall()
    columns = [description[0] for description in cursor.description]
    notifications = []
    for row in rows:
        notification_dict = dict(zip(columns, row))
        # Конвертируем в модель
        notification = Notification(**notification_dict)
        notifications.append(notification)
    return notifications

def get_notification_by_id(notification_id: int):
    """Получает уведомление по ID."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM messages WHERE id = ?", (notification_id,))
    row = cursor.fetchone()
    if row:
        columns = [description[0] for description in cursor.description]
        notification_dict = dict(zip(columns, row))
        return Notification(**notification_dict)
    return None

def update_notification_status(notification_id: int, new_status: str):
    """Обновляет статус уведомления."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE messages SET status = ? WHERE id = ?", (new_status, notification_id))
    conn.commit()
    return cursor.rowcount > 0 # Возвращаем True, если обновление прошло успешно

# Обновим get_chat_history под новую структуру и соединение
def get_chat_history(user_id, limit=8):
    """
    Получает историю чата для ИИ.
    Теперь ищет по from_user_id ИЛИ chat_id, как раньше, но использует новую структуру.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    # Ищем по from_user_id (для личных сообщений TG) или chat_id (если сообщение от бота в чате)
    # Используем source для уточнения, если нужно разделять TG и Email
    cursor.execute("""
        SELECT from_user_id, text_content, date
        FROM messages
        WHERE (from_user_id = ? OR chat_id = ?)
          AND text_content IS NOT NULL
          AND text_content != ''
        ORDER BY date DESC
        LIMIT ?
    """, (user_id, user_id, limit))
    rows = cursor.fetchall()
    # Возвращаем как кортежи (старый формат), чтобы не менять ai_response.py
    return list(reversed(rows)) # list(reversed(...)) как в оригинале

# Опционально: функция для закрытия соединения текущего потока при его завершении
def close_db_connection():
    if hasattr(_local, 'connection'):
        _local.connection.close()
        delattr(_local, 'connection')
