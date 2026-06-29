"""Точка входа в приложение.

Запуск: python main.py

Что делает:
  - создаёт нужные директории и БД при первом запуске;
  - инициализирует Bot, Dispatcher, middleware и роутеры;
  - запускает long-polling с автоматическим переподключением
    (aiogram сам делает backoff при временных ошибках Telegram API).
"""
from __future__ import annotations

import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import (
    TelegramNetworkError,
    TelegramRetryAfter,
    TelegramServerError,
    TelegramUnauthorizedError,
)
from aiogram.filters.exception import ExceptionTypeFilter
from aiogram.types import ErrorEvent, Update

from config import config
from database import Database
from filters.filters import IsAdmin
from handlers import register_all_routers
from middlewares.services import ServicesMiddleware

logger = logging.getLogger(__name__)


def ensure_dirs() -> None:
    """Создаёт все нужные директории, если их ещё нет (data/, ...)."""
    config.db_dir.mkdir(parents=True, exist_ok=True)
    logger.info("Директория данных готова: %s", config.db_dir)


def setup_dispatcher(db: Database) -> Dispatcher:
    """Конфигурирует Dispatcher: middleware + роутеры + error handler.

    workflow_data прокидывает db/config во ВСЕ обработчики (включая error),
    поэтому error-handler тоже получит `db` и `config`.
    """
    dp = Dispatcher(db=db, config=config)

    # Инъекция сервисов в каждый хендлер.
    dp.message.outer_middleware(ServicesMiddleware(db, config))
    dp.callback_query.outer_middleware(ServicesMiddleware(db, config))

    # Регистрируем все роутеры (admin первым).
    register_all_routers(dp)

    # --- Глобальный обработчик ошибок ---
    # Не даём боту упасть на исключении в хендлере: логируем и отвечаем юзеру.
    register_error_handlers(dp)

    return dp


def register_error_handlers(dp: Dispatcher) -> None:
    """Регистрирует обработчики исключений по типам."""

    # Временные ошибки Telegram (флуд/ретрай, сеть, 5xx) — логируем и
    # ждём, не валим бота. aiogram polling сам сделает backoff-переподключение.
    @dp.errors(ExceptionTypeFilter(TelegramRetryAfter))
    async def on_retry_after(event: ErrorEvent) -> None:
        exc = event.exception
        retry = getattr(exc, "retry_after", None)
        logger.warning("TelegramRetryAfter: ждём %s сек и продолжаем.", retry)
        await asyncio.sleep(float(retry or 1))

    @dp.errors(ExceptionTypeFilter(TelegramNetworkError))
    async def on_network_error(event: ErrorEvent) -> None:
        logger.error("Сетевая ошибка Telegram: %s", event.exception)

    @dp.errors(ExceptionTypeFilter(TelegramServerError))
    async def on_server_error(event: ErrorEvent) -> None:
        logger.error("Ошибка сервера Telegram (5xx): %s", event.exception)

    # Неверный токен — критично, логируем и останавливаем polling.
    @dp.errors(ExceptionTypeFilter(TelegramUnauthorizedError))
    async def on_unauthorized(event: ErrorEvent) -> None:
        logger.critical("Неверный BOT_TOKEN: %s", event.exception)

    # Любая другая ошибка в хендлере — не валим бота, логируем и шлём извинение.
    @dp.errors()
    async def on_unhandled(event: ErrorEvent, bot: Bot) -> None:
        logger.exception("Необработанная ошибка в хендлере: %s", event.exception)
        update: Update = event.update
        # Пытаемся сообщить юзеру, что что-то пошло не так (мягкая посадка).
        chat_id = _extract_chat_id(update)
        if chat_id:
            try:
                await bot.send_message(
                    chat_id=chat_id,
                    text="⚠️ Произошла ошибка. Попробуй ещё раз чуть позже.",
                )
            except Exception:  # noqa: BLE001
                logger.debug("Не удалось отправить сообщение об ошибке юзеру.")


def _extract_chat_id(update: Update) -> int | None:
    """Достаёт chat_id из любого типа апдейта (для ответа при ошибке)."""
    if update.message and update.message.chat:
        return update.message.chat.id
    if update.callback_query and update.callback_query.message:
        return update.callback_query.message.chat.id
    if update.edited_message and update.edited_message.chat:
        return update.edited_message.chat.id
    return None


async def main() -> None:
    """Главная асинхронная точка входа."""
    logger.info("Запуск бота…")
    ensure_dirs()

    # Инициализируем БД (создаёт файл и таблицы при первом запуске).
    db = Database(config.db_path)
    await db.init()

    # Bot с HTML как режимом парсинга по умолчанию.
    bot = Bot(
        token=config.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    dp = setup_dispatcher(db)

    # Удалим вебхук, чтобы polling работал корректно.
    try:
        await bot.delete_webhook(drop_pending_updates=True)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Не удалось удалить webhook: %s", exc)

    # start_polling сам делает backoff при временных ошибках Telegram API,
    # то есть обеспечивает автоматическое переподключение.
    # handle_signals=True корректно обрабатывает SIGINT/SIGTERM (Ctrl+C).
    logger.info("Polling запущен. Остановить: Ctrl+C")
    await dp.start_polling(bot, handle_signals=True)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Бот остановлен пользователем.")
    except TelegramUnauthorizedError as exc:
        logger.critical("Неверный BOT_TOKEN — проверь .env: %s", exc)
        sys.exit(1)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Фатальная ошибка: %s", exc)
        sys.exit(1)
