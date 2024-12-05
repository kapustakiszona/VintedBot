import logging

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import selectinload

from data_base.base import connection
from data_base.models import User, Link, SentItem


@connection
async def add_user(session, user_id: int, is_premium: bool = False, is_admin: bool = False, is_banned: bool = False):
    try:
        user = await session.scalar(select(User).filter_by(user_id=user_id))
        if not user:
            new_user = User(user_id=user_id, is_premium=is_premium, is_admin=is_admin, is_banned=is_banned)
            session.add(new_user)
            await session.commit()
            logging.info(f"Зарегистрировал пользователя с ID {user_id}!")
            return None
        else:
            logging.info(f"Пользователь с ID {user_id} найден!")
            return user
    except SQLAlchemyError as e:
        logging.error(f"Ошибка при добавлении пользователя: {e}")
        await session.rollback()


@connection
async def add_link(session, user_id: int, link: str):
    try:
        user = await session.scalar(select(User).filter_by(user_id=user_id))
        if not user:
            logging.info(f"Пользователь с ID {user_id} найден!")
            return None
        max_link = 15 if user.is_premium else 2
        if len(user.links) >= max_link:
            logging.warning(f"Пользователь с ID {user_id} достиг лимита ссылок.")
            return False
        new_link = Link(user_id=user_id, link=link)
        session.add(new_link)
        await session.commit()
        logging.info(f"Ссылка '{new_link}' добавлена для пользователя с ID {user_id}.")
        return True
    except SQLAlchemyError as e:
        logging.error(f"Ошибка при добавлении ссылки: {e}")
        await session.rollback()


@connection
async def add_sent_item(session, item_id: int, link, title: str, img_url: str, item_url: str):
    try:
        sent_item_exists = await session.scalar(
            select(SentItem).filter_by(item_id=item_id, link_id=link.id).exists()
        )
        if sent_item_exists:
            logging.info(f"SentItem с ID {item_id} уже существует в Link ID {link.id}.")
            return None

        new_sent_item = SentItem(
            item_id=item_id,
            title=title,
            img_url=img_url,
            item_url=item_url,
            link_id=link.id
        )
        session.add(new_sent_item)
        await session.commit()
        logging.info(f"SentItem с ID {item_id} добавлен в Link ID {link.id}.")
    except SQLAlchemyError as e:
        logging.error(f"Ошибка при добавлении sent_item: {e}")
        await session.rollback()


@connection
async def get_all_users(session):
    try:
        result = await session.scalars(select(User))
        users = result.all()
        logging.info(f"Количество полученных пользователей: {len(users)}")
        return users
    except SQLAlchemyError as e:
        logging.error(f"Ошибка при получении списка Users: {e}")


@connection
async def delete_link(session, user_id: int, link: str):
    try:
        link_to_delete = await session.scalar(
            select(Link)
            .filter_by(user_id=user_id, link=link)
        )
        if not link_to_delete:
            logging.warning(f"Ссылка '{link}' для пользователя {user_id} не найдена.")
            return False

        await session.delete(link_to_delete)
        await session.commit()
        logging.info(f"Ссылка '{link}' успешно удалена для пользователя {user_id}.")
        return True
    except SQLAlchemyError as e:
        logging.error(f"Ошибка при удалении ссылки: {e}")
        await session.rollback()
        return False


@connection
async def set_user_premium(session, user_id: int):
    try:
        user = await session.scalar(select(User).filter_by(user_id=user_id))
        if not user:
            logging.warning(f"User with ID {user_id} not found.")
            return False

        user.is_premium = not user.is_premium
        await session.commit()
        await session.refresh(user)
        # В транзакции изменения будут зафиксированы автоматически
        logging.info(f"User with ID {user_id} premium status changed to {user.is_premium}.")
        return user.is_premium
    except SQLAlchemyError as e:
        logging.error(f"Error toggling premium status for user {user_id}: {e}")
        return None


@connection
async def set_user_ban(session, user_id: int):
    try:
        user = await session.scalar(select(User).filter_by(user_id=user_id))
        if not user:
            logging.warning(f"User with ID {user_id} not found.")
            return False

        user.is_banned = not user.is_banned
        await session.commit()
        await session.refresh(user)
        # В транзакции изменения будут зафиксированы автоматически
        logging.info(f"User with ID {user_id} Ban status changed to {user.is_banned}.")
        return user.is_banned
    except SQLAlchemyError as e:
        logging.error(f"Error toggling Ban status for user {user_id}: {e}")
        return None


@connection
async def get_users_link_list(session, user_id: int):
    try:
        user = await session.scalar(
            select(User).options(selectinload(User.links)).filter_by(user_id=user_id)
        )
        if not user:
            logging.info(f"Пользователь с ID {user_id} не найден.")
        return user
    except SQLAlchemyError as e:
        logging.error(f"Ошибка при получении пользователя с ID {user_id}: {e}")
        return None
