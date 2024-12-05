from aiogram.types import KeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder

keyboard = ReplyKeyboardBuilder()
keyboard.add(KeyboardButton(text="Add Link"))
keyboard.add(KeyboardButton(text="Remove Link"))
keyboard.add(KeyboardButton(text="Show Link list"))
keyboard.add(KeyboardButton(text="Help"))
keyboard.adjust(2)