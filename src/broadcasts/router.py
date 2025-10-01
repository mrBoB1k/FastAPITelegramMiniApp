from fastapi import APIRouter, HTTPException
from broadcasts.schemas import SendGet, SendGet2, BroadcastRequest
from broadcasts.repository import Repository
from broadcasts.redis_queue import message_queue
import asyncio
from dotenv import load_dotenv
import os
import httpx


load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")

router = APIRouter(
    prefix="/api/broadcasts",
    tags=["/api/broadcasts"]
)


@router.post('/send')
async def get_send(input_data: SendGet):
    user_id = await Repository.get_user_id(input_data.telegram_id)
    if user_id is None:
        raise HTTPException(status_code=404, detail="User not found")

    data_id = []
    for interactive_id_data in input_data.interactive_id:
        data = await Repository.get_user_id_for_interactive_id(interactive_id_data.id, user_id)
        data_id = list(set(data_id + data))

    request = BroadcastRequest(message= input_data.message, user_ids=data_id)

    job_ids = []
    for user_id in request.user_ids:
        job = message_queue.enqueue(
            'worker.send_telegram_message',  # Имя функции в воркере
            args=(user_id, request.message),
            job_timeout=300  # 5 минут timeout
        )
        job_ids.append(job.id)

    return {"status": "Сообщение отправлено"}

#     x = 0
#     for id in data_id:
#         x+=1
#         if x % 100 == 0:
#             await asyncio.sleep(1)
#         await send_telegram_message(input_data.text, id)
#     return {"status": "Сообщение отправлено"}
#
#
# async def send_telegram_message(text: str, telegram_id: int):
#     url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
#     params = {
#         "chat_id": telegram_id,
#         "text": text
#     }
#     async with httpx.AsyncClient() as client:
#         response = await client.post(url, params=params)
#     return response.json()

@router.get("/queue/stats")
async def get_queue_stats():
    """Статистика очереди"""
    return {
        "queued": message_queue.count,
        "failed": len(message_queue.failed_job_registry),
        "finished": len(message_queue.finished_job_registry)
    }


@router.post('/test')
async def get_send(input_data: SendGet2):
    user_id = await Repository.get_user_id(input_data.telegram_id)
    if user_id is None:
        raise HTTPException(status_code=404, detail="User not found")

    job = message_queue.enqueue(
        'worker.send_telegram_message',  # Имя функции в воркере
        args=(user_id, SendGet2.text),
        job_timeout=300  # 5 минут timeout
    )

    return {"status": "Сообщение отправлено"}