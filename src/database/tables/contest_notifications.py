from __future__ import annotations

import datetime
import json
import sqlite3

from src.database.models import ContestNotificationState

from ._table import Table

__all__: tuple[str, ...] = ("ContestNotifications", "ContestNotificationState")


class ContestNotifications(Table):
    @property
    def name(self) -> str:
        return "contest_notifications"

    async def setup(self) -> None:
        await self.db.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {self.name} (
                contest_id INTEGER PRIMARY KEY,
                start_time_utc INTEGER NOT NULL,
                announced_at TEXT,
                milestones_sent TEXT NOT NULL,
                milestones_missed TEXT NOT NULL,
                inactive INTEGER NOT NULL,
                last_checked_at TEXT NOT NULL
            )
            """
        )

    async def seed_defaults(self) -> None:
        return

    async def upsert_contest(self, contest_id: int, start_time_utc: int) -> ContestNotificationState:
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        row = await self.db.fetchone(
            f"""
            INSERT INTO {self.name}
                (contest_id, start_time_utc, announced_at, milestones_sent, milestones_missed, inactive, last_checked_at)
            VALUES
                (?, ?, NULL, '[]', '[]', 0, ?)
            ON CONFLICT(contest_id) DO UPDATE SET
                start_time_utc = excluded.start_time_utc,
                last_checked_at = excluded.last_checked_at
            RETURNING *
            """,
            contest_id,
            start_time_utc,
            now,
        )
        assert row is not None
        return self._state_from_row(row)

    async def get_state(self, contest_id: int) -> ContestNotificationState | None:
        row = await self.db.fetchone(f"SELECT * FROM {self.name} WHERE contest_id = ?", contest_id)
        if row is None:
            return None
        return self._state_from_row(row)

    async def mark_announced(self, contest_id: int) -> None:
        await self.db.execute(
            f"UPDATE {self.name} SET announced_at = ? WHERE contest_id = ?",
            datetime.datetime.now(datetime.timezone.utc).isoformat(),
            contest_id,
        )

    async def update_milestone_sets(self, contest_id: int, sent: list[int], missed: list[int]) -> None:
        await self.db.execute(
            f"""
            UPDATE {self.name}
            SET milestones_sent = ?, milestones_missed = ?, last_checked_at = ?
            WHERE contest_id = ?
            """,
            json.dumps(sorted(set(sent), reverse=True)),
            json.dumps(sorted(set(missed), reverse=True)),
            datetime.datetime.now(datetime.timezone.utc).isoformat(),
            contest_id,
        )

    async def delete(self, contest_id: int) -> None:
        await self.db.execute(f"DELETE FROM {self.name} WHERE contest_id = ?", contest_id)

    @staticmethod
    def _state_from_row(row: sqlite3.Row) -> ContestNotificationState:
        return ContestNotificationState(
            contest_id=row["contest_id"],
            start_time_utc=row["start_time_utc"],
            announced_at=row["announced_at"],
            milestones_sent=row["milestones_sent"],
            milestones_missed=row["milestones_missed"],
            inactive=row["inactive"],
            last_checked_at=str(row["last_checked_at"]),
        )
