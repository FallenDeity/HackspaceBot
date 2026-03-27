from __future__ import annotations

import pathlib
import re
import sqlite3
import typing as t

import aiofiles
import aiosqlite

from src.database.tables import TABLES, Config, ContestNotifications, FeatureFlags, Migrations
from src.utils.constants import Paths

MIGRATION_FILE_PATTERN = re.compile(r"^(?:(?P<ts>\d{10,})__)?(?P<uuid>[0-9a-fA-F-]{36})__(?P<name>.+)\.sql$")


class Database:
    connection: aiosqlite.Connection
    config: Config
    feature_flags: FeatureFlags
    contest_notifications: ContestNotifications
    migrations: Migrations

    def __init__(self, db_path: pathlib.Path, migration_dir: pathlib.Path | None = None) -> None:
        self.db_path = db_path
        self.migration_dir = migration_dir or pathlib.Path(Paths.MIGRATIONS)

    async def connect(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = await aiosqlite.connect(self.db_path)
        self.connection.row_factory = sqlite3.Row
        await self.execute("PRAGMA journal_mode=WAL")
        await self.execute("PRAGMA foreign_keys=ON")

        _tables = [table_type(self) for table_type in TABLES]

        for table in _tables:
            await table.setup()
            setattr(self, table.name, table)

        await self.apply_migrations()

        for table in _tables:
            await table.seed_defaults()

    async def close(self) -> None:
        await self.connection.close()

    async def apply_migrations(self) -> None:
        if not self.migration_dir.exists():
            return

        applied = await self.migrations.get_applied()

        pending: list[tuple[int, str, pathlib.Path]] = []
        for file in self.migration_dir.glob("*.sql"):
            match = MIGRATION_FILE_PATTERN.match(file.name)
            if match is None:
                continue
            migration_id = match.group("uuid")
            if migration_id in applied:
                continue
            ts = int(match.group("ts")) if match.group("ts") else 0
            pending.append((ts, migration_id, file))

        pending.sort(key=lambda item: (item[0], item[1]))
        if not pending:
            return

        await self._execute("BEGIN", commit=False)
        try:
            for _, migration_id, path in pending:
                async with aiofiles.open(path, mode="r", encoding="utf-8") as file:
                    sql = await file.read()
                await self._execute(sql, commit=False)
                await self.migrations.mark_applied(migration_id, commit=False)
        except Exception:
            await self._execute("ROLLBACK", commit=False)
            raise
        await self._execute("COMMIT", commit=False)

    async def _execute(self, query: str, *args: t.Any, commit: bool = True) -> None:
        await self.connection.execute(query, args)
        if commit:
            await self.connection.commit()

    async def execute(self, query: str, *args: t.Any) -> None:
        await self._execute(query, *args)

    async def executemany(self, query: str, args: t.Iterable[tuple[t.Any, ...]]) -> None:
        await self.connection.executemany(query, args)
        await self.connection.commit()

    async def fetchone(self, query: str, *args: t.Any) -> sqlite3.Row | None:
        cursor = await self.connection.execute(query, args)
        return await cursor.fetchone()

    async def fetchall(self, query: str, *args: t.Any) -> list[sqlite3.Row]:
        cursor = await self.connection.execute(query, args)
        return list(await cursor.fetchall())

    async def fetchval(self, query: str, *args: t.Any) -> t.Any:
        row = await self.fetchone(query, *args)
        if row is None:
            return None
        return row[0]
