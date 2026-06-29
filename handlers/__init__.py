"""Пакет обработчиков (хендлеров) aiogram."""
from __future__ import annotations

from aiogram import Dispatcher

from . import user, admin


def register_all_routers(dp: Dispatcher) -> None:
    """Регистрирует все роутеры в диспетчере.

    Порядок важен: админский роутер подключаем ПЕРВЫМ, чтобы админ-фильтр
    перехватывал админские команды раньше пользовательских.
    """
    dp.include_router(admin.router)
    dp.include_router(user.router)
