from aiogram import types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo

from config import URL_FRONT

def get_host_keyboard():
    kb = [
        [types.KeyboardButton(text="Управление интерактивами")],
        [types.KeyboardButton(text="Ввести код подключения")]
    ]
    keyboard = types.ReplyKeyboardMarkup(
        keyboard=kb,
        resize_keyboard=True
    )
    return keyboard


def get_member_keyboard():
    kb = [
        [types.KeyboardButton(text="Ввести код подключения")]
        # [types.KeyboardButton(text="Получить роль ведущего для комиссий урфу")]
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
                web_app=WebAppInfo(url=f"{URL_FRONT}participant/{interactive_id}")
            )
        ]
    ])

    return keyboard_inline


def get_link_to_main_menu():
    keyboard_inline = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="Нажмите, чтобы войти 🌐",
                web_app=WebAppInfo(url=F"{URL_FRONT}leader/new_interactives")
            )
        ]
    ])

    return keyboard_inline

def get_link_to_test():
    keyboard_inline = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="Test 🌐",
                web_app=WebAppInfo(url=F"{URL_FRONT}leader/test")
            )
        ]
    ])

    return keyboard_inline