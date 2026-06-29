"""Админ-панель: статистика, смена ссылок, рассылка.

Доступ только для ID из ADMIN_ID. FSM используется для ввода
новых ссылок и текста рассылки.
"""
from __future__ import annotations

import logging

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from config import Config
from database import Database
from filters.filters import IsAdmin
from keyboards.admin import admin_menu, cancel_keyboard
from services.settings import SettingsService
from states.admin import AdminStates
from utils.callbacks import (
    AdminBroadcastCallback,
    AdminCallback,
    AdminCancelCallback,
    AdminSetLinkCallback,
    AdminStatsCallback,
)
from utils.helpers import broadcast
from utils.messages import (
    ADMIN_BROADCAST_CONFIRM,
    ADMIN_BROADCAST_PROMPT,
    ADMIN_LINK_EMPTY,
    ADMIN_LINK_UPDATED,
    ADMIN_MENU_TEXT,
    ADMIN_NOT_AUTH,
    ADMIN_SET_LINK_PROMPT,
    ADMIN_STATS_TEXT,
    broadcast_report,
)

logger = logging.getLogger(__name__)

router = Router(name="admin")


# Все хендлеры этого роутера — только для админов.
# IsAdmin читает config из workflow_data в __call__.
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())


@router.message(Command("admin"))
async def cmd_admin(message: Message) -> None:
    """Открытие админ-панели."""
    await message.answer(ADMIN_MENU_TEXT, reply_markup=admin_menu(), parse_mode="HTML")


@router.callback_query(AdminCallback.filter())
async def cb_admin_menu(callback: CallbackQuery) -> None:
    """Открытие меню по inline-кнопке."""
    await callback.message.edit_text(
        ADMIN_MENU_TEXT, reply_markup=admin_menu(), parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(AdminStatsCallback.filter())
async def cb_stats(
    callback: CallbackQuery, db: Database, config: Config
) -> None:
    """Показ статистики: пользователи, победители, кол-во ссылок."""
    users = await db.count_users()
    winners = await db.count_winners()
    settings = SettingsService(db, config)
    links = await settings.get_server_links()
    text = ADMIN_STATS_TEXT.format(
        users=users, winners=winners, links=len(links)
    )
    await callback.message.edit_text(text, reply_markup=admin_menu(), parse_mode="HTML")
    await callback.answer()


# === СМЕНА ССЫЛОК ===

@router.callback_query(AdminSetLinkCallback.filter())
async def cb_set_link(
    callback: CallbackQuery, state: FSMContext
) -> None:
    """Начало смены ссылок — переводим в FSM-состояние ожидания ввода."""
    await state.set_state(AdminStates.waiting_for_link)
    await callback.message.edit_text(
        ADMIN_SET_LINK_PROMPT,
        reply_markup=cancel_keyboard("link"),
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(AdminStates.waiting_for_link)
async def on_link_input(
    message: Message, state: FSMContext, db: Database, config: Config
) -> None:
    """Сохранение новых ссылок из текстового ввода админа."""
    if message.text is None:
        await message.answer(ADMIN_LINK_EMPTY)
        return
    settings = SettingsService(db, config)
    links = await settings.set_server_links(message.text)
    await state.clear()
    if not links:
        await message.answer(ADMIN_LINK_EMPTY, reply_markup=admin_menu())
        return
    # Показываем итоговый список.
    listed = "\n".join(f"{i + 1}. {l}" for i, l in enumerate(links))
    await message.answer(
        ADMIN_LINK_UPDATED.format(count=len(links), links=listed),
        reply_markup=admin_menu(),
        parse_mode="HTML",
    )


# === РАССЫЛКА ===

@router.callback_query(AdminBroadcastCallback.filter())
async def cb_broadcast(
    callback: CallbackQuery, state: FSMContext
) -> None:
    """Начало рассылки — переводим в FSM-состояние ожидания текста."""
    await state.set_state(AdminStates.waiting_for_broadcast)
    await callback.message.edit_text(
        ADMIN_BROADCAST_PROMPT,
        reply_markup=cancel_keyboard("broadcast"),
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(AdminStates.waiting_for_broadcast)
async def on_broadcast_input(
    message: Message, state: FSMContext, db: Database, bot: Bot
) -> None:
    """Запуск рассылки по всем пользователям."""
    if message.text is None:
        await message.answer("❌ Пришли текст сообщения.")
        return
    text = message.text
    await state.clear()
    # Подтверждаем запуск.
    await message.answer(ADMIN_BROADCAST_CONFIRM, parse_mode="HTML")

    user_ids = await db.all_user_ids()
    total = len(user_ids)
    logger.info("Админ запустил рассылку: %d получателей", total)
    sent, failed = await broadcast(bot, user_ids, text, parse_mode="HTML")
    await message.answer(
        broadcast_report(total, sent, failed), parse_mode="HTML"
    )


# === ОТМЕНА FSM ===

@router.callback_query(AdminCancelCallback.filter(), AdminStates.waiting_for_link)
@router.callback_query(AdminCancelCallback.filter(), AdminStates.waiting_for_broadcast)
async def cb_cancel(
    callback: CallbackQuery, callback_data: AdminCancelCallback, state: FSMContext
) -> None:
    """Отмена ввода в FSM-состоянии — возврат в меню."""
    await state.clear()
    await callback.message.edit_text(
        ADMIN_MENU_TEXT, reply_markup=admin_menu(), parse_mode="HTML"
    )
    await callback.answer("Действие отменено")
