import urllib.parse

from aiogram.fsm.state import StatesGroup, State


class MainStates(StatesGroup):
    waiting_for_link = State()
    waiting_for_link_removal = State()
    waiting_for_admin_action = State()
    waiting_for_generated_link_name = State()

def unescape_url(escaped_url: str) -> str:
    # Декодируем URL-кодированную строку обратно в исходную
    return urllib.parse.unquote(escaped_url)

def escape_url(url: str) -> str:
    # Применяем URL-кодирование, экранируя все символы, кроме стандартных для URL
    return urllib.parse.quote(url, safe=":/?&=.%")

def split_message(text, max_length=4000):
    """Разбивает длинное сообщение на части."""
    parts = []
    while len(text) > max_length:
        split_index = text[:max_length].rfind("\n")
        if split_index == -1:  # Если не находит подходящий перенос строки
            split_index = max_length
        parts.append(text[:split_index])
        text = text[split_index:]
    parts.append(text)
    return parts
