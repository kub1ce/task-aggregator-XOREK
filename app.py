from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import sqlite3
import websockets
import asyncio
import json
import threading
import time
import socket

app = Flask(__name__, template_folder='templates')
CORS(app)

DATABASE = "messages.db"

def find_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        s.listen(1)
        port = s.getsockname()[1]
    return port

WEBSOCKET_PORT = find_free_port()
print(f"WebSocket запущен на порту: {WEBSOCKET_PORT}")

# === WebSocket сервер ===
websocket_connections = set()

async def handle_websocket(websocket, path):
    websocket_connections.add(websocket)
    try:
        await websocket.wait_closed()
    finally:
        websocket_connections.discard(websocket)

async def run_websocket_server():
    server = await websockets.serve(handle_websocket, "localhost", WEBSOCKET_PORT)
    await server.wait_closed()

def start_websocket_server():
    asyncio.run(run_websocket_server())

def notify_websockets():
    print("notified")
    message = json.dumps({"action": "refresh"})
    for ws in websocket_connections.copy():
        if not ws.closed:
            asyncio.run(ws.send(message))

# === Запуск WebSocket сервера в отдельном потоке ===
def run_websocket_in_thread():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(run_websocket_server())

threading.Thread(target=run_websocket_in_thread, daemon=True).start()

def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            from_user_id INTEGER,
            from_user_name TEXT,
            chat_id INTEGER,
            chat_title TEXT,
            text_content TEXT,
            media_type TEXT,
            date TEXT,
            message_id INTEGER,
            raw_message TEXT,
            source TEXT DEFAULT 'telegram',
            importance INTEGER DEFAULT 3,
            ai_reply TEXT,
            app_name TEXT DEFAULT 'telegram',
            is_global INTEGER DEFAULT 1
        )
    """)
    conn.commit()
    conn.close()

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/messages', methods=['GET'])
def get_all_messages():
    limit = int(request.args.get('limit', 50))
    offset = int(request.args.get('offset', 0))
    source = request.args.get('source')
    importance = request.args.get('importance')
    search = request.args.get('search', '')
    sort_order = request.args.get('sort_order', 'desc')  # 'asc' или 'desc'

    conn = get_db_connection()
    cursor = conn.cursor()

    query = "SELECT * FROM messages WHERE 1=1"
    params = []

    if source:
        query += " AND source = ?"
        params.append(source)

    if importance:
        query += " AND importance = ?"
        params.append(int(importance))

    if search:
        query += " AND text_content LIKE ?"
        params.append(f"%{search}%")

    # === Сортировка ===
    order_by = "date DESC" if sort_order == 'desc' else "date ASC"
    query += f" ORDER BY {order_by} LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()

    messages = [dict(row) for row in rows]
    return jsonify(messages)

@app.route('/api/messages/<int:message_id>', methods=['DELETE'])
def delete_message(message_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM messages WHERE id = ?", (message_id,))
    conn.commit()
    conn.close()
    notify_websockets()
    return jsonify({"success": True})

@app.route('/api/sources', methods=['GET'])
def get_sources():
    return jsonify([
        {"name": "Telegram", "value": "telegram"},
        {"name": "Почта", "value": "email", "disabled": True}
    ])

if __name__ == '__main__':
    init_db()
    app.run(debug=True)