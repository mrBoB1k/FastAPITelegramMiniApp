import redis
from rq import Queue
import os

# Подключение к Redis
redis_conn = redis.Redis(
    host=os.getenv('REDIS_HOST', 'redis'),
    port=int(os.getenv('REDIS_PORT', 6379)),
    db=0,
    decode_responses=True
)

# Создание очереди
message_queue = Queue('telegram_messages', connection=redis_conn)