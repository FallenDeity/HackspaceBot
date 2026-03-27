from __future__ import annotations

import typing as t

import attrs

__all__: tuple[str, ...] = ("ConfigEntry",)


@attrs.define(kw_only=True, slots=True)
class ConfigEntry:
    key: str
    value: t.Any
