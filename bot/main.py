import asyncio
from aiogram import F, Router, Bot, Dispatcher
from aiogram.filters import CommandObject, CommandStart, Command
from aiogram.types import Message
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext

from requests_api import get_role, check_code, change_user_role, add_organization_participants
from keyboards import get_host_keyboard, get_member_keyboard, get_link_to_interavctive, get_link_to_main_menu, get_link_to_test

from dotenv import load_dotenv
import os

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")

# Проверка обязательных переменных
if not BOT_TOKEN:
    raise ValueError("Не все обязательные переменные окружения заданы!")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
router = Router()

class CodeInput(StatesGroup):
    waiting_for_code = State()

MAX_ATTEMPTS = 2


@router.message(F.text == "/start")
async def start_handler(message: Message):

    role = await get_role(message)
    first_name = message.from_user.first_name

    if role == "leader":
        greet_text = (
            f"Приятно познакомиться, {first_name}! Вам назначена роль ведущего. "
            "В этом сервисе вы можете создавать, управлять и проводить интерактивы."
        )
        keyboard = get_host_keyboard()

    if role == "admin":
        greet_text = (
            f"Приятно познакомиться, {first_name}! Вам назначена роль админа. "
            "В этом сервисе вы можете создавать, управлять и проводить интерактивы."
        )
        keyboard = get_host_keyboard()

    if role == "organizer":
        greet_text = (
            f"Приятно познакомиться, {first_name}! Вам назначена роль организатор. "
            "В этом сервисе вы можете создавать, управлять и проводить интерактивы."
        )
        keyboard = get_host_keyboard()

    elif role == "participant":
        greet_text = (
            f"{first_name}, добро пожаловать в Clik! Вы подключились как участник — "
            "присоединяйтесь к интерактивам и проходите их с удовольствием."
        )
        keyboard = get_member_keyboard()

    else:
        greet_text = "Ваша роль не распознана. Пожалуйста, свяжитесь с администратором."
        keyboard = None

    await message.answer(greet_text, reply_markup=keyboard)


@router.message(F.text == "Управление интерактивами")
async def start_cmd(message: Message):
    role = await get_role(message)
    if role == "leader" or role == "admin" or role == "organizer":
        await message.answer("Панель управления интерактивами", reply_markup=get_link_to_main_menu())

# @router.message(F.text == "Test")
# async def start_cmd(message: Message):
#     role = await get_role(message)
#     if await get_role(message) == "leader":
#         await message.answer("Панель управления интерактивами", reply_markup=get_link_to_test())

@router.message(F.text == "Ввести код подключения")
async def start_cmd(message: Message, state: FSMContext):
    role = await get_role(message)
    await state.set_state(CodeInput.waiting_for_code)
    await state.update_data(attempts=0)
    await message.answer("Введите код для подключения к интерактиву")

# @router.message(F.text == "Получить роль ведущего для комиссий урфу")
# async def get_leader_role(message: Message):
#     role = await get_role(message)
#     success = await change_user_role(message.from_user.id, "leader")
#     if success:
#         await message.answer("Роль успешно изменена на ведущего!", reply_markup=get_host_keyboard())
#     else:
#         await message.answer("Не удалось изменить роль. Пожалуйста, введите команду /start.")
#
# @router.message(F.text == "Получить роль участника для комиссий урфу")
# async def get_participant_role(message: Message):
#     role = await get_role(message)
#     success = await change_user_role(message.from_user.id, "participant")
#     if success:
#         await message.answer("Роль успешно изменена на участника!", reply_markup=get_member_keyboard())
#     else:
#         await message.answer("Не удалось изменить роль. Пожалуйста, введите команду /start.")

@router.message(CodeInput.waiting_for_code)
async def handle_code_input(message: Message, state: FSMContext):
    role = await get_role(message)
    code  = message.text
    if code.startswith("/start"):
        code = code[7:]
    await process_code(code, message, state)


@router.message(CommandStart(deep_link=True))
async def handle_start_with_param(message: Message, command: CommandObject, state: FSMContext):
    param = command.args
    if not param:
        return

    role = await get_role(message)

    # Проверяем состояние
    current_state = await state.get_state()
    if current_state == CodeInput.waiting_for_code.state:
        # Обрабатываем код из deep link
        await process_code(param, message, state)
        return

    # Проверяем, является ли параметр telegram_id_role (формат: "123456_leader" или "123456_participant")
    if "_" in param:
        try:
            parts = param.split("_")
            telegram_id = int(parts[0])
            role_param = parts[1]

            # Здесь просто логируем в консоль
            print(f"Получен deep link с telegram_id={telegram_id} и role={role_param}")
            role = await add_organization_participants(message, telegram_id, role_param)

            # Остальная логика для обычного deep link
            if role == "leader":
                keyboard = get_host_keyboard()
                greeting = f"Добро пожаловать, тебя добавили в организацию с ролью ведущий"
            elif role == "admin":
                keyboard = get_member_keyboard()
                greeting = f"Добро пожаловать, тебя добавили в организацию с ролью админ"
            elif role == "organizer":
                keyboard = get_member_keyboard()
                greeting = f"Добро пожаловать, тебя добавили в организацию с ролью организатор"
            else:
                greeting = "Ваша роль не распознана. Пожалуйста, свяжитесь с администратором."
                keyboard = None

            await message.answer(greeting, reply_markup=keyboard)
            return

        except (ValueError, IndexError):
            # Если не удалось распарсить как telegram_id_role, продолжаем как обычно
            pass

    # Обрабатываем как обычный код интерактива (6 символов)
    is_valid_role = True
    keyboard = None

    if role == "leader":
        keyboard = get_host_keyboard()
        greeting = f"Получен код интерактива: {param}"
    elif role == "participant":
        keyboard = get_member_keyboard()
        greeting = f"Получен код интерактива: {param}"
    else:
        is_valid_role = False
        greeting = "Ваша роль не распознана. Пожалуйста, свяжитесь с администратором."

    await message.answer(greeting, reply_markup=keyboard)

    if is_valid_role:
        if await process_code(param, message, state):
            return
        await message.answer(
            "Код неверный, попробуйте ввести его вручную. Сначала нажмите кнопку \"Ввести код подключения\""
        )

async def process_code(code: str, message: Message, state: FSMContext):
    role = await get_role(message)
    user_data = await state.get_data()
    attempts = user_data.get("attempts", 0)

    interactive_id = await check_code(code)
    if interactive_id is not None:
        await message.answer(
            "✅ Код верный! Подключайтесь к интерактиву! Скоро начнем!",
            reply_markup=get_link_to_interavctive(interactive_id)
        )
        await state.clear()
        return True

    attempts += 1
    if attempts >= MAX_ATTEMPTS:
        await state.clear()
        await message.answer(
            "Попробуйте еще раз, нажав кнопку \"Ввести код подключения\""
        )
    else:
        await state.update_data(attempts=attempts)
        await message.answer("Попробуйте ввести код еще раз")
    return False

dp.include_router(router)


async def main():
    # Удаляем webhook если был установлен
    await bot.delete_webhook(drop_pending_updates=True)

    # Запускаем polling
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())