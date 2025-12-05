import redis
from rq import Queue
import os

# Подключение к Redis
redis_conn = redis.Redis(
    host=os.environ['REDIS_HOST'],
    port=int(os.environ['REDIS_PORT']),
    db=0,
    decode_responses=True
)

# Создание очереди
message_queue = Queue('telegram_messages', connection=redis_conn)