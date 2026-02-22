import redis
from rq import Queue
from config import REDIS_HOST, REDIS_PORT

# Подключение к Redis
redis_conn = redis.Redis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    db=0,
    decode_responses=True
)

# Создание очереди
message_queue = Queue('telegram_messages', connection=redis_conn)