import json
import typing as t

from src.database.models import ConfigEntry
from src.utils.constants import DEFAULT_CONFIG_VALUES, ConfigKey

from ._table import Table

__all__: tuple[str, ...] = ("Config",)


class Config(Table):
    """
    Key-Value store for global bot configuration.
    Stores values as JSON strings so data types (int, dict, bool, list) are preserved automatically.
    """

    @property
    def name(self) -> str:
        return "config"

    async def setup(self) -> None:
        await self.db.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {self.name} (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )

    async def seed_defaults(self) -> None:
        for key, value in DEFAULT_CONFIG_VALUES.items():
            await self.set_default(key, value)

    async def set(self, key: ConfigKey | str, value: t.Any) -> None:
        """Store a configuration value."""
        key_text = key.value if isinstance(key, ConfigKey) else key
        serialized = json.dumps(value)
        await self.db.execute(
            f"""
            INSERT INTO {self.name} (key, value)
            VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            key_text,
            serialized,
        )

    async def set_default(self, key: ConfigKey | str, value: t.Any) -> None:
        key_text = key.value if isinstance(key, ConfigKey) else key
        serialized = json.dumps(value)
        await self.db.execute(
            f"""
            INSERT OR IGNORE INTO {self.name} (key, value)
            VALUES (?, ?)
            """,
            key_text,
            serialized,
        )

    async def get(self, key: ConfigKey | str, default: t.Any = None) -> t.Any:
        """Retrieve a configuration value."""
        key_text = key.value if isinstance(key, ConfigKey) else key
        row = await self.db.fetchval(f"SELECT value FROM {self.name} WHERE key = ?", key_text)
        if row is None:
            fallback = DEFAULT_CONFIG_VALUES.get(key) if isinstance(key, ConfigKey) else default
            return fallback
        try:
            return json.loads(row)
        except json.JSONDecodeError:
            return row

    async def get_entries(self) -> list[ConfigEntry]:
        rows = await self.db.fetchall(f"SELECT key, value FROM {self.name}")
        entries: list[ConfigEntry] = []
        for row in rows:
            key = str(row["key"])
            raw_value = str(row["value"])
            try:
                parsed = json.loads(raw_value)
            except json.JSONDecodeError:
                parsed = raw_value
            entries.append(ConfigEntry(key=key, value=parsed))
        return entries

    async def delete(self, key: ConfigKey | str) -> None:
        """Delete a configuration value."""
        key_text = key.value if isinstance(key, ConfigKey) else key
        await self.db.execute(f"DELETE FROM {self.name} WHERE key = ?", key_text)
