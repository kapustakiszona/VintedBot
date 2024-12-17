import asyncio
import aiohttp
from typing import Optional, List

from aiogram import Bot, types
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select, exists

from data_base.base import connection
from data_base.dao import add_sent_item, get_users_link_list, get_all_users
from data_base.models import SentItem
from utils import convert_client_to_api_url


async def _fetch_cookie(baseurl: str, user_agent: str, retries: int = 3) -> str:
    for attempt in range(retries):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(baseurl, headers={"User-Agent": user_agent}) as response:
                    if response.status == 200:
                        session_cookie = ", ".join(response.headers.getall("Set-Cookie"))
                        if session_cookie and "access_token_web=" in session_cookie:
                            return session_cookie
                    await asyncio.sleep(2 ** attempt)  # Экспоненциальная задержка
        except aiohttp.ClientError as e:
            print(f"Ошибка сети: {e}. Попытка {attempt + 1} из {retries}.")
            await asyncio.sleep(2 ** attempt)
        except asyncio.TimeoutError:
            print(f"Timeout on attempt {attempt + 1}")

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


# Функция для обработки и вывода информации о товарах
@connection
async def parse_items(session, items_data: List[dict], user_id: int, link, bot: Bot) -> List[str]:
    new_items = []
    if not items_data:
        print("Нет данных для обработки.")
        return new_items

    for item in items_data:
        item_id = item.get("id")
        item_url = item.get("url")
        item_photo = item.get("photo").get("url")
        item_brand_title = item.get("brand_title")
        item_title = item.get("title")
        item_price = item.get("total_item_price").get("amount") + item.get("total_item_price").get("currency_code")
        builder = InlineKeyboardBuilder()
        builder.row(types.InlineKeyboardButton(text="Show", url=item_url))
        if item_id and item_title and item_url:
            # Проверка, есть ли этот товар уже в базе
            async with session.begin():
                existing_item = await session.scalar(
                    select(exists().where(SentItem.item_id == item_id, SentItem.link_id == link.id))
                )
                if not existing_item:
                    # Добавление нового элемента в базу данных
                    result = await add_sent_item(item_id=item_id, link=link, title=item_title,
                                                 img_url=item.get("photo", {}).get("url"), item_url=item_url)
                    new_items.append(f"New item found: {item_title} - {item_url}")
                    if result:
                        formatted_string = (
                            f"™️ <b>{item_brand_title}</b>\n"
                            f"💵 <b>{item_price}</b>\n"
                            f"📌 <b>{item_title}</b>"
                        )
                        # Отправить уведомление пользователю
                        await bot.send_photo(
                            chat_id=user_id,
                            photo=item_photo,
                            caption=formatted_string,
                            reply_markup=builder.as_markup(),
                            parse_mode="HTML"
                        )
    return new_items


# Функция для получения товаров с сайта и проверки
async def get_items_for_user(user_id: int, bot: Bot):
    user = await get_users_link_list(user_id)
    if not user or not user.links:
        return

    for link in user.links:
        url_api = convert_client_to_api_url(link.link)  # Преобразование ссылки для API
        baseurl = link.link  # Это исходная ссылка
        user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"

        session_cookie = await _fetch_cookie(baseurl, user_agent)
        headers = {
            "User-Agent": user_agent,
            "Cookie": session_cookie,
        }

        data = await fetch_data(url_api, headers)
        if data:
            new_items = await parse_items(data.get('items', []), user_id, link, bot)
            if new_items:
                print(f"New items found for user {user_id}: {new_items}")
        else:
            print("Ошибка при получении данных.")


# Периодическая проверка новых товаров для всех пользователей
async def periodic_check(bot: Bot):
    while True:
        all_users = await get_all_users()
        tasks = [get_items_for_user(user.user_id, bot) for user in all_users]
        try:
            await asyncio.gather(*tasks)
        except Exception as e:
            print(f"An error occurred while gathering tasks: {e}")

        await asyncio.sleep(15)
