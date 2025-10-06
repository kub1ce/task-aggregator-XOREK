import sqlite3
from datetime import datetime
from models import Notification # Импортируем нашу модель

DB_PATH = "./database/messages.db"

def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT NOT NULL,
                from_user_id INTEGER,
                from_email TEXT,
                from_name TEXT,
                chat_id INTEGER,
                chat_title TEXT,
                text_content TEXT,
                media_type TEXT,
                date TEXT,
                message_id TEXT,
                raw_message TEXT,
                importance TEXT DEFAULT 'medium', -- Добавляем поле важности
                status TEXT DEFAULT 'unread'      -- Добавляем поле статуса
            )
        """)
        conn.commit()

def save_message_to_db(notification: Notification):
    """Сохраняет уведомление в БД. Возвращает ID нового уведомления."""
    try:
        with sqlite3.connect(DB_PATH) as conn:
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
        return None

def get_notifications(limit=50, offset=0, status='unread', importance=None):
    """Получает список уведомлений с фильтрацией."""
    with sqlite3.connect(DB_PATH) as conn:
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
    with sqlite3.connect(DB_PATH) as conn:
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
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE messages SET status = ? WHERE id = ?", (new_status, notification_id))
        conn.commit()
        return cursor.rowcount > 0 # Возвращаем True, если обновление прошло успешно

# Остальные функции, если нужны, можно адаптировать аналогично.
# Например, get_chat_history можно оставить, но, возможно, потребуется адаптировать под новую структуру или вынести в отдельный сервис.
