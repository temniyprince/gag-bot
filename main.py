"""Точка входа в приложение.

Запуск: python main.py

Режим работы:
  - Если задана переменная WEBHOOK_URL — запускается в webhook режиме (для Render)
  - Если нет — запускается в polling режиме (для локальной разработки)
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
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

from config import config
from database import Database
from handlers import register_all_routers
from middlewares.services import ServicesMiddleware

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logging.getLogger("aiogram.event").setLevel(logging.INFO)
logging.getLogger("aiohttp").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

# Путь для webhook (секретный, чтобы никто посторонний не слал запросы)
WEBHOOK_PATH = "/webhook"


def ensure_dirs() -> None:
    config.db_dir.mkdir(parents=True, exist_ok=True)
    logger.info("Директория данных готова: %s", config.db_dir)


def setup_dispatcher(db: Database) -> Dispatcher:
    dp = Dispatcher(db=db, config=config)
    dp.message.outer_middleware(ServicesMiddleware(db, config))
    dp.callback_query.outer_middleware(ServicesMiddleware(db, config))
    register_all_routers(dp)
    register_error_handlers(dp)
    return dp


def register_error_handlers(dp: Dispatcher) -> None:
    @dp.errors(ExceptionTypeFilter(TelegramRetryAfter))
    async def on_retry_after(event: ErrorEvent) -> None:
        retry = getattr(event.exception, "retry_after", None)
        logger.warning("TelegramRetryAfter: ждём %s сек.", retry)
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
        logger.exception("Необработанная ошибка: %s", event.exception)
        update: Update = event.update
        chat_id = _extract_chat_id(update)
        if chat_id:
            try:
                await bot.send_message(chat_id=chat_id, text="⚠️ Произошла ошибка. Попробуй ещё раз чуть позже.")
            except Exception:
                pass


def _extract_chat_id(update: Update) -> int | None:
    if update.message and update.message.chat:
        return update.message.chat.id
    if update.callback_query and update.callback_query.message:
        return update.callback_query.message.chat.id
    if update.edited_message and update.edited_message.chat:
        return update.edited_message.chat.id
    return None


async def run_webhook(bot: Bot, dp: Dispatcher) -> None:
    """Запуск в webhook режиме — для Render и других хостингов."""
    webhook_url = os.environ["WEBHOOK_URL"].rstrip("/") + WEBHOOK_PATH
    port = int(os.environ.get("PORT", 8000))

    # Регистрируем webhook в Telegram
    await bot.set_webhook(
        url=webhook_url,
        drop_pending_updates=True,
    )
    logger.info("Webhook установлен: %s", webhook_url)

    # Создаём aiohttp приложение
    app = web.Application()

    # Хендлер для health check (чтобы Render видел что сервис живой)
    async def health(request: web.Request) -> web.Response:
        return web.Response(text="OK")

    app.router.add_get("/", health)
    app.router.add_get("/health", health)

    # Подключаем aiogram к aiohttp
    SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path=WEBHOOK_PATH)
    setup_application(app, dp, bot=bot)

    # Запускаем сервер
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

    logger.info("Webhook сервер запущен на порту %s. Остановить: Ctrl+C", port)

    # Держим сервер запущенным
    try:
        await asyncio.Event().wait()
    finally:
        await runner.cleanup()
        await bot.delete_webhook()


async def run_polling(bot: Bot, dp: Dispatcher) -> None:
    """Запуск в polling режиме — для локальной разработки."""
    try:
        await bot.delete_webhook(drop_pending_updates=True)
    except Exception as exc:
        logger.warning("Не удалось удалить webhook: %s", exc)

    logger.info("Polling запущен. Остановить: Ctrl+C")
    await dp.start_polling(bot, handle_signals=True)


async def main() -> None:
    logger.info("Запуск бота…")
    ensure_dirs()

    db = Database(config.db_path)
    await db.init()

    bot = Bot(
        token=config.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    dp = setup_dispatcher(db)

    webhook_url = os.environ.get("WEBHOOK_URL", "").strip()
    if webhook_url:
        logger.info("Режим: WEBHOOK (%s)", webhook_url)
        await run_webhook(bot, dp)
    else:
        logger.info("Режим: POLLING (локальный запуск)")
        await run_polling(bot, dp)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Бот остановлен пользователем.")
    except TelegramUnauthorizedError as exc:
        logger.critical("Неверный BOT_TOKEN — проверь .env: %s", exc)
        sys.exit(1)
    except Exception as exc:
        logger.exception("Фатальная ошибка: %s", exc)
        sys.exit(1)
