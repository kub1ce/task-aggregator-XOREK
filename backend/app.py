# FASTAPI

from flask import Flask, request, jsonify
from flask_cors import CORS
import os
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

# Импорты из нашего проекта
from database import init_db, get_notifications, get_notification_by_id, update_notification_status
from services.notification_processor import calculate_importance # Пока пустой, создадим позже
from services.ai_generator import generate_ai_response # Используем вашу функцию

app = Flask(__name__)
CORS(app) # Позволяем запросы с фронтенда (если он на другом порту)

# Инициализация БД при старте API
init_db()

@app.route('/api/notifications', methods=['GET'])
def get_all_notifications():
    """Получить список уведомлений."""
    limit = int(request.args.get('limit', 50))
    offset = int(request.args.get('offset', 0))
    status = request.args.get('status', 'unread') # По умолчанию только непрочитанные
    importance = request.args.get('importance', None) # Фильтр по важности (опционально)

    notifications = get_notifications(limit=limit, offset=offset, status=status, importance=importance)
    return jsonify([n.to_dict() for n in notifications])

@app.route('/api/notifications/<int:notification_id>', methods=['GET'])
def get_single_notification(notification_id):
    """Получить конкретное уведомление."""
    notification = get_notification_by_id(notification_id)
    if notification:
        return jsonify(notification.to_dict())
    else:
        return jsonify({"error": "Notification not found"}), 404

@app.route('/api/notifications/<int:notification_id>', methods=['PUT'])
def update_notification(notification_id):
    """Обновить статус уведомления."""
    data = request.get_json()
    new_status = data.get('status')

    if new_status not in ['unread', 'read', 'archived', 'delayed']:
        return jsonify({"error": "Invalid status"}), 400

    success = update_notification_status(notification_id, new_status)
    if success:
        return jsonify({"message": "Notification updated successfully"})
    else:
        return jsonify({"error": "Notification not found"}), 404

# Эндпоинт для генерации ИИ-ответа (пока только для уведомлений с текстом)
@app.route('/api/generate_ai_response/<int:notification_id>', methods=['POST'])
def generate_response(notification_id):
    """Сгенерировать ИИ-ответ для уведомления."""
    notification = get_notification_by_id(notification_id)
    if not notification or not notification.text_content:
        return jsonify({"error": "Notification not found or has no text content"}), 404

    ai_response = generate_ai_response(notification.from_user_id or notification.from_email, notification.text_content)
    if ai_response:
        return jsonify({"response": ai_response})
    else:
        return jsonify({"error": "Failed to generate AI response"}), 500

# Эндпоинт для ручного добавления уведомления (для тестирования, например)
@app.route('/api/notifications', methods=['POST'])
def add_notification():
    """Добавить новое уведомление вручную."""
    data = request.get_json()
    source = data.get('source', 'manual')
    text_content = data.get('text_content')
    from_name = data.get('from_name', 'Manual Input')
    date = data.get('date', datetime.now().isoformat())

    if not text_content:
        return jsonify({"error": "Text content is required"}), 400

    # Создаем объект уведомления
    notification = Notification(
        source=source,
        from_name=from_name,
        text_content=text_content,
        date=date,
        # Добавьте другие поля, если нужно
    )

    # Вычисляем важность (пока просто средняя, позже улучшим)
    notification.importance = calculate_importance(notification)

    # Сохраняем
    notification_id = save_message_to_db(notification)
    if notification_id:
        notification.id = notification_id
        return jsonify(notification.to_dict()), 201
    else:
        return jsonify({"error": "Failed to save notification"}), 500


if __name__ == '__main__':
    # Запускаем API на порту 5000
    app.run(debug=True, host='0.0.0.0', port=5000)
