"""Inline-клавиатуры для админ-панели."""
from __future__ import annotations

from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from utils.callbacks import (
    AdminCallback,
    AdminStatsCallback,
    AdminSetLinkCallback,
    AdminBroadcastCallback,
    AdminCancelCallback,
)


def admin_menu() -> InlineKeyboardMarkup:
    """Главное меню админ-панели."""
    kb = InlineKeyboardBuilder()
    kb.button(text="📊 Статистика", callback_data=AdminStatsCallback().pack())
    kb.button(text="🔗 Изменить ссылку", callback_data=AdminSetLinkCallback().pack())
    kb.button(text="📣 Рассылка", callback_data=AdminBroadcastCallback().pack())
    kb.adjust(1)
    return kb.as_markup()


def cancel_keyboard(action: str) -> InlineKeyboardMarkup:
    """Кнопка отмены для FSM-состояний админа."""
    kb = InlineKeyboardBuilder()
    kb.button(text="❌ Отмена", callback_data=AdminCancelCallback(action=action).pack())
    kb.adjust(1)
    return kb.as_markup()
