"""Вспомогательные функции."""
from __future__ import annotations

import asyncio
import logging
from typing import Iterable

from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError, TelegramAPIError

logger = logging.getLogger(__name__)


async def safe_send_message(
    bot: Bot, chat_id: int, text: str, parse_mode: str = "HTML"
) -> bool:
    """Безопасная отправка одного сообщения.

    Возвращает True при успехе, False при ошибке (юзер заблокировал бота,
    чат не существует и т.п.). Ошибки логируются, но не пробрасываются.
    """
    try:
        await bot.send_message(chat_id=chat_id, text=text, parse_mode=parse_mode)
        return True
    except TelegramForbiddenError:
        # Юзер заблокировал бота — это нормально, просто пропускаем.
        return False
    except TelegramAPIError as exc:
        logger.warning("Не удалось отправить сообщение %s: %s", chat_id, exc)
        return False


async def broadcast(
    bot: Bot,
    user_ids: Iterable[int],
    text: str,
    parse_mode: str = "HTML",
    delay: float = 0.05,
) -> tuple[int, int]:
    """Рассылка по списку ID с задержкой (беречь лимиты Telegram).

    Возвращает (успешно, ошибок). Задержка между отправками — delay секунд,
    чтобы не упереться в rate-limit (≈30 msg/sec для бота).
    """
    sent = 0
    failed = 0
    ids = list(user_ids)
    for chat_id in ids:
        ok = await safe_send_message(bot, chat_id, text, parse_mode)
        if ok:
            sent += 1
        else:
            failed += 1
        # Небольшая задержка — бережём лимиты Telegram.
        if delay > 0:
            await asyncio.sleep(delay)
    logger.info("Рассылка завершена: отправлено %d, ошибок %d", sent, failed)
    return sent, failed
