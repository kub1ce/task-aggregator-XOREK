"""AI RESPONCE"""

import requests
import os
from dotenv import load_dotenv
from database import get_chat_history

load_dotenv()

OLLAMA_MODEL = os.getenv("OLLAMA_MODEL")
OLLAMA_URL = os.getenv("OLLAMA_URL")

def generate_ai_response(user_id, new_message_text):
    try:
        history = get_chat_history(user_id, limit=8)
        context_lines = []
        for from_id, text, _ in history:
            role = "Пользователь" if from_id == user_id else "Ты"
            context_lines.append(f"{role}: {text}")
        context = "\n".join(context_lines)

        prompt = f"""Ты — умный ассистент, который помогает пользователю быстро отвечать на сообщения.
Используй дружелюбный, краткий и полезный тон. Предложи один вариант ответа.

История переписки:
{context}

Новое сообщение от пользователя: {new_message_text}

Твой ответ:"""

        payload = {
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.7,
                "num_predict": 100
            }
        }

        response = requests.post(OLLAMA_URL, json=payload, timeout=1200)
        if response.status_code == 200:
            return response.json().get("response", "").strip()
        else:
            print(f"Ollama error: {response.status_code}")
            return None
    except Exception as e:
        print(f"generate_ai_response error: {e}")
        return None