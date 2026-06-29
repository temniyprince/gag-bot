"""Слой доступа к данным (SQLite через aiosqlite).

Хранит пользователей и настройки. БД и таблицы создаются автоматически
при первом запуске — никаких ручных миграций не требуется.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Iterable

import aiosqlite

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class User:
    """Модель пользователя для удобной передачи между слоями."""

    telegram_id: int
    attempts: int
    bonus_received: bool
    has_won: bool


class Database:
    """Асинхронная обёртка над SQLite.

    Каждый метод открывает своё соединение (aiosqlite прозрачно пулирует
    на уровне ОС). Это упрощает логику и избегает гонок при долгой рассылке.
    """

    def __init__(self, db_path) -> None:
        # Принимаем str или Path — приведём к строке для aiosqlite.
        self._db_path = str(db_path)

    async def init(self) -> None:
        """Создаёт БД и таблицы, если их ещё нет."""
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute("PRAGMA journal_mode=WAL")  # надёжнее при сбоях
            await db.execute("PRAGMA foreign_keys=ON")
            # --- Пользователи ---
            # attempts          — оставшиеся попытки
            # bonus_received    — получал ли доп. попытку за подписку (0/1)
            # has_won           — выигрывал ли хотя бы раз (0/1)
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    telegram_id    INTEGER PRIMARY KEY,
                    attempts       INTEGER NOT NULL DEFAULT 0,
                    bonus_received INTEGER NOT NULL DEFAULT 0,
                    has_won        INTEGER NOT NULL DEFAULT 0
                )
                """
            )
            # --- Ключ-значение для настроек (например, ссылка на сервер) ---
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS settings (
                    key   TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
                """
            )
            await db.commit()
        logger.info("База данных инициализирована: %s", self._db_path)

    # ===== ПОЛЬЗОВАТЕЛИ =====

    async def get_user(self, telegram_id: int) -> User | None:
        """Возвращает пользователя или None, если его ещё нет в БД."""
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT telegram_id, attempts, bonus_received, has_won "
                "FROM users WHERE telegram_id = ?",
                (telegram_id,),
            ) as cur:
                row = await cur.fetchone()
        if row is None:
            return None
        return User(
            telegram_id=row["telegram_id"],
            attempts=row["attempts"],
            bonus_received=bool(row["bonus_received"]),
            has_won=bool(row["has_won"]),
        )

    async def create_user(self, telegram_id: int, free_attempts: int) -> User:
        """Создаёт нового пользователя с бесплатными попытками.

        Если запись уже существует (гонка) — просто возвращаем её.
        """
        async with aiosqlite.connect(self._db_path) as db:
            # INSERT OR IGNORE защищает от дубликата при повторном /start.
            await db.execute(
                "INSERT OR IGNORE INTO users (telegram_id, attempts) VALUES (?, ?)",
                (telegram_id, free_attempts),
            )
            await db.commit()
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT telegram_id, attempts, bonus_received, has_won "
                "FROM users WHERE telegram_id = ?",
                (telegram_id,),
            ) as cur:
                row = await cur.fetchone()
        return User(
            telegram_id=row["telegram_id"],
            attempts=row["attempts"],
            bonus_received=bool(row["bonus_received"]),
            has_won=bool(row["has_won"]),
        )

    async def set_attempts(self, telegram_id: int, attempts: int) -> None:
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                "UPDATE users SET attempts = ? WHERE telegram_id = ?",
                (attempts, telegram_id),
            )
            await db.commit()

    async def decrement_attempts(self, telegram_id: int) -> None:
        """Уменьшает попытки на 1 (не уходит ниже 0)."""
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                "UPDATE users SET attempts = MAX(attempts - 1, 0) WHERE telegram_id = ?",
                (telegram_id,),
            )
            await db.commit()

    async def add_attempt(self, telegram_id: int) -> None:
        """Добавляет одну попытку (бонус за подписку)."""
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                "UPDATE users SET attempts = attempts + 1, bonus_received = 1 "
                "WHERE telegram_id = ?",
                (telegram_id,),
            )
            await db.commit()

    async def mark_winner(self, telegram_id: int) -> None:
        """Отмечает пользователя как победителя."""
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                "UPDATE users SET has_won = 1 WHERE telegram_id = ?",
                (telegram_id,),
            )
            await db.commit()

    # ===== СТАТИСТИКА =====

    async def count_users(self) -> int:
        async with aiosqlite.connect(self._db_path) as db:
            async with db.execute("SELECT COUNT(*) FROM users") as cur:
                row = await cur.fetchone()
        return row[0] if row else 0

    async def count_winners(self) -> int:
        async with aiosqlite.connect(self._db_path) as db:
            async with db.execute("SELECT COUNT(*) FROM users WHERE has_won = 1") as cur:
                row = await cur.fetchone()
        return row[0] if row else 0

    async def all_user_ids(self) -> list[int]:
        """Все ID пользователей — для рассылки."""
        async with aiosqlite.connect(self._db_path) as db:
            async with db.execute("SELECT telegram_id FROM users") as cur:
                rows = await cur.fetchall()
        return [r[0] for r in rows]

    async def all_users(self) -> list[User]:
        """Все пользователи целиком — для рассылки по chunks/пагинации."""
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT telegram_id, attempts, bonus_received, has_won FROM users"
            ) as cur:
                rows = await cur.fetchall()
        return [
            User(
                telegram_id=r["telegram_id"],
                attempts=r["attempts"],
                bonus_received=bool(r["bonus_received"]),
                has_won=bool(r["has_won"]),
            )
            for r in rows
        ]

    # ===== НАСТРОЙКИ =====

    async def get_setting(self, key: str) -> str | None:
        async with aiosqlite.connect(self._db_path) as db:
            async with db.execute(
                "SELECT value FROM settings WHERE key = ?", (key,)
            ) as cur:
                row = await cur.fetchone()
        return row[0] if row else None

    async def set_setting(self, key: str, value: str) -> None:
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                "INSERT INTO settings (key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, value),
            )
            await db.commit()
