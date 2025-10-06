# backend/services/notification_processor.py
from models import Notification

def calculate_importance(notification: Notification) -> str:
    """
    Простая логика оценки важности.
    В реальности можно использовать ИИ, ML, правила, настройки пользователя.
    """
    text = notification.text_content.lower()
    source = notification.source

    # Примеры правил
    if source == 'email':
        if 'urgent' in text or 'срочно' in text or 'важно' in text:
            return 'high'
        if 'meeting' in text or 'встреча' in text:
            return 'medium'
    elif source == 'telegram':
        # Можно добавить логику для чатов, тегов и т.д.
        if 'help' in text or 'помогите' in text:
            return 'high'

    # Если ничего не подошло, средняя важность
    return 'medium'
