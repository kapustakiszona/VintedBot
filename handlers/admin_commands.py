import logging

from aiogram import Router, F
from aiogram.exceptions import TelegramRetryAfter, TelegramAPIError, TelegramNotFound, TelegramForbiddenError
from aiogram.types import Message

from create_bot import admins, bot
from data_base.base import connection
from data_base.dao import get_all_users, set_user_premium, set_user_ban
from utils import split_message

admin_router = Router()


# admin panel handler
@admin_router.message(F.text == "Admin panel")
async def administration(message: Message):
    user_id = message.chat.id
    if user_id in admins:
        admin_text = (
            "You are logged into the admin panel. Available commands:\n"
            "/view_users - Show all users\n"
            "/send_message - Send a message to all users\n"
            "/grant_premium - Grant premium access to the user\n"
            "/ban_user - Ban user"
        )
        await message.answer(admin_text)
    else:
        await message.answer("You are not admin.")


# /view_users handler
@admin_router.message(F.text == "/view_users")
async def view_user(message: Message):
    user_id = message.chat.id
    if user_id not in admins:
        await message.answer("You are not an admin.")
        return
    users = await get_all_users()
    if not users:
        await message.answer("No users found.")
        return
    response = "User List:\n"
    for user in users:
        user_status = (
            f"Premium: {'Yes' if user.is_premium else 'No'}, "
            f"Admin: {'Yes' if user.is_admin else 'No'}, "
            f"Banned: {'Yes' if user.is_banned else 'No'}"
        )
        links_list = "\n".join(f"  - [link]({link.link})" for link in user.links) if user.links else "  No links"
        response += (
            f"\nUser ID: {user.user_id}\n"
            f"{user_status}\n"
            f"Links:\n{links_list}\n"
        )

    for part in split_message(response):
        await message.answer(part, parse_mode="Markdown")


@connection
@admin_router.message(F.text.startswith("/grant_premium"))
async def grant_user_premium(message: Message):
    user_id = message.chat.id
    if user_id not in admins:
        await message.answer("You are not an admin.")
        return
    # Проверяем правильность команды
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("Usage: /grant_premium <user_id>", parse_mode=None)
        return
    try:
        target_user_id = int(parts[1])
    except ValueError:
        await message.answer("Invalid user_id format. Please provide a valid integer ID.", parse_mode=None)
        return
    # Вызываем функцию для изменения статуса премиум
    result = await set_user_premium(target_user_id)
    if result:
        await message.answer(f"User with ID {target_user_id} now has premium access.", parse_mode=None)
    elif not result:
        await message.answer(f"User with ID {target_user_id} is no longer premium.", parse_mode=None)
    else:
        await message.answer(f"User with ID {target_user_id} not found or could not be updated.", parse_mode=None)


@connection
@admin_router.message(F.text.startswith("/ban_user"))
async def set_user_ban_status(message: Message):
    user_id = message.chat.id
    if user_id not in admins:
        await message.answer("You are not an admin.")
        return
    # Проверяем правильность команды
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("Usage: /ban_user <user_id>", parse_mode=None)
        return
    try:
        target_user_id = int(parts[1])
    except ValueError:
        await message.answer("Invalid user_id format. Please provide a valid integer ID.", parse_mode=None)
        return
    # Вызываем функцию для изменения статуса ban
    result = await set_user_ban(target_user_id)
    if result:
        await message.answer(f"User with ID {target_user_id} got banned.", parse_mode=None)
    elif not result:
        await message.answer(f"User with ID {target_user_id} is unbanned", parse_mode=None)
    else:
        await message.answer(f"User with ID {target_user_id} not found or could not be updated.", parse_mode=None)


@connection
@admin_router.message(F.text.startswith("/send_message"))
async def send_message(message: Message):
    user_id = message.chat.id
    if user_id not in admins:
        await message.answer("You are not an admin.")
        return
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("Usage: /send_message <Text_message>", parse_mode=None)
        return
    users = await get_all_users()
    for user in users:
        try:
            await bot.send_message(chat_id=user.user_id, text=parts[1], parse_mode="MarkdownV2")
            logging.info(f"Сообщение отправлено пользователю с ID {user.user_id}.")
        except TelegramForbiddenError:
            logging.warning(f"Бот заблокирован пользователем с ID {user.user_id}.")
        except TelegramNotFound:
            logging.warning(f"Чат с пользователем ID {user.user_id} не найден.")
        except TelegramRetryAfter as e:
            logging.warning(f"Превышен лимит запросов. Повторите через {e.retry_after} секунд.")
        except TelegramAPIError as e:
            logging.error(f"Ошибка Telegram API при отправке пользователю {user.user_id}: {e}")
        except Exception as e:
            logging.error(f"Непредвиденная ошибка при отправке сообщения пользователю {user.user_id}: {e}")