from __future__ import annotations

import enum
import typing as t

if t.TYPE_CHECKING:
    from src.database import Database


__all__: tuple[str, ...] = ("FeatureKey", "DEFAULT_FEATURE_FLAGS", "FeatureSwitchboard")


class FeatureKey(enum.StrEnum):
    CODEFORCES_NOTIFICATIONS = "codeforces_notifications"
    CODEFORCES_DRY_RUN_VISIBLE = "codeforces_dry_run_visible"


DEFAULT_FEATURE_FLAGS: dict[FeatureKey, bool] = {
    FeatureKey.CODEFORCES_NOTIFICATIONS: True,
    FeatureKey.CODEFORCES_DRY_RUN_VISIBLE: True,
}


class FeatureSwitchboard:
    def __init__(self, db: "Database") -> None:
        self._db = db

    async def is_enabled(self, key: FeatureKey) -> bool:
        return await self._db.feature_flags.is_enabled(key)

    async def set_enabled(self, key: FeatureKey, enabled: bool) -> None:
        await self._db.feature_flags.set_enabled(key, enabled)

    async def all(self) -> dict[FeatureKey, bool]:
        flags = await self._db.feature_flags.all_flags()
        mapped: dict[FeatureKey, bool] = {}
        for key in FeatureKey:
            mapped[key] = flags.get(key, False)
        return mapped
