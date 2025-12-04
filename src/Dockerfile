FROM python:3.12-slim

WORKDIR /app

# Копируем зависимости сначала для кэширования
COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# Копируем исходный код
COPY . .

# Создаем не-root пользователя для безопасности
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]