import json
import time
import requests
from requests import  Session

from utils import convert_client_to_api_url

url_api = convert_client_to_api_url(
    'https://www.vinted.pl/catalog?search_text=klattermusen%20&brand_ids[]=1638071&search_id=19332593046&order=newest_first&time=1733857900')
baseurl = 'https://www.vinted.pl/catalog?search_text=klattermusen%20&brand_ids[]=1638071&search_id=19332593046&order=newest_first&time=1733857900'
user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
vin_url = 'https://www.vinted.pl'


def _fetch_cookie( retries: int = 3) -> str:
    response = None
    for _ in range(retries):
        response = requests.get(
            vin_url, headers={"User-Agent": user_agent}
        )
        if response.status_code == 200:
            session_cookie = response.headers.get("Set-Cookie")
            print(session_cookie)
            if session_cookie and "access_token_web=" in session_cookie:
                # print(f"{session_cookie.split("access_token_web=")[1].split(";")[0]}")
                return session_cookie
        else:
            # Exponential backoff before retrying
            time.sleep(2 ** _)
    raise RuntimeError(
        f"Cannot fetch session cookie from {baseurl}, because of "
        f"status code: {response.status_code if response is not None else 'none'} different from 200."
    )

def get_data(url: str):
    headers = {
        "User-Agent": f"{user_agent}",
        "Cookie": f"{_fetch_cookie()}"
    }
    with requests.Session() as s:
        response = s.get(url, headers=headers)
        if response.status_code == 200:
            try:
                json_data = response.json()
                print(json_data)
                return json_data.get('items')
            except ValueError:
                print("Ответ не является JSON.")
        else:
            print(f"Ошибка: {response.status_code}, текст: {response.text}")

def get_items(url:str):
    items_data = get_data(url)
    for item in items_data:
        item_id = item.get("id")
        item_title = item.get("title")
        item_photo = item.get("photo").get("url")
        item_price = item.get("total_item_price").get("amount") +item.get("total_item_price").get("currency_code")
        item_url = item.get("url")
        item_brand_title = item.get("brand_title")
        item_description = f" {item_title}\n Brand: {item_brand_title}\n Price: {item_price}"
        print(item_description, item_photo, item_url, item_id)


def main():
    get_items(url_api)


if __name__ == "__main__":
    main()
