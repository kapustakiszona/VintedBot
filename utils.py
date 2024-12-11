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


from urllib.parse import urlencode, urlparse, parse_qs


def convert_client_to_api_url(client_url):
    # Парсим URL
    parsed_url = urlparse(client_url)
    query_params = parse_qs(parsed_url.query)

    # Определяем соответствие параметров
    param_map = {
        "search_text": "search_text",
        "catalog[]": "catalog_ids",
        "status_ids[]": "status_ids",
        "size_ids[]": "size_ids",
        "color_ids[]": "color_ids",
        "brand_ids[]": "brand_ids",
        "material_ids[]": "material_ids",
        "price_from": "price_from",
        "price_to": "price_to",
        "currency": "currency",
        "order": "order",
        "time": "time",
        "page": "page",
    }

    # Базовые параметры API
    api_params = {
        "page": query_params.get("page", ["1"])[0],
        "per_page": "10",
    }

    # Преобразуем параметры в API-формат
    for client_param, api_param in param_map.items():
        if client_param in query_params:
            if client_param.endswith("[]"):  # Массивы преобразуем в строку через запятую
                api_params[api_param] = ",".join(query_params[client_param])
            else:  # Одиночные параметры сохраняем как есть
                api_params[api_param] = query_params[client_param][0]

    # Особая обработка search_text (замена %20 на +)
    if "search_text" in api_params:
        api_params["search_text"] = api_params["search_text"].replace("%20", "+")

    # Генерация API ссылки с динамическим доменом
    api_base_url = f"{parsed_url.scheme}://{parsed_url.netloc}/api/v2/catalog/items"
    api_url = f"{api_base_url}?{urlencode(api_params)}"
    return api_url
