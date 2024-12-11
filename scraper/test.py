import asyncio
import aiohttp
from typing import Optional, List

from utils import convert_client_to_api_url


async def _fetch_cookie(baseurl: str, user_agent: str, retries: int = 3) -> str:
    for attempt in range(retries):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(baseurl, headers={"User-Agent": user_agent}) as response:
                    print(f"Статус ответа: {response.status}")
                    print(f"Заголовки ответа: {response.headers.getall("Set-Cookie")}")

                    if response.status == 200:
                        session_cookie = ", ".join(response.headers.getall("Set-Cookie"))
                        print(f"Set-Cookie: {session_cookie}")

                        if session_cookie and "access_token_web=" in session_cookie:
                            return session_cookie
                    await asyncio.sleep(2 ** attempt)  # Экспоненциальная задержка
        except aiohttp.ClientError as e:
            print(f"Ошибка сети: {e}. Попытка {attempt + 1} из {retries}.")
            await asyncio.sleep(2 ** attempt)

    raise RuntimeError(
        f"Не удалось получить cookie с {baseurl}. Статус: "
        f"{response.status if response else 'неизвестен'}."
    )


async def fetch_data(url: str, headers: dict) -> Optional[dict]:
    """Асинхронное получение данных с заданного URL."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    print(f"Ошибка: {response.status}, текст: {await response.text()}")
    except aiohttp.ClientError as e:
        print(f"Ошибка запроса: {e}")
    except ValueError:
        print("Ответ не является JSON.")
    return None


def parse_items(items_data: List[dict]) -> None:
    """Обработка и вывод данных об элементах."""
    if not items_data:
        print("Нет данных для обработки.")
        return

    for item in items_data:
        try:
            item_id = item.get("id", "Неизвестно")
            item_title = item.get("title", "Без названия")
            photo = item.get("photo", {}).get("url", "Фото отсутствует")
            price = item.get("total_item_price", {})
            item_price = f"{price.get('amount', 'N/A')}{price.get('currency_code', '')}"
            item_url = item.get("url", "URL отсутствует")
            brand_title = item.get("brand_title", "Неизвестный бренд")
            item_description = f"{item_title}\n Brand: {brand_title}\n Price: {item_price}"
            print(item_description, photo, item_url, item_id)
        except AttributeError as e:
            print(f"Ошибка обработки элемента: {e}")


async def get_items(baseurl: str, url_api: str, user_agent: str) -> None:
    """Асинхронная функция для получения и обработки данных."""
    try:
        session_cookie = await _fetch_cookie(baseurl, user_agent)
        headers = {
            "User-Agent": user_agent,
            "Cookie": session_cookie,
        }
        data = await fetch_data(url_api, headers)
        if data:
            parse_items(data.get('items', []))
        else:
            print("Получены некорректные данные.")
    except RuntimeError as e:
        print(f"Ошибка выполнения: {e}")


async def main():
    url_api = convert_client_to_api_url(
        'https://www.vinted.pl/catalog?search_text=klattermusen%20&brand_ids[]=1638071&search_id=19332593046&order=newest_first&time=1733857900')
    baseurl = 'https://www.vinted.pl/catalog?search_text=klattermusen%20&brand_ids[]=1638071&search_id=19332593046&order=newest_first&time=1733857900'
    user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    vin_url = 'https://www.vinted.pl'
    await get_items(vin_url, url_api, user_agent)


if __name__ == "__main__":
    asyncio.run(main())
