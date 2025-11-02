from __future__ import annotations

import datetime
import logging
import os
import traceback
import typing
import pathlib

import aiohttp
import discord
from discord.ext import commands
from dotenv import load_dotenv
from src.utils.help import CustomHelpCommand
from src.utils.tree import SlashCommandTree

__all__: tuple[str, ...] = ("HackspaceBot",)

logger = logging.getLogger(__name__)


class HackspaceBot(commands.Bot):
    client: aiohttp.ClientSession
    _uptime: datetime.datetime = datetime.datetime.now(datetime.timezone.utc)

    def __init__(self, prefix: str, ext_dir: str | pathlib.Path, *args: typing.Any, **kwargs: typing.Any) -> None:
        super().__init__(*args, **kwargs, command_prefix=commands.when_mentioned_or(prefix), intents=discord.Intents.all(), help_command=CustomHelpCommand(with_app_command=True), tree_cls=SlashCommandTree)
        self.ext_dir = pathlib.Path(ext_dir)
        self.synced = True

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

    async def on_error(self, event_method: str, *args: typing.Any, **kwargs: typing.Any) -> None:
        logger.error(f"An error occurred in {event_method}.\n{traceback.format_exc()}")

    async def on_ready(self) -> None:
        logger.info(f"Logged in as {self.user} ({self.user.id})")

    async def setup_hook(self) -> None:
        self.client = aiohttp.ClientSession()
        await self._load_extensions()
        if not self.synced:
            await self.tree.sync()
            self.synced = not self.synced
            logger.info("Synced command tree")

    async def close(self) -> None:
        await super().close()
        await self.client.close()

    def run(self, *args: typing.Any, **kwargs: typing.Any) -> None:
        load_dotenv()
        try:
            super().run(str(os.getenv("DISCORD_BOT_TOKEN")), *args, **kwargs)
        except (discord.LoginFailure, KeyboardInterrupt):
            logger.info("Exiting...")
            exit()

    @property
    def user(self) -> discord.ClientUser:
        assert super().user, "Bot is not ready yet"
        return typing.cast(discord.ClientUser, super().user)

    @property
    def uptime(self) -> datetime.timedelta:
        return datetime.datetime.now(datetime.timezone.utc) - self._uptime
