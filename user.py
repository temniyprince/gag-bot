"""Хендлеры для обычных пользователей: /start, игра, проверка подписки.

Логика:
  1. /start — создаём пользователя с бесплатными попытками (один раз).
  2. «Использовать попытку» — roll(25%); выигрыш → ссылка(и), проигрыш → кнопка подписки.
  3. «Проверить подписку» — getChatMember; подписан и бонус не выдан → +1 попытка.
"""
from __future__ import annotations

import logging

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from config import Config
from database import Database
from keyboards.user import (
    check_sub_keyboard,
    play_keyboard,
    win_links_keyboard,
)
from services.game import get_all_server_links, roll
from services.settings import SettingsService
from services.subscription import is_subscribed
from utils.callbacks import CheckSubCallback, PlayCallback
from utils.messages import (
    BONUS_ALREADY_TEXT,
    BONUS_GRANTED_TEXT,
    LOSE_TEXT,
    NO_ATTEMPTS_TEXT,
    NO_LINK_TEXT,
    NOT_SUBSCRIBED_TEXT,
    OUT_OF_ATTEMPTS_TEXT,
    START_TEXT,
    WIN_TEXT,
)

logger = logging.getLogger(__name__)

router = Router(name="user")


@router.message(Command("start"))
async def cmd_start(message: Message, db: Database, config: Config) -> None:
    """Обработка /start. Создаёт пользователя, если его ещё нет."""
    if message.from_user is None:
        return
    user_id = message.from_user.id
    user = await db.get_user(user_id)
    if user is None:
        user = await db.create_user(user_id, config.free_attempts)
        logger.info("Новый пользователь: %s (попыток: %d)", user_id, user.attempts)

    if user.attempts > 0:
        await message.answer(
            START_TEXT.format(name=message.from_user.first_name or "друг"),
            reply_markup=play_keyboard(),
            parse_mode="HTML",
        )
    else:
        await message.answer(NO_ATTEMPTS_TEXT, reply_markup=check_sub_keyboard(config.channel_link))


@router.callback_query(PlayCallback.filter())
async def cb_play(
    callback: CallbackQuery,
    callback_data: PlayCallback,
    db: Database,
    config: Config,
    bot: Bot,
) -> None:
    """Обработка нажатия «Использовать попытку»."""
    if callback.from_user is None:
        return
    user_id = callback.from_user.id
    user = await db.get_user(user_id)
    if user is None:
        user = await db.create_user(user_id, config.free_attempts)

    if user.attempts <= 0:
        await callback.message.edit_text(
            OUT_OF_ATTEMPTS_TEXT,
            reply_markup=check_sub_keyboard(config.channel_link),
        )
        await callback.answer()
        return

    await db.decrement_attempts(user_id)

    if roll(config.win_chance):
        # Выигрыш: выдаём ВСЕ ссылки на сервера (если один полон — пробуют другой).
        settings = SettingsService(db, config)
        links = await settings.get_server_links()
        all_links = get_all_server_links(links)
        if not all_links:
            await callback.message.edit_text(NO_LINK_TEXT, reply_markup=None)
        else:
            await callback.message.edit_text(
                WIN_TEXT,
                reply_markup=win_links_keyboard(all_links),
                parse_mode="HTML",
            )
        await db.mark_winner(user_id)
        logger.info("Пользователь %s ВЫИГРАЛ — выданы ссылки", user_id)
    else:
        await callback.message.edit_text(
            LOSE_TEXT, reply_markup=check_sub_keyboard(config.channel_link)
        )
        logger.info("Пользователь %s проиграл", user_id)

    await callback.answer()


@router.callback_query(CheckSubCallback.filter())
async def cb_check_sub(
    callback: CallbackQuery,
    callback_data: CheckSubCallback,
    db: Database,
    config: Config,
    bot: Bot,
) -> None:
    """Обработка нажатия «Проверить подписку».

    Проверяем getChatMember; если подписан и бонус ещё не выдавался — даём +1.
    """
    if callback.from_user is None:
        return
    user_id = callback.from_user.id
    user = await db.get_user(user_id)
    if user is None:
        user = await db.create_user(user_id, config.free_attempts)

    subscribed = await is_subscribed(bot, config.channel_id, user_id)
    if not subscribed:
        await callback.answer(NOT_SUBSCRIBED_TEXT, show_alert=True)
        return

    if user.bonus_received:
        await callback.answer(BONUS_ALREADY_TEXT, show_alert=True)
        return

    await db.add_attempt(user_id)
    logger.info("Пользователю %s выдана бонусная попытка за подписку", user_id)
    await callback.message.edit_text(
        BONUS_GRANTED_TEXT, reply_markup=play_keyboard(), parse_mode="HTML"
    )
    await callback.answer()
