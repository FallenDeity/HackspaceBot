import inspect
import logging
import typing as t

from discord.ext import commands, tasks

if t.TYPE_CHECKING:
    from src.core.bot import HackspaceBot


__all__: tuple[str, ...] = ("BaseCog",)

logger = logging.getLogger(__name__)


class BaseCog(commands.Cog):
    hidden: bool

    def __init__(self, bot: "HackspaceBot") -> None:
        self.bot = bot

    def __init_subclass__(cls, hidden: bool = False) -> None:
        cls.hidden = hidden

    def _patch_loop(self, loop: tasks.Loop[t.Callable[..., t.Coroutine[t.Any, t.Any, t.Any]]]) -> None:
        async def _loop_error_handler(self: BaseCog, error: Exception) -> None:
            logger.error(f"Error in loop {loop.coro.__name__} of cog {self.__class__.__name__}", exc_info=error)

        async def _loop_before_loop(self: BaseCog) -> None:
            await self.bot.wait_until_ready()
            logger.info(f"Starting loop {loop.coro.__name__} of cog {self.__class__.__name__}")

        loop.error(_loop_error_handler)  # type: ignore[arg-type]
        loop.before_loop(_loop_before_loop)

    async def cog_load(self) -> None:
        loop: tasks.Loop[t.Callable[..., t.Coroutine[t.Any, t.Any, t.Any]]]
        for _, loop in inspect.getmembers(self, predicate=lambda x: isinstance(x, tasks.Loop)):
            self._patch_loop(loop)
            loop.start()

    async def cog_unload(self) -> None:
        loop: tasks.Loop[t.Callable[..., t.Coroutine[t.Any, t.Any, t.Any]]]
        for _, loop in inspect.getmembers(self, predicate=lambda x: isinstance(x, tasks.Loop)):
            loop.cancel()
