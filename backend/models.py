""""""

from datetime import datetime
from dataclasses import dataclass

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

    def to_dict(self):
        return {
            "id": self.id,
            "source": self.source,
            "from_user_id": self.from_user_id,
            "from_email": self.from_email,
            "from_name": self.from_name,
            "chat_id": self.chat_id,
            "chat_title": self.chat_title,
            "text_content": self.text_content,
            "media_type": self.media_type,
            "date": self.date,
            "message_id": self.message_id,
            "raw_message": self.raw_message,
            "importance": self.importance,
            "status": self.status
        }