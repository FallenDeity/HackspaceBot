from __future__ import annotations

import datetime

from src.utils.features import DEFAULT_FEATURE_FLAGS, FeatureKey

from ._table import Table

__all__: tuple[str, ...] = ("FeatureFlags",)


class FeatureFlags(Table):
    @property
    def name(self) -> str:
        return "feature_flags"

    async def setup(self) -> None:
        await self.db.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {self.name} (
                feature TEXT PRIMARY KEY,
                enabled INTEGER NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )

    async def seed_defaults(self) -> None:
        for feature, enabled in DEFAULT_FEATURE_FLAGS.items():
            await self.set_default(feature, enabled)

    async def set_default(self, feature: FeatureKey, enabled: bool) -> None:
        await self.db.execute(
            f"""
            INSERT OR IGNORE INTO {self.name} (feature, enabled, updated_at)
            VALUES (?, ?, ?)
            """,
            feature.value,
            int(enabled),
            datetime.datetime.now(datetime.timezone.utc).isoformat(),
        )

    async def set_enabled(self, feature: FeatureKey, enabled: bool) -> None:
        await self.db.execute(
            f"""
            INSERT INTO {self.name} (feature, enabled, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(feature) DO UPDATE SET
                enabled = excluded.enabled,
                updated_at = excluded.updated_at
            """,
            feature.value,
            int(enabled),
            datetime.datetime.now(datetime.timezone.utc).isoformat(),
        )

    async def is_enabled(self, feature: FeatureKey) -> bool:
        result = await self.db.fetchval(f"SELECT enabled FROM {self.name} WHERE feature = ?", feature.value)
        if result is None:
            return DEFAULT_FEATURE_FLAGS.get(feature, False)
        return bool(result)

    async def all_flags(self) -> dict[FeatureKey, bool]:
        rows = await self.db.fetchall(f"SELECT feature, enabled FROM {self.name} ORDER BY feature ASC")
        mapped: dict[FeatureKey, bool] = {}
        for row in rows:
            feature_raw = str(row["feature"])
            try:
                key = FeatureKey(feature_raw)
            except ValueError:
                continue
            mapped[key] = bool(row["enabled"])
        return mapped
