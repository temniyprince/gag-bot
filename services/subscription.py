"""Сервис проверки подписки на канал через Telegram Bot API.

Использует getChatMember — настоящая проверка, что пользователь состоит
в канале/группе. Бот должен быть админом канала с правом чтения участников.
"""
from __future__ import annotations

import logging

from aiogram import Bot
from aiogram.enums import ChatMemberStatus
from aiogram.exceptions import TelegramForbiddenError, TelegramAPIError

logger = logging.getLogger(__name__)


async def is_subscribed(bot: Bot, channel_id: int | str, user_id: int) -> bool:
    """Возвращает True, если пользователь подписан на канал.

    Подписанными считаем статусы: creator, administrator, member.
    Не подписаны: left, kicked, restricted (если restricted — считаем
    что не подписан, т.к. доступ ограничен).
    """
    try:
        member = await bot.get_chat_member(chat_id=channel_id, user_id=user_id)
    except TelegramForbiddenError:
        logger.error(
            "Нет доступа к каналу %s — добавьте бота админом канала.", channel_id
        )
        return False
    except TelegramAPIError as exc:
        # Любая другая ошибка API — считаем не подписанным, но логируем.
        logger.warning("Ошибка проверки подписки для %s: %s", user_id, exc)
        return False

    status = member.status
    return status in (
        ChatMemberStatus.CREATOR,
        ChatMemberStatus.ADMINISTRATOR,
        ChatMemberStatus.MEMBER,
    )
