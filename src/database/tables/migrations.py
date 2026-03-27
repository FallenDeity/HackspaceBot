from __future__ import annotations

import datetime

from ._table import Table

__all__: tuple[str, ...] = ("Migrations",)


class Migrations(Table):
    @property
    def name(self) -> str:
        return "migrations"

    async def setup(self) -> None:
        await self.db.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {self.name} (
                migration_id TEXT PRIMARY KEY,
                applied_at TEXT NOT NULL
            )
            """
        )

    async def seed_defaults(self) -> None:
        return

    async def get_applied(self) -> set[str]:
        rows = await self.db.fetchall(f"SELECT migration_id FROM {self.name}")
        return {str(row["migration_id"]) for row in rows}

    async def mark_applied(self, migration_id: str, *, commit: bool = True) -> None:
        await self.db._execute(  # pyright: ignore[reportPrivateUsage]
            f"INSERT INTO {self.name} (migration_id, applied_at) VALUES (?, ?)",
            migration_id,
            datetime.datetime.now(datetime.timezone.utc).isoformat(),
            commit=commit,
        )
