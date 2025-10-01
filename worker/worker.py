import os
import asyncio
import redis
from rq import Worker, Queue, Connection
from aiogram import Bot
from aiogram.exceptions import TelegramRetryAfter, TelegramBadRequest

# Настройки ограничений Telegram
MAX_MESSAGES_PER_SECOND = 25
DELAY_BETWEEN_MESSAGES = 1.0 / MAX_MESSAGES_PER_SECOND


class TelegramSender:
    def __init__(self):
        self.bot = Bot(token=os.getenv('BOT_TOKEN'))

    async def send_message(self, user_id: int, message: str):
        """Отправка сообщения с обработкой ограничений"""
        try:
            await self.bot.send_message(chat_id=user_id, text=message)
            print(f"✅ Message sent to user {user_id}")
            return True

        except TelegramRetryAfter as e:
            # Превышены лимиты - ждем указанное время
            wait_time = e.retry_after
            print(f"⏳ Rate limit hit, waiting {wait_time} seconds")
            await asyncio.sleep(wait_time)
            # Пробуем снова
            return await self.send_message(user_id, message)

        except TelegramBadRequest as e:
            # Неверный chat_id или пользователь заблокировал бота
            print(f"❌ Failed to send to {user_id}: {e}")
            return False

        except Exception as e:
            print(f"⚠️ Unexpected error for user {user_id}: {e}")
            return False

    async def close(self):
        await self.bot.session.close()


def send_telegram_message(user_id: int, message: str):
    """
    Синхронная обертка для асинхронной отправки сообщения
    Эта функция вызывается RQ Worker
    """
    sender = TelegramSender()

    try:
        # Создаем и запускаем асинхронную функцию
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    try:
        # Добавляем задержку между сообщениями
        result = loop.run_until_complete(
            asyncio.gather(
                asyncio.sleep(DELAY_BETWEEN_MESSAGES),
                sender.send_message(user_id, message)
            )
        )
        return result[1]  # возвращаем результат отправки
    finally:
        loop.run_until_complete(sender.close())


if __name__ == "__main__":
    print("🚀 Starting RQ Worker for Telegram messages...")

    # Подключение к Redis
    redis_conn = redis.Redis(
        host=os.getenv('REDIS_HOST', 'redis'),
        port=int(os.getenv('REDIS_PORT', 6379)),
        db=0
    )

    # Запуск воркера
    with Connection(redis_conn):
        worker = Worker(['telegram_messages'])
        print("✅ Worker started. Listening for messages...")
        worker.work()