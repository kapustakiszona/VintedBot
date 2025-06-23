import asyncio
import logging
import random
from datetime import datetime, timedelta, UTC
from typing import Optional, List

import aiohttp
from aiogram import Bot, types
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select, exists

from config_reader import config
from data_base.base import connection
from data_base.dao import add_sent_item, get_users_link_list, get_all_users, get_user_filter_words
from data_base.models import SentItem
from utils import convert_client_to_api_url

# Формируем список прокси
PROXY_URL = f"http://{config.smartproxy_username.get_secret_value()}:{config.smartproxy_password.get_secret_value()}@{config.smartproxy_endpoint}:{config.smartproxy_port}"

# Пул User-Agent для ротации
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:115.0) Gecko/20100101 Firefox/115.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.4 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.1901.183 Safari/537.36 Edg/115.0.1901.183",
]


class SessionManager:
    def __init__(self, baseurl: str, user_agent: str):
        self.baseurl = baseurl
        self.user_agent = user_agent
        self.cookies = {}
        self.last_cookie_update = datetime.now(UTC)
        self.lock = asyncio.Lock()
        self.consecutive_failures = 0

    async def _fetch_cookies(self, session: aiohttp.ClientSession) -> bool:
        """Получает куки с главной страницы"""
        try:
            headers = {
                "User-Agent": self.user_agent,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "Accept-Encoding": "gzip, deflate, br",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1"
            }

            async with session.get(
                    self.baseurl,
                    headers=headers,
                    proxy=PROXY_URL,
                    verify_ssl=True,
                    allow_redirects=True
            ) as response:
                if response.status == 200:
                    self.cookies = {k: v.value for k, v in response.cookies.items()}
                    self.last_cookie_update = datetime.now(UTC)
                    self.consecutive_failures = 0
                    return True
                else:
                    self.consecutive_failures += 1
                    logging.error(f"Failed to fetch cookies, status: {response.status}")
                    return False

        except Exception as e:
            self.consecutive_failures += 1
            logging.error(f"Error fetching cookies: {str(e)}")
            return False

    def _should_update_cookies(self) -> bool:
        """Проверяет, нужно ли обновить куки"""
        if not self.cookies:
            return True

        # Обновляем куки каждый час или если были ошибки
        if (datetime.now(UTC) - self.last_cookie_update) > timedelta(hours=1):
            return True

        return self.consecutive_failures >= 3

    def get_headers(self) -> dict:
        """Возвращает заголовки для запроса"""
        headers = {
            "Accept": "application/json",
            "Accept-Language": "en-US,en;q=0.9",
            "User-Agent": self.user_agent,
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Cache-Control": "no-cache",
            "X-Requested-With": "XMLHttpRequest"
        }

        if self.cookies:
            cookie_str = "; ".join([f"{k}={v}" for k, v in self.cookies.items()])
            headers["Cookie"] = cookie_str

        return headers


async def fetch_data(session: aiohttp.ClientSession, url: str, headers: dict, session_mgr: SessionManager) -> Optional[
    dict]:
    max_retries = 3
    base_delay = 5  # начальная задержка в секундах

    for attempt in range(max_retries):
        try:
            # Проверяем, нужно ли обновить куки
            if session_mgr._should_update_cookies():
                await session_mgr._fetch_cookies(session)
                # Обновляем заголовки с новыми куками
                headers = session_mgr.get_headers()

            async with session.get(
                    url,
                    headers=headers,
                    timeout=30,
                    proxy=PROXY_URL,
                    verify_ssl=True,
                    compress=True
            ) as response:
                if response.status == 200:
                    return await response.json()
                elif response.status == 403:
                    logging.error("Получен код 403 (возможно, блокировка Cloudflare)")
                    # Пробуем обновить куки при 403 ошибке
                    await session_mgr._fetch_cookies(session)
                    await asyncio.sleep(60 * (attempt + 1))
                elif response.status == 429:
                    logging.error("Получен код 429 (слишком много запросов)")
                    await asyncio.sleep(30 * (attempt + 1))
                else:
                    logging.error(f"Ошибка: {response.status}, текст: {await response.text()}")
                    await asyncio.sleep(base_delay * (2 ** attempt))

        except aiohttp.ClientError as e:
            logging.error(f"Ошибка запроса: {e}")
            await asyncio.sleep(base_delay * (2 ** attempt))
        except asyncio.TimeoutError:
            logging.error("Timeout error")
            await asyncio.sleep(base_delay * (2 ** attempt))
        except ValueError as e:
            logging.error(f"Ошибка парсинга JSON: {e}")
            return None
        except Exception as e:
            logging.error(f"Неожиданная ошибка: {e}")
            await asyncio.sleep(base_delay * (2 ** attempt))

    return None


async def get_items_for_user(user_id: int, bot: Bot, session_mgr: SessionManager):
    user = await get_users_link_list(user_id)
    if not user or not user.links:
        return

    async with aiohttp.ClientSession() as session:
        for link in user.links:
            url_api = convert_client_to_api_url(link.link)
            headers = session_mgr.get_headers()

            data = await fetch_data(session, url_api, headers, session_mgr)
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
    session_mgr = SessionManager(baseurl=first_link, user_agent=user_agent)

    # Создаем словарь для отслеживания времени последнего запроса для каждого пользователя
    last_check_times = {user.user_id: datetime.now(UTC) for user in all_users}
    last_mode_log = None  # Для отслеживания изменения режима

    while True:
        current_time = datetime.now(UTC)
        current_hour = current_time.hour

        # Определяем режим работы и интервалы
        is_night_mode = 0 <= current_hour < 7
        min_interval = 120 if is_night_mode else 15  # секунд

        # Логируем изменение режима работы только при его смене
        current_mode = "ночной" if is_night_mode else "дневной"
        if last_mode_log != current_mode:
            logging.info(f"Режим работы: {current_mode}")
            logging.info(f"Интервал между запросами: {min_interval} секунд")
            last_mode_log = current_mode

        for user in await get_all_users():
            # Проверяем, прошло ли достаточно времени с последней проверки для этого пользователя
            if user.user_id not in last_check_times:
                last_check_times[user.user_id] = datetime.now(UTC)

            time_since_last_check = (current_time - last_check_times[user.user_id]).total_seconds()

            if time_since_last_check >= min_interval:
                try:
                    # В ночное время увеличиваем случайную задержку
                    max_random_delay = 10 if is_night_mode else 5
                    delay = random.uniform(0, max_random_delay)
                    logging.debug(f"Задержка перед запросом: {delay:.1f} сек")
                    await asyncio.sleep(delay)

                    # Обновляем время последней проверки
                    last_check_times[user.user_id] = current_time

                    # Выполняем проверку для пользователя
                    await get_items_for_user(user.user_id, bot, session_mgr)

                except Exception as e:
                    logging.error(f"Ошибка при проверке для пользователя {user.user_id}: {e}")
                    # Добавляем дополнительную задержку при ошибке
                    await asyncio.sleep(random.uniform(5, 15))

        # Случайная задержка между циклами проверки всех пользователей
        cycle_delay = random.uniform(30, 60) if is_night_mode else random.uniform(15, 30)
        logging.debug(f"Задержка между циклами: {cycle_delay:.1f} сек")
        await asyncio.sleep(cycle_delay)


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
