""""""

from dataclasses import dataclass


# backend/models.py
@dataclass
class Notification:
    id: int = None # будет присвоен при вставке
    source: str = ""
    from_user_id: int = None
    from_email: str = None
    from_name: str = ""
    chat_id: int = None
    chat_title: str = ""
    text_content: str = ""
    media_type: str = None
    date: str = None # или datetime, если удобнее
    message_id: str = None
    raw_message: str = None
    importance: str = "medium" # "low", "medium", "high", "critical"
    status: str = "unread" # "unread", "read", "archived", "delayed"
