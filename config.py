"""Конфигурация приложения.

Загружает все настройки из переменных окружения (.env).
Не содержит хардкода секретов и абсолютных путей — всё берётся из env.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final

from dotenv import load_dotenv

# --- Загрузка .env ---
# base_dir указывает на корень проекта (где лежит main.py).
# Используем относительные пути — никаких абсолютных.
BASE_DIR: Final[Path] = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

# --- Логирование ---
# Настраиваем до использования конфига, чтобы видеть проблемы загрузки.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
# aiogram очень шумит на DEBUG; оставляем WARNING для нижележащего aiohttp.
logging.getLogger("aiogram.event").setLevel(logging.INFO)
logging.getLogger("aiohttp").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


def _parse_admin_ids(raw: str) -> set[int]:
    """Парсит строку ADMIN_ID (через запятую) во множество ID админов."""
    ids: set[int] = set()
    if not raw:
        return ids
    for part in raw.split(","):
        part = part.strip()
        if part.isdigit():
            ids.add(int(part))
    return ids


def _parse_server_links(raw: str) -> list[str]:
    """Парсит SERVER_LINK: поддерживает одну ссылку или список через запятую."""
    if not raw:
        return []
    return [link.strip() for link in raw.split(",") if link.strip()]


def _coerce_id(raw: str) -> int | str:
    """Преобразует CHANNEL_ID: число → int, иначе строка (@username)."""
    raw = raw.strip().lstrip("-") if raw else ""
    if raw.isdigit():
        # Возвращаем с исходным знаком (приватные чаты имеют отрицательный ID).
        return int(raw.strip()) if not raw.strip().startswith("-") else -int(raw)
    return raw.strip()


@dataclass(frozen=True)
class Config:
    """Контейнер всех настроек приложения."""

    # --- Токен и админы ---
    bot_token: str
    admin_ids: frozenset[int]

    # --- Канал подписки ---
    channel_id: int | str
    channel_link: str | None

    # --- Ссылки на сервер Roblox (по умолчанию из .env) ---
    # Хранятся как список; БД может переопределять значение через админку.
    server_links: tuple[str, ...]

    # --- Игровая логика ---
    win_chance: float
    free_attempts: int

    # --- Пути ---
    db_path: Path

    @property
    def db_dir(self) -> Path:
        """Директория базы данных (создаётся автоматически при запуске)."""
        return self.db_path.parent


def load_config() -> Config:
    """Собирает Config из переменных окружения с валидацией."""
    token = os.getenv("BOT_TOKEN", "").strip()
    if not token:
        logger.critical("BOT_TOKEN не задан в .env — бот не сможет запуститься.")
        raise RuntimeError("BOT_TOKEN is required")

    # Путь к базе: data/bot.db относительно корня проекта.
    db_path = BASE_DIR / "data" / "bot.db"

    win_chance_raw = os.getenv("WIN_CHANCE", "0.25")
    try:
        win_chance = float(win_chance_raw)
    except ValueError:
        logger.warning("WIN_CHANCE=%r некорректен, использую 0.25", win_chance_raw)
        win_chance = 0.25
    # Нормализуем в диапазон [0, 1].
    win_chance = max(0.0, min(1.0, win_chance))

    free_attempts_raw = os.getenv("FREE_ATTEMPTS", "1")
    try:
        free_attempts = int(free_attempts_raw)
    except ValueError:
        logger.warning("FREE_ATTEMPTS=%r некорректен, использую 1", free_attempts_raw)
        free_attempts = 1
    free_attempts = max(0, free_attempts)

    return Config(
        bot_token=token,
        admin_ids=frozenset(_parse_admin_ids(os.getenv("ADMIN_ID", ""))),
        channel_id=_coerce_id(os.getenv("CHANNEL_ID", "")),
        channel_link=os.getenv("CHANNEL_LINK") or None,
        server_links=tuple(_parse_server_links(os.getenv("SERVER_LINK", ""))),
        win_chance=win_chance,
        free_attempts=free_attempts,
        db_path=db_path,
    )


# Глобальный экземпляр конфига — импортируется другими модулями.
config: Config = load_config()
