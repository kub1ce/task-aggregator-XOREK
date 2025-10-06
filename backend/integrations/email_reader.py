
# ! ЗАЙТИ в настройки -> внешние сервисы -> Доступ к Почте по IMАР, РОР и SMTP + ПАРОЛЬ ДЛЯ ВНЕШНИХ ПРИЛОЖЕНИЙ
# ! ЗАЙТИ в настройки -> внешние сервисы -> Доступ к Почте по IMАР, РОР и SMTP + ПАРОЛЬ ДЛЯ ВНЕШНИХ ПРИЛОЖЕНИЙ
# ! ЗАЙТИ в настройки -> внешние сервисы -> Доступ к Почте по IMАР, РОР и SMTP + ПАРОЛЬ ДЛЯ ВНЕШНИХ ПРИЛОЖЕНИЙ

# email_reader.py
import imaplib
import email
from email.header import decode_header
import time
import os
from datetime import datetime
from dotenv import load_dotenv
from backend.database import DB_PATH
import sqlite3

load_dotenv()

EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
IMAP_SERVER = os.getenv("IMAP_SERVER", "imap.mail.com")
IMAP_PORT = int(os.getenv("IMAP_PORT", "993"))

def decode_mime_words(s):
    """Декодирует заголовки вроде =?utf-8?B?...?="""
    if s is None:
        return ""
    decoded_fragments = decode_header(s)
    parts = []
    for fragment, encoding in decoded_fragments:
        if isinstance(fragment, bytes):
            fragment = fragment.decode(encoding or 'utf-8', errors='replace')
        parts.append(fragment)
    return ''.join(parts)

def connect_to_email():
    mail = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT)
    mail.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
    return mail

def fetch_unread_emails():
    try:
        mail = connect_to_email()
        mail.select("INBOX", readonly=True)
        
        # Ищем непрочитанные письма
        status, messages = mail.search(None, 'UNSEEN')
        if status != 'OK':
            print("❌ Не удалось получить список писем")
            return

        email_ids = messages[0].split()
        print(f"📬 Найдено непрочитанных писем: {len(email_ids)}")

        for eid in email_ids:
            try:
                status, msg_data = mail.fetch(eid, '(RFC822)')
                if status != 'OK':
                    continue

                raw_email = msg_data[0][1]
                msg = email.message_from_bytes(raw_email)

                # Отправитель
                from_header = msg.get("From", "")
                from_name, from_email = parse_email_address(from_header)

                # Тема
                subject = decode_mime_words(msg.get("Subject", ""))

                # Дата
                date_str = msg.get("Date", "")
                try:
                    email_date = email.utils.parsedate_to_datetime(date_str)
                    date_iso = email_date.isoformat()
                except:
                    date_iso = datetime.utcnow().isoformat()

                # Тело письма
                body = get_email_body(msg)

                # Message-ID
                message_id = msg.get("Message-ID", str(eid))

                # Сохраняем в БД
                save_email_to_db({
                    "from_email": from_email,
                    "from_name": from_name,
                    "subject": subject,
                    "body": body,
                    "date": date_iso,
                    "message_id": message_id,
                    "raw": str(msg)[:1000]
                })

                print(f"✅ Сохранено письмо от {from_name} ({from_email}): {subject[:50]}...")

            except Exception as e:
                print(f"❌ Ошибка при обработке письма {eid}: {e}")

        mail.close()
        mail.logout()

    except Exception as e:
        print(f"❌ Ошибка подключения к почте: {e}")

def parse_email_address(from_header):
    """Преобразует 'Имя <email@example.com>' → ('Имя', 'email@example.com')"""
    from_header = from_header.strip()
    if "<" in from_header and ">" in from_header:
        name_part = from_header.split("<")[0].strip()
        email_part = from_header.split("<")[1].split(">")[0]
        name = decode_mime_words(name_part)
        return name, email_part
    else:
        return "", from_header

def get_email_body(msg):
    """Извлекает текстовое тело письма (игнорирует HTML)"""
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            content_disposition = str(part.get("Content-Disposition"))
            if "attachment" not in content_disposition and content_type == "text/plain":
                try:
                    return part.get_payload(decode=True).decode('utf-8', errors='replace')
                except:
                    return str(part.get_payload())[:500]
    else:
        if msg.get_content_type() == "text/plain":
            try:
                return msg.get_payload(decode=True).decode('utf-8', errors='replace')
            except:
                return str(msg.get_payload())[:500]
    return ""

def save_email_to_db(data):
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        
        # Проверяем, не сохраняли ли уже это письмо
        cursor.execute("SELECT 1 FROM messages WHERE message_id = ? AND source = 'email'", (data["message_id"],))
        if cursor.fetchone():
            return  # уже есть

        cursor.execute("""
            INSERT INTO messages (
                source, from_email, from_name, chat_title,
                text_content, date, message_id, raw_message
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            "email",
            data["from_email"],
            data["from_name"],
            data["subject"],
            data["body"],
            data["date"],
            data["message_id"],
            data["raw"]
        ))
        conn.commit()

if __name__ == "__main__":

    import threading, time

    def email_worker():
        """Фоновый поток для проверки почты"""
        while True:
            try:
                fetch_unread_emails()
            except Exception as e:
                print(f"⚠️ Ошибка в email_worker: {e}")
            time.sleep(60)  # проверка каждую минуту

    # Запуск фонового потока для почты
    email_thread = threading.Thread(target=email_worker, daemon=True)
    email_thread.start()

    while 1: pass