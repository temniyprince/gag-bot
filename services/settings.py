"""Сервис настроек: хранит ссылки на сервер в БД.

Позволяет админу менять ссылки через админ-панель без правки кода.
Источником правды является БД; если в БД пусто — берём из .env (config).
"""
from __future__ import annotations

import logging

from config import Config
from database import Database

logger = logging.getLogger(__name__)

# Ключ в таблице settings для ссылок на сервер.
SERVER_LINKS_KEY = "server_links"


class SettingsService:
    """Читает/пишет настройки из БД с откатом к .env по умолчанию."""

    def __init__(self, db: Database, config: Config) -> None:
        self._db = db
        self._config = config

    async def get_server_links(self) -> list[str]:
        """Список ссылок на сервер: из БД, иначе из .env."""
        raw = await self._db.get_setting(SERVER_LINKS_KEY)
        if raw:
            links = [s.strip() for s in raw.split(",") if s.strip()]
            if links:
                return links
        # Откат к значениям из .env.
        return list(self._config.server_links)

    async def set_server_links(self, raw: str) -> list[str]:
        """Сохраняет новые ссылки (строка через запятую) в БД.

        Возвращает распарсенный список для отображения админу.
        """
        links = [s.strip() for s in raw.split(",") if s.strip()]
        # Сохраняем как есть — чтобы админ мог видеть свой ввод.
        await self._db.set_setting(SERVER_LINKS_KEY, raw.strip())
        logger.info("Ссылки на сервер обновлены через админку: %d шт.", len(links))
        return links
