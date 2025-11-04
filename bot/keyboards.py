from aiogram import types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo


def get_host_keyboard():
    kb = [
        [types.KeyboardButton(text="Управление интерактивами")],
        [types.KeyboardButton(text="Подключение к интерактиву")],
        [types.KeyboardButton(text="Получить роль участника для комиссий урфу")],
        [types.KeyboardButton(text="Test")]
    ]
    keyboard = types.ReplyKeyboardMarkup(
        keyboard=kb,
        resize_keyboard=True
    )
    return keyboard


def get_member_keyboard():
    kb = [
        [types.KeyboardButton(text="Подключение к интерактиву")],
        [types.KeyboardButton(text="Получить роль ведущего для комиссий урфу")]
    ]
    keyboard = types.ReplyKeyboardMarkup(
        keyboard=kb,
        resize_keyboard=True,
    )
    return keyboard


def get_link_to_interavctive(interactive_id: int):
    keyboard_inline = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="Нажмите, чтобы подключиться 🌐",
                web_app=WebAppInfo(url=f"https://voshod07.ru/participant/{interactive_id}")
            )
        ]
    ])

    return keyboard_inline


def get_link_to_main_menu():
    keyboard_inline = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="Нажмите, чтобы войти 🌐",
                web_app=WebAppInfo(url="https://voshod07.ru/leader/main_menu")
            )
        ]
    ])

    return keyboard_inline

def get_link_to_test():
    keyboard_inline = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="Test 🌐",
                web_app=WebAppInfo(url="https://voshod07.ru/leader/test")
            )
        ]
    ])

    return keyboard_inline