import itertools
import random
import typing as t

import discord
from discord import app_commands
from discord.ext import tasks

from src.core.checks import developer_only
from src.utils.ansi import AnsiBuilder, Colors, Styles
from src.utils.constants import PRESENCE_MAP
from src.views.roles import ReactionRolesSetup

from . import BaseCog

if t.TYPE_CHECKING:
    from src.core.bot import HackspaceBot


class Utility(BaseCog):
    """A cog for utility commands."""

    _activity_types = itertools.cycle(
        (
            discord.ActivityType.playing,
            discord.ActivityType.listening,
            discord.ActivityType.watching,
            discord.ActivityType.competing,
        )
    )

    @tasks.loop(minutes=5)
    async def presence_loop(self) -> None:
        activity_type = next(self._activity_types)
        phrase = random.choice(PRESENCE_MAP.get(activity_type, []))
        activity = discord.Activity(type=activity_type, name=phrase(self.bot))
        await self.bot.change_presence(activity=activity)

    async def cog_load(self) -> None:
        help_command = self.bot.help_command
        help_command.cog = self  # type: ignore
        await super().cog_load()

    async def cog_unload(self) -> None:
        help_command = self.bot.help_command
        help_command.cog = None  # type: ignore
        await super().cog_unload()

    @app_commands.command(name="ping", description="Check the bot's latency.")
    @developer_only()
    async def ping(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        embed = discord.Embed(
            title="🏓 Pong!",
            description=AnsiBuilder.from_string(
                f"Bot Latency: {round(self.bot.latency * 1000)} ms", Colors.CYAN, Styles.BOLD
            ),
            color=discord.Color.green(),
        )
        embed.timestamp = discord.utils.utcnow()
        embed.set_thumbnail(url=self.bot.user.display_avatar)
        await interaction.edit_original_response(embed=embed)

    @app_commands.command(name="reaction_roles", description="Set up reaction roles in the current channel.")
    @developer_only()
    async def reaction_roles(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        embed = discord.Embed(
            title="Reaction Roles Setup",
            description="Please select the roles you want to set up for reaction roles.",
            color=discord.Color.blurple(),
        )
        embed.timestamp = discord.utils.utcnow()
        embed.set_thumbnail(url=self.bot.user.display_avatar)  # type: ignore
        embed.set_footer(text="Select roles and confirm to set up reaction roles.")
        view = ReactionRolesSetup(user=interaction.user)
        await interaction.edit_original_response(embed=embed, view=view)


async def setup(bot: "HackspaceBot") -> None:
    await bot.add_cog(Utility(bot))
