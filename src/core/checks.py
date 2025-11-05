from __future__ import annotations

import inspect
import typing as t

import discord
from discord import app_commands
from discord.ext import commands

from src.core.errors import DeveloperOnly
from src.utils.constants import DEVELOPER_IDS

if t.TYPE_CHECKING:
    from src.core.bot import HackspaceBot


__all__: tuple[str, ...] = (
    "developer_only",
    "get_cooldown_bucket",
)


def developer_only(slash: bool = False):
    async def predicate(ctx_or_inter: commands.Context["HackspaceBot"] | discord.Interaction) -> bool:
        author = ctx_or_inter.author if isinstance(ctx_or_inter, commands.Context) else ctx_or_inter.user
        if author.id in DEVELOPER_IDS:
            return True
        raise DeveloperOnly()

    return commands.check(predicate) if not slash else app_commands.check(predicate)


def get_cooldown_bucket(
    f: t.Callable[..., t.Any],
) -> t.Callable[[discord.Interaction], t.Coroutine[t.Any, t.Any, app_commands.Cooldown | None]] | None:
    mod_name = getattr(f, "__module__", None)
    qualname = getattr(f, "__qualname__", "")

    if mod_name != "discord.app_commands.checks" and "_create_cooldown_decorator" not in qualname:
        return None

    closure = getattr(f, "__closure__", ()) or ()
    get_bucket_cell = next(
        (
            cell
            for cell in closure
            if inspect.isfunction(cell.cell_contents) and cell.cell_contents.__name__ == "get_bucket"
        ),
        None,
    )

    if get_bucket_cell is None:
        return None

    return get_bucket_cell.cell_contents  # type: ignore
