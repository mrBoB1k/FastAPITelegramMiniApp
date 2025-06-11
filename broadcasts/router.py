from fastapi import APIRouter, Depends, HTTPException, status
from broadcasts.schemas import SendGet
from typing import Annotated
from broadcasts.repository import Repository
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

    x = 0
    for id in data_id:
        x+=1
        if x % 100 == 0:
            await asyncio.sleep(1)
        await send_telegram_message(input_data.text, id)
    return {"status": "Сообщение отправлено"}


async def send_telegram_message(text: str, telegram_id: int):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    params = {
        "chat_id": telegram_id,
        "text": text
    }
    async with httpx.AsyncClient() as client:
        response = await client.post(url, params=params)
    return response.json()