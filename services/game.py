"""Игровая логика: расчёт выигрыша и выдача ссылки на сервер.

SERVER_LINK может содержать несколько ссылок через запятую.
При выигрыше выбирается случайная из списка.
"""
from __future__ import annotations

import logging
import random

logger = logging.getLogger(__name__)


def roll(win_chance: float) -> bool:
    """Возвращает True с вероятностью win_chance (от 0 до 1)."""
    # random.random() ∈ [0, 1); вероятность попасть в [0, win_chance) = win_chance.
    return random.random() < win_chance


def pick_server_link(links: list[str]) -> str | None:
    """Выбирает случайную ссылку из списка.

    Возвращает None, если список пуст (например, админ ещё не задал ссылку).
    """
    if not links:
        logger.warning("Список ссылок на сервер пуст — нечего выдавать.")
        return None
    return random.choice(links)
