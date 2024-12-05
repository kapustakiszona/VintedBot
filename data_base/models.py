from __future__ import annotations

from sqlalchemy import Boolean, Integer, ForeignKey, BigInteger, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from data_base.database import Base


class User(Base):
    __tablename__ = "users"
    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, nullable=False)  # Telegram user_id
    is_premium: Mapped[bool] = mapped_column(Boolean, default=False)  # Премиум статус
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)  # Администратор
    is_banned: Mapped[bool] = mapped_column(Boolean, default=False)  # Забанен
    links: Mapped[list["Link"]] = relationship(
        "Link", back_populates="user", cascade="all, delete-orphan", lazy= "selectin"
    ) # Список ссылок пользователя


class Link(Base):
    __tablename__ = "links"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)  # Уникальный ID ссылки
    user_id: Mapped[int] = mapped_column(ForeignKey("users.user_id"), nullable=False)  # ID пользователя
    link: Mapped[str] = mapped_column(String, nullable=True)  # URL ссылки
    # Связь с таблицей SentItem
    sent_items: Mapped[list["SentItem"]] = relationship(
        "SentItem", back_populates="link", cascade="all, delete-orphan"
    )
    user: Mapped["User"] = relationship("User", back_populates="links")# Связь с таблицей User


class SentItem(Base):
    __tablename__ = "sent_items"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)  # Уникальный ID записи
    item_id: Mapped[int] = mapped_column(BigInteger, nullable=False, unique=True)  # Уникальный ID товара
    title: Mapped[str] = mapped_column(String, nullable=False)  # Название товара
    img_url: Mapped[str] = mapped_column(String, nullable=False)  # URL изображения
    item_url: Mapped[str] = mapped_column(String, nullable=False)  # URL товара
    link_id: Mapped[int] = mapped_column(ForeignKey("links.id"), nullable=False)  # Связь с таблицей ссылок
    link: Mapped["Link"] = relationship("Link", back_populates="sent_items")# Связь с таблицей Link