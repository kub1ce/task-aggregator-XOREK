from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import logging
from datetime import datetime
from dotenv import load_dotenv
from database import init_db

# Настройка логирования
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# Загружаем переменные окружения
load_dotenv()

# Импорты из нашего проекта
from database import get_notifications, get_notification_by_id, update_notification_status, save_message_to_db
from models import Notification
from services.notification_processor import calculate_importance
from services.ai_generator import generate_ai_response

# ИМПОРТ ИНТЕГРАЦИЙ - ЭТО ЗАПУСТИТ ИХ АВТОМАТИЧЕСКИ ЧЕРЕЗ __init__.py
# Это также вызовет init_db() один раз при импорте
# import integrations

app = Flask(__name__)
CORS(app)

# БД инициализируется в __init__.py интеграций
init_db() # Убираем, так как вызывается в integrations/__init__.py

@app.route('/api/notifications', methods=['GET'])
def get_all_notifications():
    """Получить список уведомлений."""
    limit = int(request.args.get('limit', 50))
    offset = int(request.args.get('offset', 0))
    status = request.args.get('status', 'unread')
    importance = request.args.get('importance', None)

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

    notification = Notification(
        source=source,
        from_name=from_name,
        text_content=text_content,
        date=date,
    )

    notification.importance = calculate_importance(notification)

    notification_id = save_message_to_db(notification)
    if notification_id:
        notification.id = notification_id
        return jsonify(notification.to_dict()), 201
    else:
        return jsonify({"error": "Failed to save notification"}), 500

# ...
if __name__ == '__main__':
    # Запускаем API на порту 5000
    # Интеграции НЕ запускаются здесь, т.к. Pyrogram отдельно
    print("🚀 API запускается на http://localhost:5000")
    # ВАЖНО: use_reloader=False, чтобы не убивать фоновые потоки при изменениях файлов
    # Но теперь Flask не запускает потоки интеграций, так что можно и debug=True, если нужно
    app.run(debug=False, host='0.0.0.0', port=5000, use_reloader=True) # Или debug=True, если нужен hot-reload для API
