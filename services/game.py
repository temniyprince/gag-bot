"""Игровая логика: расчёт выигрыша и выдача ссылки на сервер.
 
SERVER_LINK может содержать несколько ссылок через запятую.
При выигрыше выдаются ВСЕ ссылки из списка (на случай если один сервер полон).
"""
from __future__ import annotations
 
import logging
import random
 
logger = logging.getLogger(__name__)
 
 
def roll(win_chance: float) -> bool:
    """Возвращает True с вероятностью win_chance (от 0 до 1)."""
    return random.random() < win_chance
 
 
def pick_server_link(links: list[str]) -> str | None:
    """Выбирает случайную ссылку из списка (оставлено для совместимости)."""
    if not links:
        logger.warning("Список ссылок на сервер пуст — нечего выдавать.")
        return None
    return random.choice(links)
 
 
def get_all_server_links(links: list[str]) -> list[str]:
    """Возвращает все ссылки на сервера для выдачи победителю."""
    if not links:
        logger.warning("Список ссылок на сервер пуст — нечего выдавать.")
        return []
    return list(links)
