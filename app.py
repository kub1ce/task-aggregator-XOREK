from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import sqlite3
import websockets
import asyncio
import json
import threading
import time
import socket
import re
from collections import Counter
from datetime import datetime


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

# === WebSocket сервер (как было) ===
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
            try:
                asyncio.run(ws.send(message))
            except Exception:
                pass

# === DB helpers ===
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

# старт websocket в треде
def run_websocket_in_thread():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(run_websocket_server())

threading.Thread(target=run_websocket_in_thread, daemon=True).start()

# === Роуты ===
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/messages', methods=['GET'])
def get_all_messages():
    limit = int(request.args.get('limit', 50))
    offset = int(request.args.get('offset', 0))
    # source фильтрация удалена — теперь это делается на клиенте мульти-выбором
    importance = request.args.get('importance')
    search = request.args.get('search', '')
    sort_order = request.args.get('sort_order', 'desc')  # 'asc' или 'desc'

    conn = get_db_connection()
    cursor = conn.cursor()

    query = "SELECT * FROM messages WHERE 1=1"
    params = []

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
    # можно расширить чтением из БД — сейчас отдаём статично, но в массиве включены все имеющиеся источники
    return jsonify([
        {"name": "Telegram", "value": "telegram"},
        {"name": "Почта", "value": "email"}
    ])

# === НОВЫЙ: аналитика ИИ (эвристический анализ, возвращает html-блок для вставки) ===
@app.route('/api/analysis', methods=['GET'])
def analysis():
    """
    Собирает последние сообщения и формирует удобный HTML-блок:
    - топ тем (чипы) — кликабельные
    - для каждой темы: краткий обзор + примеры сообщений
    - список срочных сообщений
    Возвращает JSON: { html: "...", prompt: "..." }
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, from_user_name, chat_title, text_content, importance, date, source FROM messages ORDER BY date DESC LIMIT 800")
    rows = cursor.fetchall()
    conn.close()

    messages = [dict(r) for r in rows]

    stopwords = set("""и в во не на я он она мы вы ты что это для как до через под без при же так но его её за от по или ли их о об""".split())
    word_counter = Counter()
    msg_map = []
    word_re = re.compile(r'\b[а-яА-Яa-zA-Z0-9]{3,}\b', flags=re.UNICODE)

    for m in messages:
        txt = (m.get('text_content') or '').lower()
        words = word_re.findall(txt)
        filtered = [w for w in words if w not in stopwords]
        word_counter.update(filtered)
        msg_map.append({
            'id': m['id'],
            'text': m.get('text_content') or '',
            'importance': int(m.get('importance') or 3),
            'from': m.get('from_user_name') or '',
            'date': m.get('date'),
            'source': m.get('source') or 'telegram'
        })

    top_words = [w for w,_ in word_counter.most_common(10)]
    if not top_words:
        top_words = ["(нет тем)"]

    # Создаём группы: для каждой топ-темы считаем примеры и краткий обзор
    groups = []
    for kw in top_words[:8]:
        hits = [m for m in msg_map if kw in (m['text'] or '').lower()]
        if hits:
            avg_imp = sum(h['importance'] for h in hits) / len(hits)
            # пост-обработка: собрать частые слова внутри группы (кроме ключа)
            local_counter = Counter()
            for h in hits:
                words = word_re.findall((h['text'] or '').lower())
                local_counter.update([w for w in words if w not in stopwords and w != kw])
            top_local = [w for w,_ in local_counter.most_common(3)]
            if top_local:
                summary = f"Коротко: в теме часто встречаются слова «{', '.join(top_local)}» — основные вопросы связаны с ними."
            else:
                summary = "Коротко: обсуждается тема, есть разные сообщения по смежным вопросам."
            groups.append({
                'keyword': kw,
                'count': len(hits),
                'avg_importance': round(avg_imp,2),
                'examples': hits[:3],
                'summary': summary
            })

    # Топ срочных сообщений
    urgent = sorted([m for m in msg_map if int(m['importance']) >= 4], key=lambda x: -int(x['importance']))[:8]

    # ==== Формирование HTML ====
    def safe(s):
        return (s or '').replace('<','&lt;').replace('>','&gt;')

    html_parts = []

    # Top topics (чипы) — делаем прокручиваемую плитку
    html_parts.append('<div class="analysis-block">')
    html_parts.append('<div style="font-weight:700;margin-bottom:8px">Топ тем</div>')
    html_parts.append('<div class="top-topics">')
    for g in groups:
        html_parts.append(f'<div class="kw-chip" data-keyword="{safe(g["keyword"])}" title="Нажмите, чтобы отфильтровать по теме"><strong>{safe(g["keyword"])}</strong> <span class="small-muted" style="margin-left:6px;font-size:0.85rem">({g["count"]})</span></div>')
    html_parts.append('</div>')
    html_parts.append('</div>')

    # Detailed groups: краткий обзор + примеры
    for g in groups:
        html_parts.append('<div class="analysis-block">')
        html_parts.append(f'<div style="display:flex;justify-content:space-between;align-items:center;"><div style="font-weight:700">Тема: {safe(g["keyword"])}</div><div class="small-muted">Сообщений: {g["count"]} • ср. значимость: {g["avg_importance"]}/5</div></div>')
        html_parts.append(f'<div class="small-muted" style="margin-top:6px">{safe(g["summary"])}</div>')
        html_parts.append('<div style="margin-top:10px;">')
        for ex in g['examples']:
            dstr = ''
            try:
                dstr = datetime.fromisoformat(ex['date']).strftime('%Y-%m-%d %H:%M')
            except Exception:
                dstr = (ex['date'] or '')[:16]
            html_parts.append(
                f'<div style="padding:8px;border-radius:8px;margin-bottom:6px;background:#fbfbfd;">'
                f'<div style="font-weight:600">{safe(ex["from"]) or "—"}</div>'
                f'<div style="font-size:0.92rem;margin-top:4px">{safe(ex["text"][:350])}</div>'
                f'<div class="small-muted" style="font-size:0.8rem;margin-top:6px">{dstr} • {safe(ex["source"])} • приоритет: {ex["importance"]}</div>'
                f'</div>'
            )
        html_parts.append('</div></div>')

    # urgent block
    if urgent:
        html_parts.append('<div class="analysis-block">')
        html_parts.append('<div style="font-weight:700">Срочные / важные сообщения</div>')
        html_parts.append('<div style="margin-top:8px;">')
        for u in urgent:
            dstr = ''
            try:
                dstr = datetime.fromisoformat(u['date']).strftime('%Y-%m-%d %H:%M')
            except Exception:
                dstr = (u['date'] or '')[:16]
            html_parts.append(
                f'<div style="padding:8px;border-radius:8px;margin-bottom:6px;background:linear-gradient(90deg, rgba(255,240,240,0.95), #fff);">'
                f'<div style="font-weight:600">{safe(u["from"]) or "—"}</div>'
                f'<div style="font-size:0.92rem;margin-top:4px">{safe(u["text"][:400])}</div>'
                f'<div class="small-muted" style="font-size:0.8rem;margin-top:6px">{dstr} • {safe(u["source"])} • приоритет: {u["importance"]}</div>'
                f'</div>'
            )
        html_parts.append('</div></div>')

    # prompt для LLM (на будущее) — короткая инструкция
    prompt = (
        "Проанализируй список сообщений. "
        "Выдели 5-8 основных тем и для каждой темы дай краткое резюме (1-2 предложения), "
        "укажи количество сообщений и среднюю важность. "
        "Отдельным блоком перечисли топ-8 самых срочных сообщений (importance >=4) с краткой причиной, почему они важны. "
        "Верни результат в HTML-блоках, готовых к вставке в панель справа."
    )
    html_parts.append('<div class="analysis-block small-muted" style="font-size:0.85rem">')
    html_parts.append('<div style="font-weight:600;margin-bottom:6px">Промпт (для LLM)</div>')
    html_parts.append(f'<div style="white-space:pre-wrap">{safe(prompt)}</div>')
    html_parts.append('</div>')

    html = "\n".join(html_parts)
    return jsonify({'html': html, 'prompt': prompt})

def _simple_summarize_text(full_text, max_sentences=3):
    """
    Простая экстрактивная сводка:
    - разбиваем на предложения,
    - считаем частоты слов (без стоп-слов),
    - оцениваем предложение как сумму частот слов,
    - возвращаем top-N предложений в исходном порядке.
    """
    if not full_text or len(full_text) < 120:
        return full_text.strip()

    # разбивка на предложения (очень простая)
    sents = re.split(r'(?<=[.!?])\s+', full_text.strip())
    if len(sents) <= max_sentences:
        return " ".join(sents).strip()

    # базовые стоп-слова (рус/eng)
    stopwords = set("""и в во не на я он она мы вы ты что это для как до через под без при же так но его её за от по или ли их о об the a an and or to of in on is are""".split())

    word_re = re.compile(r'\b[а-яА-Яa-zA-Z0-9]{3,}\b', flags=re.UNICODE)
    words = word_re.findall(full_text.lower())
    words = [w for w in words if w not in stopwords]
    if not words:
        # fallback: return first max_sentences sentences
        return " ".join(sents[:max_sentences]).strip()

    freqs = Counter(words)
    # score each sentence
    sent_scores = []
    for i, sent in enumerate(sents):
        ws = word_re.findall(sent.lower())
        score = sum(freqs.get(w, 0) for w in ws)
        sent_scores.append((i, score, sent.strip()))

    # pick top sentences by score
    top = sorted(sent_scores, key=lambda x: x[1], reverse=True)[:max_sentences]
    top_idx = sorted([t[0] for t in top])
    summary = " ".join([sents[i].strip() for i in top_idx])
    return summary.strip()

@app.route('/api/grouped_messages', methods=['GET'])
def get_grouped_messages():
    conn = get_db_connection()
    cur = conn.cursor()

    # Получаем предварительно посчитанные сводки
    cur.execute("SELECT chat_id, chat_title, is_group, summary, ai_reply, priority, total_messages, total_chars, last_updated FROM chat_summaries")
    rows = cur.fetchall()
    summaries = {r['chat_id']: dict(r) for r in rows}

    # Получаем последние сообщения по всем чатам
    cur.execute("SELECT id, from_user_id, from_user_name, chat_id, chat_title, text_content, importance, date, source, ai_reply FROM messages ORDER BY date ASC")
    rows = cur.fetchall()
    conn.close()
    msgs = [dict(r) for r in rows]

    groups = {}
    for m in msgs:
        if m.get('chat_title'):
            key = f"group::{m.get('chat_id')}"
            title = m.get('chat_title')
            is_group = True
        else:
            uid = m.get('from_user_id') or m.get('chat_id') or (m.get('from_user_name') or 'private')
            key = f"private::{uid}"
            title = m.get('from_user_name') or f"Пользователь {uid}"
            is_group = False

        if key not in groups:
            groups[key] = {"group_key": key, "chat_id": m.get('chat_id') or m.get('from_user_id'), "chat_title": title, "is_group": is_group, "messages": []}
        groups[key]['messages'].append({
            "id": m.get('id'),
            "from_user_id": m.get('from_user_id'),
            "from_user_name": m.get('from_user_name'),
            "text_content": m.get('text_content'),
            "importance": m.get('importance'),
            "date": m.get('date'),
            "source": m.get('source'),
            "ai_reply": m.get('ai_reply') or ''
        })

    result = []
    for gk, g in groups.items():
        chat_id = str(g.get('chat_id') or '')
        summary_row = summaries.get(chat_id) or {}
        # if summary not found, fallback to inline computation (optional)
        summary = summary_row.get('summary') or ''
        ai_reply = summary_row.get('ai_reply') or ''
        priority = int(summary_row.get('priority') or (max((m['importance'] for m in g['messages']), default=3)))

        total_messages = len(g['messages'])
        total_chars = sum(len(m.get('text_content') or '') for m in g['messages'])
        collapsed = True if total_chars > 800 or total_messages > 6 else False

        result.append({
            "group_key": gk,
            "chat_id": chat_id,
            "chat_title": g.get('chat_title'),
            "is_group": g.get('is_group'),
            "messages": g['messages'],
            "summary": summary,
            "ai_reply": ai_reply,
            "priority": priority,
            "collapsed": collapsed,
            "total_messages": total_messages,
            "total_chars": total_chars
        })

    # сортируем: по приоритету, затем по времени последнего сообщения (новые сверху)
    def group_sort_key(item):
        last_date = item['messages'][-1].get('date') if item['messages'] else None
        ts = 0
        if last_date:
            try:
                ts = datetime.fromisoformat(last_date).timestamp()
            except:
                try:
                    ts = float(last_date)
                except:
                    ts = 0
        return (-int(item['priority']), -int(ts or 0))

    result_sorted = sorted(result, key=group_sort_key)
    return jsonify(result_sorted)


if __name__ == '__main__':
    init_db()
    print("Запуск приложения на Flask...")
    app.run(debug=True)
