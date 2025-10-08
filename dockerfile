FROM python:3.11-slim

WORKDIR /app

# Установка зависимостей
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем код
COPY . .

# Порт для веб-интерфейса
EXPOSE 5000

# По умолчанию — ничего не запускаем (команда будет в docker-compose)
CMD ["python", "app.py"]