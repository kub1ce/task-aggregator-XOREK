# backend/integrations/email_reader.py
import imaplib
import email
from email.header import decode_header
import time
import os
from datetime import datetime
from dotenv import load_dotenv
from database import save_message_to_db, Notification # Импортируем функцию сохранения и модель
from services.notification_processor import calculate_importance # Импортируем вычисление важности

load_dotenv()

EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
IMAP_SERVER = os.getenv("IMAP_SERVER", "imap.mail.com")
IMAP_PORT = int(os.getenv("IMAP_PORT", "993"))

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
        mail.select("INBOX", readonly=True)
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

                # --- НАЧАЛО: КОНВЕРТАЦИЯ Email в нашу модель Notification ---
                notification = Notification(
                    source='email',
                    from_email=from_email,
                    from_name=from_name,
                    chat_title=subject, # Тема письма
                    text_content=body,
                    date=date_iso,
                    message_id=message_id,
                    raw_message=str(msg)[:1000]
                )

                # Вычисляем важность
                notification.importance = calculate_importance(notification)
                # Статус по умолчанию 'unread'
                notification.status = 'unread'
                # --- КОНЕЦ: КОНВЕРТАЦИЯ ---

                # --- СОХРАНЕНИЕ ---
                notification_id = save_message_to_db(notification)
                if notification_id:
                    print(f"✅ Письмо от {notification.from_name} ({notification.from_email}) сохранено в БД с ID {notification_id}")
                else:
                    print(f"❌ Ошибка при сохранении письма от {from_name} ({from_email})")

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

def run_integration():
    return
    """
    Функция для запуска цикла проверки почты в отдельном потоке.
    """
    # logger.info("📧 Запуск цикла проверки Email интеграции...")
    while True:
        # try:
        fetch_unread_emails()
        # except Exception as e:
            # logger.error(f"⚠️ Ошибка в цикле email_reader: {e}")
        time.sleep(60) # Проверка каждую минуту

# Основной цикл проверки почты остается, но теперь он вызывает новую функцию сохранения
if __name__ == "__main__":
    import threading, time

    def email_worker():
        """Фоновый поток для проверки почты"""
        while True:
            try:
                fetch_unread_emails()
            except Exception as e:
                print(f"⚠️ Ошибка в email_worker: {e}")
            time.sleep(60)

    email_thread = threading.Thread(target=email_worker, daemon=True)
    email_thread.start()
    while 1: pass
