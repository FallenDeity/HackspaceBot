import itertools
import random
import typing as t

import discord
from discord import app_commands
from discord.ext import tasks

from src.utils.ansi import AnsiBuilder, Colors, Styles
from src.utils.constants import PRESENCE_MAP, Roles
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
    @app_commands.checks.has_any_role(Roles.ADMIN, Roles.MODERATOR)
    async def reaction_roles(self, interaction: discord.Interaction, description: str) -> None:
        await interaction.response.defer(ephemeral=True)
        embed = discord.Embed(
            title="Reaction Roles Setup",
            description="Please select the roles you want to set up for reaction roles.",
            color=discord.Color.blurple(),
        )
        embed.timestamp = discord.utils.utcnow()
        embed.set_thumbnail(url=self.bot.user.display_avatar)  # type: ignore
        embed.set_footer(text="Select roles and confirm to set up reaction roles.")
        view = ReactionRolesSetup(user=interaction.user, description=description)
        await interaction.edit_original_response(embed=embed, view=view)

    @app_commands.command(name="rules", description="Display the server rules.")
    async def rules(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)

        embed = discord.Embed(
            description=(
                "# **Rules**\n"
                "**1.** All members must comply with Discord's [Terms of Service](https://discord.com/terms) and [Community Guidelines](https://discord.com/guidelines).\n\n"
                "**2.** No spam or self-promotion (server invites, advertisements, etc.) without permission from a staff member. This includes DMing fellow members.\n\n"
                "**3.** No age-restricted or obscene content. This includes text, images, or links featuring nudity, sexual content, hard violence, or any graphically disturbing material.\n\n"
                "**4.** Keep discussions tech-focused. This server is for topics such as technology, coding, projects, hackathons, and careers. Off-topic or unrelated discussions belong in #off-topic.\n\n"
                "**5.** Use English for communication. To ensure clear communication across the community, all discussions should be in English.\n\n"
                "**6.** No advertisements for paid internships, personal services, YouTube channels, Discord servers, or courses. Sharing resources is fine, just avoid promotion or monetized links.\n\n"
                "**7.** Post in the correct channels. Check channel descriptions before posting (e.g., #career-talk, #code-review, #project-showcase).\n\n"
                "**8.** Be polite and respectful. Respect all members and moderators. Personal attacks, sarcasm meant to insult, or toxic behavior will not be tolerated."
            ),
            color=discord.Color(0x4169E1),
        )
        rules_banner = discord.File("res/rules_banner.jpeg", filename="rules_banner.jpeg")
        embed.set_image(url="attachment://rules_banner.jpeg")
        embed.timestamp = discord.utils.utcnow()
        embed.set_footer(
            text="Please adhere to the server rules.",
            icon_url=interaction.guild.icon.url if interaction.guild and interaction.guild.icon else None,
        )

        channel = t.cast(discord.TextChannel, interaction.channel)
        await channel.send(embed=embed, file=rules_banner)  # type: ignore

        await interaction.edit_original_response(content="Server rules have been posted successfully.", view=None)


async def setup(bot: "HackspaceBot") -> None:
    await bot.add_cog(Utility(bot))
