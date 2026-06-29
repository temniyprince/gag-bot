"""Кастомные фильтры aiogram."""
from __future__ import annotations

from typing import Any

from aiogram.filters import BaseFilter
from aiogram.types import Message, CallbackQuery

from config import Config


class IsAdmin(BaseFilter):
    """Пропускает только пользователей из ADMIN_ID.

    Config берётся из workflow_data (прокидывается через Dispatcher(...)),
    поэтому фильтр инстанцируется без аргументов — aiogram сам подставит
    `config` в `__call__` из данных контекста.
    """

    async def __call__(
        self, event: Message | CallbackQuery, config: Config, *args: Any
    ) -> bool:
        # У CallbackQuery и Message есть .from_user; protect от None.
        user = getattr(event, "from_user", None)
        if user is None:
            return False
        return user.id in config.admin_ids
