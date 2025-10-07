from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)


@app.route('/api/notifications', methods=['GET'])
def get_all_notifications():
    """Получить список уведомлений."""
    limit = int(request.args.get('limit', 50))
    offset = int(request.args.get('offset', 0))
    status = request.args.get('status', 'unread')
    importance = request.args.get('importance', None)

    notifications = get_notifications(limit=limit, offset=offset, status=status, importance=importance)
    return jsonify([n.to_dict() for n in notifications])

