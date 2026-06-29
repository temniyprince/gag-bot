"""Точка входа в приложение.

Запуск: python main.py

Что делает:
  - создаёт нужные директории и БД при первом запуске;
  - инициализирует Bot, Dispatcher, middleware и роутеры;
  - запускает фейковый HTTP-сервер (для Render/хостингов);
  - запускает long-polling с автоматическим переподключением.
"""
from __future__ import annotations

import asyncio
import logging
import os
import sys

from aiohttp import web
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

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def ensure_dirs() -> None:
    """Создаёт все нужные директории, если их ещё нет."""
    config.db_dir.mkdir(parents=True, exist_ok=True)
    logger.info("Директория данных готова: %s", config.db_dir)


def setup_dispatcher(db: Database) -> Dispatcher:
    """Конфигурирует Dispatcher: middleware + роутеры + error handler."""
    dp = Dispatcher(db=db, config=config)

    # Инъекция сервисов в каждый хендлер
    dp.message.outer_middleware(ServicesMiddleware(db, config))
    dp.callback_query.outer_middleware(ServicesMiddleware(db, config))

    # Регистрируем все роутеры (admin первым)
    register_all_routers(dp)

    # Глобальный обработчик ошибок
    register_error_handlers(dp)

    return dp


def register_error_handlers(dp: Dispatcher) -> None:
    """Регистрирует обработчики исключений по типам."""

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

    @dp.errors(ExceptionTypeFilter(TelegramUnauthorizedError))
    async def on_unauthorized(event: ErrorEvent) -> None:
        logger.critical("Неверный BOT_TOKEN: %s", event.exception)

    @dp.errors()
    async def on_unhandled(event: ErrorEvent, bot: Bot) -> None:
        logger.exception("Необработанная ошибка в хендлере: %s", event.exception)
        update: Update = event.update
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
    """Достаёт chat_id из любого типа апдейта."""
    if update.message and update.message.chat:
        return update.message.chat.id
    if update.callback_query and update.callback_query.message:
        return update.callback_query.message.chat.id
    if update.edited_message and update.edited_message.chat:
        return update.edited_message.chat.id
    return None


async def start_health_server() -> None:
    """Запускает простой HTTP-сервер для Render (чтобы не засыпал)."""
    async def health(request: web.Request) -> web.Response:
        return web.Response(text="OK")

    app = web.Application()
    app.router.add_get("/", health)
    app.router.add_get("/health", health)

    runner = web.AppRunner(app)
    await runner.setup()

    port = int(os.environ.get("PORT", 8000))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info("Health-check сервер запущен на порту %s", port)


async def main() -> None:
    """Главная асинхронная точка входа."""
    logger.info("Запуск бота…")
    ensure_dirs()

    # Инициализируем БД
    db = Database(config.db_path)
    await db.init()

    # Bot с HTML как режимом парсинга по умолчанию
    bot = Bot(
        token=config.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    dp = setup_dispatcher(db)

    # Удалим вебхук, чтобы polling работал корректно
    try:
        await bot.delete_webhook(drop_pending_updates=True)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Не удалось удалить webhook: %s", exc)

    # Запускаем health-check сервер для Render
    await start_health_server()

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
