import logging

from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, KeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder

from create_bot import admins
from data_base.base import connection
from data_base.dao import add_user, add_link, get_users_link_list, delete_link, add_user_filter_word, \
    remove_user_filter_word, get_user_filter_words
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
        "All users have the option to add two tracked links. Premium access increases their number to 15. To get premium, write @KierownikBoss\n"
        "Enter Help to get information on how to work with the bot or\n"
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
        "Help - Information about the bot\n"
        "\n"
        "📣To get premium access or if you have any questions or problems, write to @KierownikBoss\n"
    )
    await message.answer(help_text)


# /manage_filters handler
@router.message(F.text == "Manage Filters")
async def manage_filters_menu(message: Message, state: FSMContext):
    """Обработчик нажатия кнопки 'Manage Filters'. Показ нового меню."""
    await state.clear()

    # Формируем меню управления фильтрами
    filter_keyboard = ReplyKeyboardBuilder()  # Изменено имя переменной
    filter_keyboard.add(KeyboardButton(text="Add Filter"))
    filter_keyboard.add(KeyboardButton(text="Remove Filter"))
    filter_keyboard.add(KeyboardButton(text="Show Filters"))
    filter_keyboard.add(KeyboardButton(text="⬅️ Back"))  # Кнопка возврата к основному меню
    filter_keyboard.adjust(2)

    await state.set_state(MainStates.filter_management_menu)  # Устанавливаем состояние для контекста фильтров
    await message.answer(
        "Filter Management Menu:\n"
        "- Add Filter: Add a word to your filters. For example, if you want to filter items containing certain words, add them here.\n"
        "- Remove Filter: Remove a word from your filters if you no longer want it to affect the results.\n"
        "- Show Filters: View all words currently in your filters. These are the words being considered for filtering your tracked items.",
        reply_markup=filter_keyboard.as_markup(resize_keyboard=True)
    )


# /back_to_main_menu handler (кнопка "⬅️ Back")
@router.message(F.text == "⬅️ Back")
async def back_to_main_menu(message: Message, state: FSMContext):
    """Возвращает пользователя в главное меню."""
    await state.clear()

    # Основное меню
    main_keyboard = ReplyKeyboardBuilder()  # Изменено имя переменной
    main_keyboard.add(KeyboardButton(text="Add Link"))
    main_keyboard.add(KeyboardButton(text="Remove Link"))
    main_keyboard.add(KeyboardButton(text="Show Link list"))
    main_keyboard.add(KeyboardButton(text="Manage Filters"))
    main_keyboard.add(KeyboardButton(text="Help"))
    main_keyboard.adjust(2)

    await message.answer(
        "Returned to the main menu. Select an action:",
        reply_markup=main_keyboard.as_markup(resize_keyboard=True)
    )


@router.message(F.text == "Add Filter")
async def add_filter_prompt(message: Message, state: FSMContext):
    """Начало добавления фильтра"""
    await state.clear()
    await message.answer("Please send the word you want to add to the filter:")
    await state.set_state(MainStates.waiting_for_filter_to_add)


@router.message(MainStates.waiting_for_filter_to_add)
async def add_filter_process(message: Message, state: FSMContext):
    """Обработка вводимого слова для фильтра."""
    user_id = message.chat.id
    word = message.text.strip().lower()
    if not word:
        await message.answer("Invalid input. Please try again.")
        return

    added = await add_user_filter_word(user_id=user_id, word=word)
    if added:
        await message.answer(f"Word '{word}' was successfully added to your filter!")
    else:
        await message.answer(f"The word '{word}' is already in your filter, or an error occurred.")
    await state.clear()


# Handler for "Remove Filter"
@router.message(F.text == "Remove Filter")
async def remove_filter_prompt(message: Message, state: FSMContext):
    """Начало удаления фильтра."""
    await state.clear()
    await message.answer("Please send the word you want to remove from the filter.")
    await state.set_state(MainStates.waiting_for_filter_to_remove)


@router.message(MainStates.waiting_for_filter_to_remove)
async def remove_filter_process(message: Message, state: FSMContext):
    """Обработка удаления слова из фильтра."""
    user_id = message.chat.id
    word = message.text.strip().lower()
    if not word:
        await message.answer("Invalid input. Please try again.")
        return

    removed = await remove_user_filter_word(user_id=user_id, word=word)
    if removed:
        await message.answer(f"Word '{word}' was successfully removed from your filter!")
    else:
        await message.answer(f"The word '{word}' was not found in your filter or an error occurred.")
    await state.clear()


# Handler for "Show Filters"
@router.message(F.text == "Show Filters")
async def show_filters(message: Message):
    """Показать текущие слова фильтров пользователя."""
    user_id = message.chat.id
    filter_words = await get_user_filter_words(user_id=user_id)
    if filter_words:
        filters_list = "\n".join(f"- {word}" for word in filter_words if word)
        await message.answer(f"Your current filter words are:\n{filters_list}")
    else:
        await message.answer("You have no filter words set yet.")
