FROM python:3.11-alpine

WORKDIR /app

# Устанавливаем зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем код воркера
COPY . .

# Запускаем воркер
CMD ["python", "-m", "worker.py"]