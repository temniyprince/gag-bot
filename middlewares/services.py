"""Middleware для инъекции общих сервисов в хендлеры.

Через workflow_data мы прокидываем db и config в каждый обработчик,
чтобы не тянуть глобальные синглтоны и было удобно тестировать.
"""
from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

from config import Config
from database import Database

logger = logging.getLogger(__name__)


class ServicesMiddleware(BaseMiddleware):
    """Добавляет `db` и `config` в словарь данных каждого обработчика."""

    def __init__(self, db: Database, config: Config) -> None:
        self.db = db
        self.config = config

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        data["db"] = self.db
        data["config"] = self.config
        return await handler(event, data)
