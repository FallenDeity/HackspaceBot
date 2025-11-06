from __future__ import annotations

import datetime
import io
import logging
import pathlib
import traceback
import typing as t

import aiohttp
import discord
from discord.ext import commands

from src.core.errors import BotExceptions, ExceptionResponse, UnknownError
from src.core.tree import SlashCommandTree
from src.utils.constants import Channels
from src.utils.embeds import build_error_embed
from src.utils.env import ENV
from src.utils.help import CustomHelpCommand
from src.views.messages import DynamicDeleteButton
from src.views.roles import DynamicRoleSelect

__all__: tuple[str, ...] = ("HackspaceBot",)

logger = logging.getLogger(__name__)


class HackspaceBot(commands.Bot):
    client: aiohttp.ClientSession
    _uptime: datetime.datetime = datetime.datetime.now(datetime.timezone.utc)

    def __init__(self, prefix: str, ext_dir: str | pathlib.Path, *args: t.Any, **kwargs: t.Any) -> None:
        super().__init__(
            *args,
            **kwargs,
            command_prefix=commands.when_mentioned_or(prefix),
            intents=discord.Intents.all(),
            help_command=CustomHelpCommand(with_app_command=True),
            tree_cls=SlashCommandTree,
        )
        self.ext_dir = pathlib.Path(ext_dir)

    def __check_on_guild(self, ctx: commands.Context[HackspaceBot]) -> bool:
        if ctx.guild is None:
            raise commands.NoPrivateMessage("This command cannot be used in DMs.")
        return True

    def __check_on_bot_owner(self, ctx: commands.Context[HackspaceBot]) -> bool:
        return not ctx.author.bot

    def _disable_dm_commands(self) -> None:
        for command in self.tree.get_commands():
            command.guild_only = True
        self.check(self.__check_on_guild)
        self.check(self.__check_on_bot_owner)

    async def _load_extensions(self) -> None:
        if not self.ext_dir.is_dir():
            logger.error(f"Extension directory {self.ext_dir} does not exist.")
            return
        for filename in self.ext_dir.iterdir():
            if filename.suffix == ".py" and not filename.name.startswith("_"):
                try:
                    await self.load_extension(f"{self.ext_dir.as_posix().replace('/', '.')}.{filename.stem}")
                    logger.info(f"Loaded extension {filename.stem}")
                except commands.ExtensionError:
                    logger.error(f"Failed to load extension {filename.stem}\n{traceback.format_exc()}")

    async def on_command_error(self, context: commands.Context[HackspaceBot], exception: commands.CommandError | Exception) -> None:  # type: ignore[override]
        if isinstance(exception, commands.CommandNotFound):
            return
        if not isinstance(exception, commands.CommandOnCooldown) and context.command is not None:
            context.command.reset_cooldown(context)
        if isinstance(exception, commands.CommandInvokeError):
            exception = exception.original

        error_response = BotExceptions.get_response(exception)

        if isinstance(error_response, ExceptionResponse):
            if error_response.error is UnknownError:
                embeds, description, tb = build_error_embed(context, exception)
                logger.error(f"{description}\n{tb}")
                await self.sys_log(
                    embeds=embeds, file=discord.File(fp=io.BytesIO(tb.encode()), filename="traceback.txt")
                )
            error_response = str(error_response)

        await context.reply(error_response)

    async def sys_log(self, *args: t.Any, **kwargs: t.Any) -> None:
        channel = t.cast(
            discord.TextChannel, self.get_channel(Channels.LOGS) or await self.fetch_channel(Channels.LOGS)
        )
        await channel.send(*args, **kwargs)

    async def on_error(self, event_method: str, *args: t.Any, **kwargs: t.Any) -> None:
        logger.error(f"An error occurred in {event_method}.\n{traceback.format_exc()}")

    async def on_ready(self) -> None:
        logger.info(f"Logged in as {self.user} ({self.user.id})")

    async def setup_hook(self) -> None:
        self.client = aiohttp.ClientSession()
        await self._load_extensions()
        await self.load_extension("jishaku")
        self.add_dynamic_items(DynamicRoleSelect, DynamicDeleteButton)
        self._disable_dm_commands()

    async def close(self) -> None:
        await self.client.close()
        await super().close()

    def run(self, *args: t.Any, **kwargs: t.Any) -> None:
        try:
            super().run(ENV.DISCORD_TOKEN, *args, **kwargs)
        except (discord.LoginFailure, KeyboardInterrupt):
            logger.info("Exiting...")
            exit()

    @property
    def user(self) -> discord.ClientUser:
        assert super().user, "Bot is not ready yet"
        return t.cast(discord.ClientUser, super().user)

    @property
    def uptime(self) -> datetime.timedelta:
        return datetime.datetime.now(datetime.timezone.utc) - self._uptime

    @property
    def tree(self) -> SlashCommandTree:  # type: ignore[override]
        return t.cast(SlashCommandTree, super().tree)
