FROM python:3.11-slim

# Устанавливаем ffmpeg и зависимости
RUN apt-get update && \
    apt-get install -y ffmpeg curl && \
    rm -rf /var/lib/apt/lists/*

# Устанавливаем Python пакеты
RUN pip install --no-cache-dir flask flask-cors yt-dlp gunicorn requests


# Копируем приложение
WORKDIR /app
COPY app.py .

# Открываем порт
EXPOSE 8080

# Запускаем
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "2", "--timeout", "60", "app:app"]
