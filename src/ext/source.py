from __future__ import annotations

import enum
import inspect
import pathlib
import typing as t

import discord
from discord import app_commands
from discord.ext import commands
from discord.utils import escape_markdown

from src.utils.constants import URLs

from . import BaseCog

if t.TYPE_CHECKING:
    from src.core.bot import HackspaceBot

SourceObject = (
    commands.Command[t.Any, ..., t.Any] | commands.Cog | app_commands.Command[t.Any, ..., t.Any] | app_commands.Group
)


class SourceType(enum.StrEnum):
    command = enum.auto()
    cog = enum.auto()


class BotSource(BaseCog):
    """Displays information about the bot's source code."""

    @app_commands.command(name="source")
    async def source_command(
        self,
        interaction: discord.Interaction[HackspaceBot],
        *,
        source_item: str | None = None,
    ) -> None:
        """
        Display information and a GitHub link to the source code of a command, or cog.

        Parameters
        ----------
        source_item : str | None
            The name of the command or cog to get the source for. If None, displays the bot's GitHub repository link.
        """
        await interaction.response.defer()
        if not source_item:
            embed = discord.Embed(title="Bot's GitHub Repository", color=discord.Color.blurple())
            embed.add_field(name="Repository", value=f"[Go to GitHub]({URLs.GITHUB_REPO})")
            embed.set_thumbnail(url="https://avatars1.githubusercontent.com/u/9919")
            await interaction.edit_original_response(embed=embed)
            return

        obj, source_type = await self.get_source_object(interaction, source_item)
        embed = await self.build_embed(obj, source_type)
        await interaction.edit_original_response(embed=embed)

    @source_command.autocomplete("source_item")
    async def source_item_autocomplete(
        self,
        interaction: discord.Interaction[HackspaceBot],
        current: str,
    ) -> list[app_commands.Choice[str]]:
        """Autocomplete for the source_item argument."""
        choices: list[app_commands.Choice[str]] = []
        all_commands = list(self.bot.walk_commands()) + list(self.bot.tree.walk_commands())
        all_cogs = list(self.bot.cogs.values())
        for query_item in all_commands + all_cogs:
            query_item_name = query_item.qualified_name
            if current.lower() in query_item_name.lower():
                choices.append(app_commands.Choice(name=query_item_name, value=query_item_name))
        return choices[:25]

    @staticmethod
    async def get_source_object(
        interaction: discord.Interaction[HackspaceBot], argument: str
    ) -> tuple[SourceObject, SourceType]:
        """Convert argument into the source object and source type."""
        cog = interaction.client.get_cog(argument)
        if cog:
            return cog, SourceType.cog

        cmd = interaction.client.get_command(argument) or interaction.client.tree.get_command(argument)
        if cmd:
            return cmd, SourceType.command

        escaped_arg = escape_markdown(argument)

        raise commands.BadArgument(f"Unable to convert '{escaped_arg}' to valid command or Cog.")

    def get_source_link(
        self, source_item: SourceObject, source_type: SourceType
    ) -> tuple[str, str | pathlib.Path, int | None]:
        """
        Build GitHub link of source item, return this link, file location and first line number.

        Raise BadArgument if `source_item` is a dynamically-created object (e.g. via internal eval).
        """
        filename: str | None = None

        if source_type == SourceType.command:
            source_item = inspect.unwrap(source_item.callback)  # type: ignore
            src = source_item.__code__  # type: ignore
            filename = str(src.co_filename)  # type: ignore
        else:
            src = type(source_item)
            try:
                filename = inspect.getsourcefile(src)
            except TypeError:
                raise commands.BadArgument("Cannot get source for a dynamically-created object.")

        try:
            lines, first_line_no = inspect.getsourcelines(src)  # type: ignore
        except OSError:
            raise commands.BadArgument("Cannot get source for a dynamically-created object.")

        lines_extension = f"#L{first_line_no}-L{first_line_no+len(lines)-1}"

        if not filename:
            raise commands.BadArgument("Cannot get source for a dynamically-created object.")

        if not first_line_no:
            file_location = pathlib.Path(filename)
        else:
            file_location = pathlib.Path(filename).relative_to(pathlib.Path.cwd()).as_posix()

        # if file location dosen't start with 'src/', that means it's likely from a 3rd party library
        if not str(file_location).startswith("src/"):
            # sanitize the file location so it comes after site-packages or dist-packages
            package_sites = (
                "site-packages",
                "dist-packages",
            )
            for part in package_sites:
                if part in str(file_location):
                    file_location_parts = str(file_location).split(part, 1)
                    file_location = pathlib.Path(part).joinpath(file_location_parts[1].lstrip("/\\"))
                    break
            raise commands.BadArgument(
                "Source comes from a 3rd party library, cannot provide link.\n```\n" f"{file_location}\n```"
            )

        url = f"{URLs.GITHUB_REPO}/blob/master/{file_location}{lines_extension}"

        return url, file_location, first_line_no or None

    async def build_embed(self, source_object: SourceObject, source_type: SourceType) -> discord.Embed | None:
        """Build embed based on source object."""
        url, location, first_line = self.get_source_link(source_object, source_type)
        if source_type == SourceType.command:
            description = getattr(source_object, "__doc__", "") or getattr(source_object, "description", "") or "\n\n"
            title = f"Command: {getattr(source_object, 'qualified_name', None) or getattr(source_object, 'name', None) or str(source_object)}"
        else:
            title = f"Cog: {getattr(source_object, 'qualified_name', None) or getattr(source_object, '__name__', None) or str(source_object)}"
            description = getattr(source_object, "__doc__", "") or getattr(source_object, "description", "") or "\n\n"

        embed = discord.Embed(title=title, description=description, color=discord.Color.blurple())
        embed.add_field(name="Source Code", value=f"[Go to GitHub]({url})")
        embed.set_thumbnail(url="https://avatars1.githubusercontent.com/u/9919")
        line_text = f":{first_line}" if first_line else ""
        embed.set_footer(text=f"{location}{line_text}")

        return embed


async def setup(bot: HackspaceBot) -> None:
    await bot.add_cog(BotSource(bot))
