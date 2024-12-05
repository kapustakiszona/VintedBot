import logging

from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, KeyboardButton

from create_bot import admins
from data_base.base import connection
from data_base.dao import add_user, add_link, get_users_link_list, delete_link
from keyboards.for_main_commands import keyboard
from utils import MainStates, escape_url

router = Router()


# /start handler
@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    user_id = message.chat.id
    # Получаем пользователя из базы данных (или добавляем нового, если его нет)
    user = await add_user(user_id=user_id, is_admin=user_id in admins)
    # Проверяем, забанен ли пользователь
    if user.is_banned:
        await message.answer("You are banned and cannot use this bot.")
        logging.warning(f"Banned user {user_id} ({message.chat.username}) tried to access the bot.")
        return
    # Если пользователь администратор, добавляем кнопку "Admin panel"
    if user_id in admins:
        keyboard.add(KeyboardButton(text="Admin panel"))
    # Приветственное сообщение и клавиатура
    await message.answer(
        "Hi! I am Vinted tracker bot!\n"
        "Select an action using the buttons below:",
        reply_markup=keyboard.as_markup(resize_keyboard=True)
    )
    logging.info(f"User {user_id} ({message.chat.username}) started the bot.")



# /add_link handler
@router.message(F.text == "Add Link")
async def add_user_link(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Please send tracking link!")
    await state.set_state(MainStates.waiting_for_link)


# handler for getting link
@connection
@router.message(MainStates.waiting_for_link)
async def save_link(message: Message, state: FSMContext):
    user_id = message.chat.id
    row_link = message.text
    if row_link.startswith("https://www.vinted."):
        link = escape_url(row_link)
        result = await add_link(user_id=user_id, link=link)
        if result is False:
            await message.answer("You have reached the maximum number of links allowed.")
        else:
            await message.answer(f"Link {row_link} added for tracking.")
        logging.info(f"Link {link} added by user {user_id}")
    else:
        await message.answer("Please send the correct link starting with 'https://www.vinted.'.")
    await state.clear()


# handler for show links
@router.message(F.text == "Show Link list")
async def show_links(message: Message):
    user_id = message.chat.id
    user = await get_users_link_list(user_id)
    if not user:
        await message.answer("User not found.")
        return
    if not user.links:
        await message.answer("You don't have any links added yet.")
        return
    links_list = "\n".join(f"- {link.link}" for link in user.links)
    await message.answer(f"Your links:\n{links_list}")


# /delete_link handler
@router.message(F.text == "Remove Link")
async def add_user_link(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Please send link for removing.")
    await state.set_state(MainStates.waiting_for_link_removal)


# handler for removing link
@router.message(MainStates.waiting_for_link_removal)
async def remove_user_link(message: Message, state: FSMContext):
    user_id = message.chat.id
    user_link = message.text
    if not user_link.startswith("https://www.vinted."):
        await message.answer("This appears to be an incorrect link."
                             " The link must start with 'https://www.vinted.'.")
        return
    result = await delete_link(user_id=user_id, link=user_link)
    if result:
        await message.answer(f"Link {user_link} has been removed from tracking.")
    else:
        await message.answer(f"This link was not found in your list or an error occurred")
    await state.clear()


# /help handler
@router.message(F.text == "Help")
async def help_user(message: Message):
    help_text = (
        "This bot helps you track products on the Vinted website.\n\n"
        "Here are the available commands:\n"
        "/start - Start the bot\n"
        "Add link - Send a link that the bot will track\n"
        " -In order to receive the link, you must use the web version of Vinted.\n"
        " -Go to the Vinted website, enter information about what you are looking for in the search bar\n"
        " -if desired, filter the search by size, price, category, etc.\n"
        " -IMPORTANT! Select sorting 'newest first'.\n"
        " -After this, copy the resulting link from the browser and add it to the bot.\n"
        "Remove link - Remove link from tracking\n"
        "Show list - Show all added tracking links\n"
        "Help - Information about the bot"
    )
    await message.answer(help_text)
