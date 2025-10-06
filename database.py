import sqlite3
from datetime import datetime

DB_PATH = "./database/messages.db"

def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                from_user_id INTEGER,
                from_user_name TEXT,
                chat_id INTEGER,
                chat_title TEXT,
                text_content TEXT,
                media_type TEXT,
                date TEXT,
                message_id INTEGER,
                raw_message TEXT
            )
        """)
        conn.commit()

def save_message_to_db(msg):
    try:
        from_user = msg.from_user
        chat = msg.chat

        if not from_user:
            return

        first_name = from_user.first_name or ""
        last_name = from_user.last_name or ""
        full_name = f"{first_name} {last_name}".strip()

        if chat.title:
            chat_title = chat.title
        elif chat.first_name:
            chat_title = f"{chat.first_name} {chat.last_name or ''}".strip()
        else:
            chat_title = str(chat.id)

        text_content = msg.text or msg.caption or ""

        media_type = None
        if msg.photo: media_type = "photo"
        elif msg.document: media_type = "document"
        elif msg.video: media_type = "video"
        elif msg.voice: media_type = "voice"
        elif msg.audio: media_type = "audio"
        elif msg.sticker: media_type = "sticker"
        elif msg.animation: media_type = "animation"

        msg_date = msg.date.isoformat()

        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO messages (
                    from_user_id, from_user_name, chat_id, chat_title,
                    text_content, media_type, date, message_id, raw_message
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                from_user.id,
                full_name,
                chat.id,
                chat_title,
                text_content,
                media_type,
                msg_date,
                msg.id,
                str(msg)[:1000]
            ))
            conn.commit()

        return {
            "from_user_id": from_user.id,
            "full_name": full_name,
            "chat_id": chat.id,
            "text_content": text_content,
            "username": getattr(from_user, "username", None)
        }

    except Exception as e:
        print(f"save_message_to_db error: {e}")
        return None

def get_chat_history(user_id, limit=8):
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
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
        return list(reversed(rows))