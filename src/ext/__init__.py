import typing as t

from discord.ext import commands

if t.TYPE_CHECKING:
    from src.core.bot import HackspaceBot


__all__: tuple[str, ...] = ("BaseCog",)


class BaseCog(commands.Cog):
    hidden: bool

    def __init__(self, bot: "HackspaceBot") -> None:
        self.bot = bot

    def __init_subclass__(cls, hidden: bool = False) -> None:
        cls.hidden = hidden