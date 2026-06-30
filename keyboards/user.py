"""Inline-клавиатуры для обычных пользователей."""
from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from utils.callbacks import (
    PlayCallback,
    CheckSubCallback,
)


def play_keyboard() -> InlineKeyboardMarkup:
    """Кнопка 'Использовать попытку'."""
    kb = InlineKeyboardBuilder()
    kb.button(text="🎁 Использовать попытку", callback_data=PlayCallback().pack())
    kb.adjust(1)
    return kb.as_markup()


def check_sub_keyboard(channel_link: str | None = None) -> InlineKeyboardMarkup:
    """Кнопки 'Подписаться' (опционально) и 'Проверить подписку'."""
    kb = InlineKeyboardBuilder()
    if channel_link:
        kb.button(text="📢 Подписаться на канал", url=channel_link)
    kb.button(text="✅ Проверить подписку", callback_data=CheckSubCallback().pack())
    # По 1 кнопке в ряд — аккуратнее на мобильных.
    kb.adjust(1)
    return kb.as_markup()


def win_link_button(server_link: str) -> InlineKeyboardMarkup:
    """Кнопка-ссылка на приватный сервер Roblox."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🎮 Зайти на сервер", url=server_link)]
        ]
    )
def win_links_keyboard(server_links: list[str]) -> InlineKeyboardMarkup:
    """Клавиатура со ВСЕМИ ссылками на сервера (на случай если один полон)."""
    kb = InlineKeyboardBuilder()
    for i, link in enumerate(server_links, start=1):
        label = "🎮 Зайти на сервер" if len(server_links) == 1 else f"🎮 Сервер #{i}"
        kb.button(text=label, url=link)
    kb.adjust(1)
    return kb.as_markup()