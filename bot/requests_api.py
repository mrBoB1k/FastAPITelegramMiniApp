import certifi
import aiohttp
import os
import ssl

from dotenv import load_dotenv

load_dotenv()

_URL = "http://127.0.0.1:8000"
# _URL = "http://fastapi_app:8000"
# получение роли пользователя

# _URL = "https://carclicker.ru"

async def get_role(message):
    url = f"{_URL}/api/users/register"
    params = {
        "x_key": os.getenv("SECRET_KEY"),
        "telegram_id": message.from_user.id,
        "username": message.from_user.username,
        "first_name": message.from_user.first_name,
        "last_name": message.from_user.last_name,
        "phone_number": ""
    }

    params = {k: v for k, v in params.items() if v is not None}

    # отключает проверку на подлинность ssl сертификата, иначе у меня на машине выдает ошибку
    ssl_context = ssl.create_default_context(cafile=certifi.where())

    async with aiohttp.ClientSession() as session:
        async with session.post(url, params=params, ssl=ssl_context) as response:
            try:
                response_data = await response.json()
            except aiohttp.ContentTypeError:
                pass

            return response_data.get("role")
    # return  "leader"


# функция проверки существования интерактива по коду (пока заглушка)


async def check_code(code: str) -> int | None:
    url = f"{_URL}/api/interactivities/join"
    params = {
        "x_key": os.getenv("SECRET_KEY"),
        "code": code
    }

    # Удаляем None значения
    params = {k: v for k, v in params.items() if v is not None}

    # Настраиваем SSL контекст
    ssl_context = ssl.create_default_context(cafile=certifi.where())

    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params, ssl=ssl_context) as response:
            if response.status == 404:
                return None

            try:
                response_data = await response.json()
                return response_data.get("interactive_id")
            except aiohttp.ContentTypeError:
                return None
    # return 1213

async def change_user_role(telegram_id: int, role: str):
    url = f"{_URL}/api/users/user_change_role"
    params = {
        "x_key": os.getenv("SECRET_KEY"),
        "telegram_id": telegram_id,
        "role": role
    }

    # Удаляем None значения
    params = {k: v for k, v in params.items() if v is not None}

    # Настраиваем SSL контекст
    ssl_context = ssl.create_default_context(cafile=certifi.where())

    async with aiohttp.ClientSession() as session:
        async with session.patch(url, params=params, ssl=ssl_context) as response:
            if response.status == 200:
                return True
            return False