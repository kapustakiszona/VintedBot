import asyncio
import logging

from create_bot import bot, dp, admins
from data_base.base import create_tables
from aiogram.types import BotCommand, BotCommandScopeDefault
from handlers.admin_commands import admin_router
from handlers.main_commands import router
from scraper.scraper import periodic_check


# Функция, которая настроит командное меню (дефолтное для всех пользователей)
async def set_commands():
    commands = [BotCommand(command='start', description='Start')]
    await bot.set_my_commands(commands, BotCommandScopeDefault())


# Функция, которая выполнится когда бот запустится
async def start_bot():
    await set_commands()
    await create_tables()
    for admin_id in admins:
        try:
            await bot.send_message(admin_id, f'Bot started.')
        except Exception as e:
            logging.error(f"Ошибка при отправке сообщения админу {admin_id}: {e}")

    # Запускаем периодическую проверку новых товаров
    asyncio.create_task(periodic_check(bot))


# Функция, которая выполнится когда бот завершит свою работу
async def stop_bot():
    try:
        for admin_id in admins:
            await bot.send_message(admin_id, 'Bot stopped')
    except Exception as e:
        logging.error(f"Ошибка при отправке сообщения админу при остановке бота: {e}")


async def main():
    # регистрация роутеров
    dp.include_router(router)
    dp.include_router(admin_router)

    # регистрация функций
    dp.startup.register(start_bot)
    dp.shutdown.register(stop_bot)
    # запуск бота в режиме long polling при запуске бот очищает все обновления, которые были за его моменты бездействия
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
