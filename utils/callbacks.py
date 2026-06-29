"""Типизированные CallbackData для inline-кнопок (aiogram 3.x).

Использование классов вместо «голых» строк даёт автодополнение,
проверку типов и защиту от опечаток в callback_data.
"""
from __future__ import annotations

from aiogram.filters.callback_data import CallbackData


class PlayCallback(CallbackData, prefix="play"):
    """Нажатие 'Использовать попытку'."""


class CheckSubCallback(CallbackData, prefix="checksub"):
    """Нажатие 'Проверить подписку'."""


# === Админ-панель ===

class AdminCallback(CallbackData, prefix="admin"):
    """Открытие админ-панели."""


class AdminStatsCallback(CallbackData, prefix="admin_stats"):
    """Просмотр статистики."""


class AdminSetLinkCallback(CallbackData, prefix="admin_link"):
    """Смена ссылок на сервер."""


class AdminBroadcastCallback(CallbackData, prefix="admin_broadcast"):
    """Запуск рассылки."""


class AdminCancelCallback(CallbackData, prefix="admin_cancel"):
    """Отмена FSM-действия админа."""

    action: str  # какое действие отменяем (link / broadcast)
