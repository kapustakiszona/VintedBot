import asyncio
import logging
import random
from datetime import datetime, timedelta
from typing import Optional, List

import cloudscraper
import aiohttp
from aiogram import Bot, types
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select, exists

from data_base.base import connection
from data_base.dao import add_sent_item, get_users_link_list, get_all_users, get_user_filter_words
from data_base.models import SentItem
from utils import convert_client_to_api_url

# Пул User-Agent для ротации
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:115.0) Gecko/20100101 Firefox/115.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.4 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.1901.183 Safari/537.36 Edg/115.0.1901.183",
]

class CookieManager:
    def __init__(self, baseurl: str, user_agent: str):
        self.baseurl = baseurl
        self.user_agent = user_agent
        self.cookie: Optional[str] = None
        self.expiry: datetime = datetime.min
        self.lock = asyncio.Lock()

    async def _fetch_and_parse(self) -> None:
        # Используем cloudscraper для прохождения CF challenge
        scraper = cloudscraper.create_scraper()
        scraper.headers.update({"User-Agent": self.user_agent})
        resp = scraper.get(self.baseurl)
        if resp.status_code != 200:
            raise RuntimeError(f"CF challenge failed: {resp.status_code}")
        # Собираем куки и expiry не отслеживается (можно задать ttl вручную)
        cookies = scraper.cookies.get_dict()
        self.cookie = "; ".join(f"{k}={v}" for k, v in cookies.items())
        # Не все куки имеют expires, установим короткий TTL, чтобы обновлять часто
        self.expiry = datetime.utcnow() + timedelta(minutes=30)

    async def get_cookie(self) -> str:
        async with self.lock:
            if not self.cookie or datetime.utcnow() >= self.expiry:
                await self._fetch_and_parse()
            return self.cookie or ""


async def fetch_data(session: aiohttp.ClientSession, url: str, headers: dict) -> Optional[dict]:
    try:
        async with session.get(url, headers=headers) as response:
            if response.status == 200:
                return await response.json()
            logging.error(f"Ошибка: {response.status}, текст: {await response.text()}")
    except aiohttp.ClientError as e:
        logging.error(f"Ошибка запроса: {e}")
    except ValueError:
        logging.error("Ответ не является JSON.")
    return None


@connection
async def parse_items(session, items_data: List[dict], user_id: int, link, bot: Bot) -> List[str]:
    new_items = []
    if not items_data:
        logging.info("Нет данных для обработки.")
        return new_items
    user_filter_words = await get_user_filter_words(user_id=user_id)

    for item in items_data:
        item_id = item.get("id")
        item_url = item.get("url")
        item_photo = item.get("photo", {}).get("url")
        item_brand_title = item.get("brand_title")
        item_title = item.get("title")
        price_info = item.get("total_item_price", {})
        item_price = price_info.get("amount", "") + " " + price_info.get("currency_code", "")

        if item_id and item_title and item_url:
            async with session.begin():
                exists_item = await session.scalar(
                    select(exists().where(SentItem.item_id == item_id, SentItem.link_id == link.id))
                )
                if not exists_item:
                    result = await add_sent_item(
                        item_id=item_id,
                        link=link,
                        title=item_title,
                        img_url=item_photo,
                        item_url=item_url
                    )
                    if result:
                        builder = InlineKeyboardBuilder()
                        builder.row(types.InlineKeyboardButton(text="👀Show", url=item_url))
                        send_notification = True
                        if user_filter_words:
                            text_to_check = item_title.lower()
                            if any(w in text_to_check for w in user_filter_words):
                                send_notification = False
                                logging.info(f"Фильтрация {item_title} для пользователя {user_id}.")
                        if send_notification:
                            caption = (
                                f"™️ <b>{item_brand_title}</b>\n"
                                f"💵 <b>{item_price}</b>\n"
                                f"📌 <b>{item_title}</b>"
                            )
                            await bot.send_photo(
                                chat_id=user_id,
                                photo=item_photo,
                                caption=caption,
                                reply_markup=builder.as_markup(),
                                parse_mode="HTML"
                            )
                            new_items.append(f"New item: {item_title} - {item_url}")
    return new_items


async def get_items_for_user(user_id: int, bot: Bot, cookie_mgr: CookieManager):
    user = await get_users_link_list(user_id)
    if not user or not user.links:
        return

    async with aiohttp.ClientSession() as session:
        for link in user.links:
            url_api = convert_client_to_api_url(link.link)
            session_cookie = await cookie_mgr.get_cookie()
            user_agent = cookie_mgr.user_agent
            headers = {
                "Accept": "application/json",
                "X-Requested-With": "XMLHttpRequest",
                "User-Agent": user_agent,
                "Cookie": session_cookie,
            }

            data = await fetch_data(session, url_api, headers)
            if data:
                await parse_items(data.get('items', []), user_id, link, bot)
            else:
                logging.error("Ошибка при получении данных.")


async def periodic_check(bot: Bot):
    all_users = await get_all_users()
    if not all_users:
        return
    first_link = (await get_users_link_list(all_users[0].user_id)).links[0].link
    user_agent = random.choice(USER_AGENTS)
    cookie_mgr = CookieManager(baseurl=first_link, user_agent=user_agent)

    while True:
        users = await get_all_users()
        tasks = [get_items_for_user(u.user_id, bot, cookie_mgr) for u in users]
        try:
            await asyncio.gather(*tasks)
        except Exception as e:
            logging.error(f"Ошибка сбора задач: {e}")
        await asyncio.sleep(15)
