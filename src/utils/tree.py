from __future__ import annotations

import io
import logging
import typing as t

import discord
from discord import app_commands
from discord.abc import Snowflake
from discord.app_commands.errors import AppCommandError
from discord.ext import commands
from discord.interactions import Interaction

from src.core.checks import get_cooldown_bucket
from src.core.errors import BotExceptions, ExceptionResponse, UnknownError
from src.utils.embeds import build_error_embed

if t.TYPE_CHECKING:
    from src.core.bot import HackspaceBot

__all__: tuple[str, ...] = ("SlashCommandTree",)

logger = logging.getLogger(__name__)


class SlashCommandTree(app_commands.CommandTree["HackspaceBot"]):
    def __init__(self, *args: t.Any, **kwargs: t.Any) -> None:
        super().__init__(*args, **kwargs)
        self.application_commands: dict[int | None, list[app_commands.AppCommand]] = {}
        self.cache: dict[
            int | None,
            dict[app_commands.Command[t.Any, ..., t.Any] | commands.HybridCommand[t.Any, ..., t.Any] | str, str],
        ] = {}

    async def sync(self, *, guild: Snowflake | None = None) -> t.List[app_commands.AppCommand]:
        ret = await super().sync(guild=guild)
        guild_id = guild.id if guild else None
        self.application_commands[guild_id] = ret
        self.cache.pop(guild_id, None)
        return ret

    async def fetch_commands(self, *, guild: Snowflake | None = None) -> t.List[app_commands.AppCommand]:
        commands = await super().fetch_commands(guild=guild)
        guild_id = guild.id if guild else None
        self.application_commands[guild_id] = commands
        self.cache.pop(guild_id, None)
        return commands

    async def get_or_fetch_commands(self, *, guild: Snowflake | None = None) -> t.List[app_commands.AppCommand]:
        guild_id = guild.id if guild else None
        if guild_id in self.application_commands:
            return self.application_commands[guild_id]
        return await self.fetch_commands(guild=guild)

    async def find_mention_for(
        self,
        command: app_commands.Command[t.Any, ..., t.Any] | commands.HybridCommand[t.Any, ..., t.Any] | str,
        *,
        guild: Snowflake | None = None,
    ) -> str | None:
        guild_id = guild.id if guild else None

        try:
            return self.cache[guild_id][command]
        except KeyError:
            pass

        check_global = self.fallback_to_global is True or guild is not None

        if isinstance(command, str):
            _command = discord.utils.get(self.walk_commands(guild=guild), qualified_name=command)

            if _command is None and check_global:
                _command = discord.utils.get(self.walk_commands(), qualified_name=command)
        else:
            _command = command

        if _command is None:
            return None

        local_commands = await self.get_or_fetch_commands(guild=guild)
        app_command_found = discord.utils.get(local_commands, name=(_command.root_parent or _command).name)

        if check_global and app_command_found is None:
            global_commands = await self.get_or_fetch_commands()
            app_command_found = discord.utils.get(global_commands, name=(_command.root_parent or _command).name)

        if app_command_found is None:
            return None

        mention = app_command_found.mention
        self.cache.setdefault(guild_id, {})[_command] = mention  # type: ignore
        return mention

    async def on_error(self, interaction: Interaction["HackspaceBot"], error: AppCommandError | Exception) -> None:  # type: ignore[override]
        if isinstance(error, app_commands.errors.CommandInvokeError):
            error = error.original

        if not isinstance(error, app_commands.errors.CommandOnCooldown) and interaction.command is not None:
            buckets = [b for c in interaction.command.checks if (b := get_cooldown_bucket(c)) is not None]
            for bucket_func in buckets:
                bucket = await bucket_func(interaction)
                if bucket is not None:
                    bucket.reset()

        error_response = BotExceptions.get_response(error)

        if isinstance(error_response, ExceptionResponse):
            if error_response.error is UnknownError:
                embeds, description, tb = build_error_embed(interaction, error)
                logger.error(f"{description}\n{tb}")
                await interaction.client.sys_log(
                    embeds=embeds, file=discord.File(fp=io.BytesIO(tb.encode()), filename="traceback.txt")
                )
            error_response = str(error_response)

        try:
            await interaction.response.send_message(error_response)
        except discord.InteractionResponded:
            await interaction.edit_original_response(content=error_response)
