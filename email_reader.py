import imaplib
import email
from email.header import decode_header
import time
import os
from datetime import datetime
import sqlite3
import json
from dotenv import load_dotenv

load_dotenv()

EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
IMAP_SERVER = os.getenv("IMAP_SERVER", "imap.mail.com")
IMAP_PORT = int(os.getenv("IMAP_PORT", "993"))

DATABASE = "messages.db"

def calculate_importance(notification):
    importance = 3
    if notification.from_email in ["boss@company.com", "ceo@example.com"]:
        importance = 5
    elif any(word in notification.text_content.lower() for word in ["срочно", "важно", "пожалуйста"]):
        importance = 4
    elif any(word in notification.chat_title.lower() for word in ["срочное", "важное"]):
        importance = 4
    return importance

class Notification:
    def __init__(self, source, from_email, from_name, chat_title, text_content, date, message_id, raw_message, importance=3):
        self.source = source
        self.from_email = from_email
        self.from_name = from_name
        self.chat_title = chat_title
        self.text_content = text_content
        self.date = date
        self.message_id = message_id
        self.raw_message = raw_message
        self.importance = importance
        self.status = 'unread'

def message_exists_in_db(notification):
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id FROM messages
        WHERE message_id = ? AND source = ?
    """, (notification.message_id, notification.source))
    result = cursor.fetchone()
    conn.close()
    return result is not None

def save_message_to_db(notification):
    if message_exists_in_db(notification):
        print(f"⚠️ Письмо с ID {notification.message_id} уже существует в базе.")
        return None

    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()

    display_name = f"{notification.from_name} ({notification.from_email})" if notification.from_name else notification.from_email

    cursor.execute("""
        INSERT INTO messages (
            source, from_user_name, chat_title, text_content, date, message_id, raw_message, importance
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        notification.source,
        display_name,
        notification.chat_title,
        notification.text_content,
        notification.date,
        notification.message_id,
        json.dumps(notification.raw_message),
        notification.importance
    ))
    conn.commit()
    msg_id = cursor.lastrowid
    conn.close()
    return msg_id

def decode_mime_words(s):
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
        mail.select("INBOX", readonly=True)  # readonly=True, т.к. не отмечаем как прочитанные
        status, messages = mail.search(None, 'ALL')  # Получаем все письма
        if status != 'OK':
            print("Не удалось получить список писем")
            return

        email_ids = messages[0].split()
        print(f"📬 Найдено писем: {len(email_ids)}")

        for eid in email_ids:
            try:
                status, msg_data = mail.fetch(eid, '(RFC822)')
                if status != 'OK':
                    continue
                raw_email = msg_data[0][1]
                msg = email.message_from_bytes(raw_email)

                from_header = msg.get("From", "")
                from_name, from_email = parse_email_address(from_header)

                subject = decode_mime_words(msg.get("Subject", ""))
                date_str = msg.get("Date", "")
                try:
                    email_date = email.utils.parsedate_to_datetime(date_str)
                    date_iso = email_date.isoformat()
                except:
                    date_iso = datetime.utcnow().isoformat()

                body = get_email_body(msg)
                message_id = msg.get("Message-ID", str(eid))

                notification = Notification(
                    source='email',
                    from_email=from_email,
                    from_name=from_name,
                    chat_title=subject,
                    text_content=body,
                    date=date_iso,
                    message_id=message_id,
                    raw_message=str(msg)[:1000]
                )

                notification.importance = calculate_importance(notification)
                notification_id = save_message_to_db(notification)
                if notification_id:
                    print(f"Письмо от {notification.from_name} ({notification.from_email}) сохранено в БД с ID {notification_id}")

            except Exception as e:
                print(f"❌ Ошибка при обработке письма {eid}: {e}")

        mail.close()
        mail.logout()
    except Exception as e:
        print(f"❌ Ошибка подключения к почте: {e}")

def parse_email_address(from_header):
    from_header = from_header.strip()
    if "<" in from_header and ">" in from_header:
        name_part = from_header.split("<")[0].strip()
        email_part = from_header.split("<")[1].split(">")[0]
        name = decode_mime_words(name_part)
        return name, email_part
    else:
        return "", from_header

def get_email_body(msg):
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

def main():
    while True:
        try:
            fetch_unread_emails()
        except Exception as e:
            print(f"⚠️ Ошибка в email_worker: {e}")
        time.sleep(60)

if __name__ == "__main__":
    main()