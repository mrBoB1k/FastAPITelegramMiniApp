import asyncio
import json

from fastapi import APIRouter, HTTPException, UploadFile, Form, File, Depends, BackgroundTasks
from typing import Annotated

from auth.router import get_current_active_token
from auth.schemas import TokenData
from send_email import send_email_with_file

from broadcasts.repository import Repository

router = APIRouter(
    prefix="/api/broadcasts",
    tags=["/api/broadcasts"]
)


@router.post('/send')
async def post_send(
        current_token: Annotated[TokenData, Depends(get_current_active_token)],
        background_tasks: BackgroundTasks,
        interactive_id: Annotated[list[str] | str, Form(...)],
        text: str = Form(None, description="Сообщение от 0 до 4096 знаков"),
        file: UploadFile = File(default=None, description="Файл (может отсутствовать), размер до 50МБ"),
):
    # 1. Если строка
    if isinstance(interactive_id, str):
        interactive_ids = parse_string(interactive_id)

    # 2. Если список
    else:
        result = []
        for item in interactive_id:
            result.extend(parse_string(item))
        interactive_ids = result


    if not text and not file:
        raise HTTPException(status_code=400, detail="No content to send")

    if text is not None:
        if len(text) > 4096:
            raise HTTPException(status_code=409, detail="Message too long")

        if len(text) == 0:
            text = ""

    data_email = set()
    for iid in interactive_ids:
        email = await Repository.get_email_for_interactive_id(interactive_id=iid, organization_id=current_token.organization_id)
        data_email.update(email)

    data_email = list(data_email)
    if not data_email:
        raise HTTPException(404, "No recipients found")

    file_bytes= None
    filename = None
    if file:
        file_bytes = await file.read()
        filename = file.filename
        if file.size > 52428799:
            raise HTTPException(409, "File too big")

    background_tasks.add_task(
        safe_send_email,
        list_email=data_email,
        subject="Click!",
        body=text,
        file=file_bytes,
        filename=filename,
    )
    return {"status": "Сообщение отправлено"}

async def safe_send_email(
    list_email: list[str],
    subject: str,
    body: str,
    file: bytes | None = None,
    filename: str | None = None,
):
    for receiver_email in list_email:
        try:
            await asyncio.sleep(1)
            await send_email_with_file(
                receiver_email=receiver_email,
                subject=subject,
                body=body,
                file=file,
                filename=filename
            )

        except Exception as e:
            try:
                await asyncio.sleep(1)
                await send_email_with_file(
                    receiver_email=receiver_email,
                    subject=subject,
                    body=body,
                    file=file,
                    filename=filename
                )
            except Exception as e:
                print(e)

def parse_string(value: str) -> list[int]:
    value = value.strip()

    # 🔹 JSON формат: "[1,2,3]"
    if value.startswith("[") and value.endswith("]"):
        data = json.loads(value)
        return [int(x) for x in data]

    # 🔹 CSV формат: "1,2,3"
    if "," in value:
        return [int(x) for x in value.split(",") if x]

    # 🔹 одиночное значение
    return [int(value)]

    # # Подготовка данных файла
    # file_data = None
    # file_type = "document"
    # if file:
    #     if file.size > 52428799:
    #         raise HTTPException(409, "File too big")
    #
    #     file_type = await determine_file_type(file, file.size)
    #
    #     bucket = "broadcasts"
    #     ext = os.path.splitext(file.filename)[1]
    #
    #     unique = await Repository_interactive.generate_unique_filename(ext=ext[1:], bucket_name=bucket)
    #
    #     saved_file = await services.save_image_to_minio(
    #         file=await file.read(),
    #         filename=file.filename,
    #         unique_filename=unique,
    #         content_type=file.content_type,
    #         size=file.size,
    #         bucket_name=bucket
    #     )
    #
    #     await Repository.save_image(saved_file)
    #
    #     url = URL_MINIO
    #
    #     file_data = {
    #         "url": f"{url}{bucket}/{unique}",
    #         "filename": file.filename,
    #         "unique_filename": unique,
    #         "bucket_name": bucket,
    #         "content_type": file.content_type,
    #         "test_chat_id": TELEGRAM_TEST_CHAT_ID
    #     }



    # # Создаем одну задачу для всех пользователей
    # # file_type Тип файла: document, photo, video, audio
    # message_queue.enqueue(
    #     'worker.send_telegram_message',
    #     args=(data_ids, text, file_data, file_type),
    #     job_timeout=300
    # )




# @router.get("/queue/stats")
# async def get_queue_stats():
#     """Статистика очереди"""
#     return {
#         "queued": message_queue.count,
#         "failed": len(message_queue.failed_job_registry),
#         "finished": len(message_queue.finished_job_registry)
#     }

#
# async def determine_file_type(file: UploadFile, file_size: int) -> str:
#     """
#     Определяет тип файла для отправки в Telegram
#     Возвращает: 'photo', 'audio', 'video', 'document'
#     """
#     # Получаем MIME type и расширение файла
#     mime_type = file.content_type
#     filename = file.filename.lower()
#
#     # 1. Проверяем фото
#     if mime_type and mime_type.startswith('image/'):
#         if file_size > 10 * 1024 * 1024:  # 10 МБ
#             return "document"
#
#         # Проверяем допустимые форматы изображений для Telegram
#         image_extensions = ['.jpg', '.jpeg', '.png', '.webp']
#         file_extension = os.path.splitext(filename)[1]
#         if file_extension in image_extensions:
#             return "photo"
#         else:
#             return "document"
#
#     # 2. Проверяем аудио
#     elif mime_type and mime_type.startswith('audio/'):
#
#         audio_extensions = ['.mp3', '.m4a']
#         file_extension = os.path.splitext(filename)[1]
#         if file_extension in audio_extensions:
#             return "audio"
#         else:
#             return "document"
#
#     # 3. Проверяем видео
#     elif mime_type and mime_type.startswith('video/'):
#         video_extensions = ['.mp4', '.mpeg4', '.mov', '.avi']
#         file_extension = os.path.splitext(filename)[1]
#         if file_extension in video_extensions:
#             return "video"
#         else:
#             return "document"
#
#     # 4. Всё остальное - документ
#     else:
#         return "document"
