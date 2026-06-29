"""Хендлеры для обычных пользователей: /start, игра, проверка подписки.

Логика:
  1. /start — создаём пользователя с бесплатными попытками (один раз).
  2. «Использовать попытку» — roll(25%); выигрыш → ссылка, проигрыш → кнопка подписки.
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
    win_link_button,
)
from services.game import pick_server_link, roll
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
    # Получаем (или создаём) запись пользователя.
    user = await db.get_user(user_id)
    if user is None:
        user = await db.create_user(user_id, config.free_attempts)
        logger.info("Новый пользователь: %s (попыток: %d)", user_id, user.attempts)

    # Если есть попытки — кнопка игры; иначе — сразу зовём подписаться.
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
        # На всякий случай создадим (например, если юзер нажал старую кнопку).
        user = await db.create_user(user_id, config.free_attempts)

    if user.attempts <= 0:
        # Попыток нет — зовём подписаться.
        await callback.message.edit_text(
            OUT_OF_ATTEMPTS_TEXT,
            reply_markup=check_sub_keyboard(config.channel_link),
        )
        await callback.answer()
        return

    # Списываем одну попытку.
    await db.decrement_attempts(user_id)

    # Бросаем «кубик»: 25% шанс выигрыша.
    if roll(config.win_chance):
        # Выигрыш: выдаём случайную ссылку из списка.
        settings = SettingsService(db, config)
        links = await settings.get_server_links()
        link = pick_server_link(links)
        if link is None:
            # Ссылки не заданы — извиняемся (админ должен настроить).
            await callback.message.edit_text(NO_LINK_TEXT, reply_markup=None)
        else:
            await callback.message.edit_text(
                WIN_TEXT.format(link=link),
                reply_markup=win_link_button(link),
                parse_mode="HTML",
                disable_web_page_preview=False,
            )
        # Отмечаем победителем (один флаг на пользователя — выигрывал ли хоть раз).
        await db.mark_winner(user_id)
        logger.info("Пользователь %s ВЫИГРАЛ — выдана ссылка", user_id)
    else:
        # Проигрыш: показываем кнопку проверки подписки для доп. попытки.
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

    # Подписан. Бонус можно выдать только один раз.
    if user.bonus_received:
        await callback.answer(BONUS_ALREADY_TEXT, show_alert=True)
        return

    # Выдаём ровно одну дополнительную попытку.
    await db.add_attempt(user_id)
    logger.info("Пользователю %s выдана бонусная попытка за подписку", user_id)
    # Обновляем клавиатуру: теперь можно играть.
    await callback.message.edit_text(
        BONUS_GRANTED_TEXT, reply_markup=play_keyboard(), parse_mode="HTML"
    )
    await callback.answer()
