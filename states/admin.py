"""FSM-состояния админ-панели (aiogram 3.x)."""
from __future__ import annotations

from aiogram.fsm.state import State, StatesGroup


class AdminStates(StatesGroup):
    """Состояния диалога админа."""

    waiting_for_link = State()  # ожидаем ввод новых ссылок на сервер
    waiting_for_broadcast = State()  # ожидаем текст рассылки
