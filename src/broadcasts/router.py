from fastapi import APIRouter, HTTPException, UploadFile, Form, File
from dotenv import load_dotenv
import os

from broadcasts.schemas import SendGet, SendGet2, BroadcastRequest, InteractiveId
from broadcasts.repository import Repository
from broadcasts.redis_queue import message_queue

from interactivities.repository import Repository as Repository_interactive
import minios3.services as services

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")

router = APIRouter(
    prefix="/api/broadcasts",
    tags=["/api/broadcasts"]
)


@router.post('/send')
async def get_send(
        telegram_id: int = Form(..., description="ID пользователя Telegram"),
        interactive_id: list[int] = Form(..., description="список интерактивов"),
        text: str = Form(..., description="Сообщение от 0 до 4096 знаков"),
        file: UploadFile = File(default=None, description="Файл (может отсутствовать)")
):
    user_id = await Repository.get_user_id(telegram_id)
    if user_id is None:
        raise HTTPException(status_code=404, detail="User not found")

    if len(text) > 4096:
        raise HTTPException(status_code=409, detail="Message too long")

    if len(text) == 0:
        text = None

    data_ids = set()
    for iid in interactive_id:
        ids = await Repository.get_telegram_id_for_interactive_id(iid, user_id)
        data_ids.update(ids)

    data_ids = list(data_ids)
    if not data_ids:
        raise HTTPException(404, "No recipients found")

    # Подготовка данных файла
    file_data = None
    if file:
        if file.size > 52428799:
            raise HTTPException(409, "File too big")

        bucket = "broadcasts"
        ext = os.path.splitext(file.filename)[1]

        unique = await Repository_interactive.generate_unique_filename(ext=ext, bucket_name=bucket)

        saved_file = await services.save_image_to_minio(
            file=await file.read(),
            filename=file.filename,
            unique_filename=unique,
            content_type=file.content_type,
            size=file.size,
            bucket_name=bucket
        )

        await Repository.save_image(saved_file)

        file_data = {
            "url": f"https://carclicker.ru/{bucket}/{unique}",
            "filename": file.filename,
            "unique_filename": unique,
            "bucket_name": bucket,
            "content_type": file.content_type,
            "test_chat_id": os.getenv("TELEGRAM_TEST_CHAT_ID")
        }

    # Проверяем, что есть что отправлять
    if not text and not file_data:
        raise HTTPException(status_code=400, detail="No content to send")

    # Создаем одну задачу для всех пользователей
    # file_type Тип файла: document, photo, video, audio
    message_queue.enqueue(
        'worker.send_telegram_message',
        args=(data_ids, text, file_data, "document"),
        job_timeout=300
    )

    return {"status": "Сообщение отправлено"}


@router.get("/queue/stats")
async def get_queue_stats():
    """Статистика очереди"""
    return {
        "queued": message_queue.count,
        "failed": len(message_queue.failed_job_registry),
        "finished": len(message_queue.finished_job_registry)
    }
