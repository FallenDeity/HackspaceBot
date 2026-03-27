from __future__ import annotations

import json
import typing as t

import attrs

__all__: tuple[str, ...] = ("ContestNotificationState",)


def _to_positive_int_list(value: t.Any) -> list[int]:
    parsed: t.Any = value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return []

    if not isinstance(parsed, list):
        return []

    normalized = [
        item for item in parsed if isinstance(item, int) and item > 0  # pyright: ignore[reportUnknownVariableType]
    ]
    return sorted(set(normalized), reverse=True)


@attrs.define(kw_only=True, slots=True)
class ContestNotificationState:
    contest_id: int = attrs.field(converter=int)
    start_time_utc: int = attrs.field(converter=int)
    announced_at: str | None
    milestones_sent: list[int] = attrs.field(converter=_to_positive_int_list)
    milestones_missed: list[int] = attrs.field(converter=_to_positive_int_list)
    inactive: bool = attrs.field(converter=bool)
    last_checked_at: str
