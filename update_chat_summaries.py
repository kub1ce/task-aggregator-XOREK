import sqlite3

DATABASE = "messages.db"

def update_chat_summaries():
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()

    # === Обновления ===
    updates = [
        {
            "chat_id": -4506481873,
            "summary": "Команда обсуждает решение хакатона и упоминает о скором дедлайне.",
            "ai_reply": "Сервис находится уже в финальной стадии разработки и тестирования. Сейчас буду записыавть видео-демонстрацию."
        },
        {
            "chat_id": -1498743463,
            "summary": "Обсуждение участия в концерте STERVELL в Москве.",
            "ai_reply": "Друзья, я тоже выдвигаюсь на концерт STERVELL в Москву 10.10 в клуб Свобода."
        },
        {
            "chat_id": -3012949936,
            "summary": "Сервис готов, загружают файлы в форму.",
            "ai_reply": "Наш сервис уже готов! Загружаем файлы в форму!"
        }
    ]

    for entry in updates:
        cursor.execute("""
            INSERT INTO chat_summaries (chat_id, summary, ai_reply)
            VALUES (?, ?, ?)
            ON CONFLICT(chat_id) DO UPDATE SET
                summary=excluded.summary,
                ai_reply=excluded.ai_reply
        """, (entry["chat_id"], entry["summary"], entry["ai_reply"]))

    conn.commit()
    conn.close()
    print("✅ Обновления в chat_summaries успешно применены.")

if __name__ == "__main__":
    update_chat_summaries()