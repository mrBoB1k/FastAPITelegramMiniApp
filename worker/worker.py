import os
import asyncio
import redis
import tempfile
from rq import Worker, Queue
from aiogram import Bot
from aiogram.types import FSInputFile
from aiogram.exceptions import TelegramRetryAfter, TelegramBadRequest
import boto3


# Настройки ограничений Telegram
MAX_MESSAGES_PER_SECOND = 25
DELAY_BETWEEN_MESSAGES = 1.0 / MAX_MESSAGES_PER_SECOND


class TelegramSender:
    def __init__(self):
        self.bot = Bot(token=os.getenv('BOT_TOKEN'))
        self.file_cache = {}

        try:
            self.s3_client = boto3.client(
                service_name='s3',
                endpoint_url=os.getenv("BOTO3_ENDPOINT_URL"),
                aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
                aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY")
            )

            # Проверяем подключение
            try:
                # Пробуем получить список бакетов для проверки подключения
                self.s3_client.list_buckets()
                print("✅ S3 client (boto3) initialized successfully")
            except Exception as e:
                print(f"⚠️ S3 client created but connection test failed: {e}")
                print("Continuing anyway, connection will be tested on first use")

        except Exception as e:
            print(f"❌ Failed to initialize S3 client: {e}")
            self.s3_client = None

    async def upload_file_to_telegram(self, file_data, file_type):
        """Загружает файл в Telegram и получает file_id используя MinIO клиент"""
        cache_key = f"{file_data['unique_filename']}_{file_type}"

        # Проверяем кэш
        if cache_key in self.file_cache:
            return self.file_cache[cache_key]

        # Проверяем, что MinIO клиент инициализирован
        if not self.s3_client:
            raise Exception("MinIO client not available")

        temp_path = None
        try:
            # Скачиваем файл из MinIO используя клиент
            temp_path = f"/tmp/{file_data['filename']}"

            print(f"📥 Downloading file from MinIO: {file_data['bucket_name']}/{file_data['unique_filename']}")

            # Скачиваем объект из MinIO напрямую
            self.s3_client.download_file(
                Bucket=file_data['bucket_name'],
                Key=file_data['unique_filename'],
                Filename=temp_path
            )

            print(f"✅ File downloaded to {temp_path}")

            # Загружаем в Telegram
            if file_type == 'photo':
                result = await self.bot.send_photo(
                    chat_id=file_data['test_chat_id'],
                    photo=FSInputFile(temp_path)
                )
                file_id = result.photo[-1].file_id

            elif file_type == 'video':
                result = await self.bot.send_video(
                    chat_id=file_data['test_chat_id'],
                    video=FSInputFile(temp_path)
                )
                file_id = result.video.file_id

            elif file_type == 'audio':
                result = await self.bot.send_audio(
                    chat_id=file_data['test_chat_id'],
                    audio=FSInputFile(temp_path)
                )
                file_id = result.audio.file_id

            else:  # document
                result = await self.bot.send_document(
                    chat_id=file_data['test_chat_id'],
                    document=FSInputFile(temp_path)
                )
                file_id = result.document.file_id

            # Сохраняем в кэш
            self.file_cache[cache_key] = {
                'file_id': file_id,
                'file_type': file_type
            }

            print(f"✅ File uploaded to Telegram, file_id: {file_id}")
            return self.file_cache[cache_key]

        except Exception as e:
            print(f"❌ Failed to upload file to Telegram: {e}")
            raise
        finally:
            # Удаляем временный файл
            if temp_path and os.path.exists(temp_path):
                try:
                    os.unlink(temp_path)
                    print(f"✅ Temporary file cleaned: {temp_path}")
                except Exception as e:
                    print(f"⚠️ Failed to clean temporary file: {e}")

    async def send_content(self, telegram_id, message=None, file_info=None, file_type='document'):
        """Отправка контента с использованием file_id"""
        try:
            if file_info and message:
                # Отправка файла с подписью
                if file_type == 'photo':
                    await self.bot.send_photo(
                        chat_id=telegram_id,
                        photo=file_info['file_id'],
                    )
                    await asyncio.sleep(DELAY_BETWEEN_MESSAGES)
                    await self.bot.send_message(chat_id=telegram_id, text=message)
                elif file_type == 'video':
                    await self.bot.send_video(
                        chat_id=telegram_id,
                        video=file_info['file_id'],
                    )
                    await asyncio.sleep(DELAY_BETWEEN_MESSAGES)
                    await self.bot.send_message(chat_id=telegram_id, text=message)
                elif file_type == 'audio':
                    await self.bot.send_audio(
                        chat_id=telegram_id,
                        audio=file_info['file_id'],
                    )
                    await asyncio.sleep(DELAY_BETWEEN_MESSAGES)
                    await self.bot.send_message(chat_id=telegram_id, text=message)
                else:  # document
                    await self.bot.send_document(
                        chat_id=telegram_id,
                        document=file_info['file_id'],
                    )
                    await asyncio.sleep(DELAY_BETWEEN_MESSAGES)
                    await self.bot.send_message(chat_id=telegram_id, text=message)
                print(f"✅ File with message sent to user {telegram_id}")

            elif file_info and not message:
                # Отправка только файла
                if file_type == 'photo':
                    await self.bot.send_photo(
                        chat_id=telegram_id,
                        photo=file_info['file_id']
                    )
                elif file_type == 'video':
                    await self.bot.send_video(
                        chat_id=telegram_id,
                        video=file_info['file_id']
                    )
                elif file_type == 'audio':
                    await self.bot.send_audio(
                        chat_id=telegram_id,
                        audio=file_info['file_id']
                    )
                else:  # document
                    await self.bot.send_document(
                        chat_id=telegram_id,
                        document=file_info['file_id']
                    )
                print(f"✅ File sent to user {telegram_id}")

            elif message and not file_info:
                # Отправка только сообщения
                await self.bot.send_message(chat_id=telegram_id, text=message)
                print(f"✅ Message sent to user {telegram_id}")

            else:
                print(f"❌ No content to send to user {telegram_id}")
                return {"user_id": telegram_id, "status": "failed", "error": "No content provided"}

            return {"user_id": telegram_id, "status": "success"}

        except TelegramRetryAfter as e:
            wait_time = e.retry_after
            print(f"⏳ Rate limit hit for user {telegram_id}, waiting {wait_time} seconds")
            await asyncio.sleep(wait_time)
            return await self.send_content(telegram_id, message, file_info, file_type)

        except TelegramBadRequest as e:
            print(f"❌ Failed to send to {telegram_id}: {e}")
            return {"user_id": telegram_id, "status": "failed", "error": str(e)}

        except Exception as e:
            print(f"⚠️ Unexpected error for user {telegram_id}: {e}")
            return {"user_id": telegram_id, "status": "failed", "error": str(e)}

    async def send_bulk_content(self, telegram_ids, message=None, file_data=None, file_type='document'):
        """Массовая отправка контента с использованием file_id"""
        results = []

        # Сначала загружаем файл в Telegram (если есть)
        file_info = None
        if file_data:
            try:
                file_info = await self.upload_file_to_telegram(file_data, file_type)
            except Exception as e:
                print(f"❌ Failed to upload file, sending without file: {e}")
                # Продолжаем отправку только текста, если файл не загрузился
                if not message:
                    return [{"user_id": tid, "status": "failed", "error": "File upload failed"} for tid in telegram_ids]

        # Отправляем сообщения всем пользователям
        for i, telegram_id in enumerate(telegram_ids):
            if i > 0:
                await asyncio.sleep(DELAY_BETWEEN_MESSAGES)

            result = await self.send_content(telegram_id, message, file_info, file_type)
            results.append(result)

        return results

    async def close(self):
        await self.bot.session.close()


def send_telegram_message(telegram_ids, message=None, file_data=None, file_type='document'):
    """
    Синхронная обертка для асинхронной массовой отправки контента
    """
    sender = TelegramSender()

    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    try:
        results = loop.run_until_complete(
            sender.send_bulk_content(telegram_ids, message, file_data, file_type)
        )

        success_count = sum(1 for r in results if r["status"] == "success")
        failed_count = len(results) - success_count

        print(f"📊 Bulk send completed: {success_count} successful, {failed_count} failed")
        return {
            "total": len(results),
            "successful": success_count,
            "failed": failed_count,
            "details": results
        }
    finally:
        loop.run_until_complete(sender.close())


if __name__ == "__main__":
    print("🚀 Starting RQ Worker for Telegram bulk messages with MinIO...")

    # Подключение к Redis
    redis_conn = redis.Redis(
        host=os.getenv('REDIS_HOST', 'redis'),
        port=int(os.getenv('REDIS_PORT', 6379)),
        db=0
    )

    # Создаем и запускаем воркер с явным управлением соединением
    queue = Queue('telegram_messages', connection=redis_conn)
    worker = Worker([queue], connection=redis_conn)

    print("✅ Worker started. Listening for bulk messages...")
    worker.work()