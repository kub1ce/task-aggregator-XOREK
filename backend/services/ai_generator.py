# backend/services/ai_generator.py

from ai_response import generate_ai_response as _generate_ai_response

def generate_ai_response(user_id_or_email, message_text):
    """
    Обертка для вашей функции генерации ИИ-ответа.
    Здесь можно добавить логику кэширования, логирования, обработки ошибок и т.д.
    """
    return _generate_ai_response(user_id_or_email, message_text)
