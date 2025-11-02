import typing as t

import discord
from discord import app_commands

from . import BaseCog

if t.TYPE_CHECKING:
    from src.core.bot import HackspaceBot


class Utility(BaseCog):
    """A cog for utility commands."""

    async def cog_load(self) -> None:
        help_command = self.bot.help_command
        help_command.cog = self

    async def cog_unload(self) -> None:
        help_command = self.bot.help_command
        help_command.cog = None
    
    @app_commands.command(name="ping", description="Check the bot's latency.")
    async def ping(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        await interaction.edit_original_response(content=f"Pong! Latency: {round(self.bot.latency * 1000)}ms")


async def setup(bot: "HackspaceBot") -> None:
    await bot.add_cog(Utility(bot))
