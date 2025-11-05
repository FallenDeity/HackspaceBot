import typing as t

import discord
from discord import app_commands
from discord.ext import commands

from src.core.errors import ViewTimeout
from src.views import BaseModal, BaseView

from . import BaseCog

if t.TYPE_CHECKING:
    from src.core.bot import HackspaceBot


class MyModal(BaseModal):
    name = discord.ui.TextInput[BaseModal](label="Enter something", placeholder="Type here...")


class MyView(BaseView):
    @discord.ui.button(label="Click Me", style=discord.ButtonStyle.primary)
    async def click_me(self, interaction: discord.Interaction, button: discord.ui.Button["MyView"]) -> None:
        modal = MyModal(title="Test Modal", timeout=10.0)
        await interaction.response.send_modal(modal)
        timedout = await modal.wait()
        if timedout:
            raise ViewTimeout("The modal has timed out.")
        await interaction.edit_original_response(content="You entered: " + modal.name.value)


class Utility(BaseCog, hidden=True):
    """A cog for utility commands."""

    async def cog_load(self) -> None:
        help_command = self.bot.help_command
        help_command.cog = self  # type: ignore

    async def cog_unload(self) -> None:
        help_command = self.bot.help_command
        help_command.cog = None  # type: ignore

    @app_commands.command(name="ping", description="Check the bot's latency.")
    async def ping(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        await interaction.edit_original_response(content=f"Pong! Latency: {round(self.bot.latency * 1000)}ms")

    @app_commands.command(name="error_check", description="Check the bot's error handling.")
    @app_commands.checks.cooldown(1, 60, key=lambda i: i.user.id)
    async def error_check(self, interaction: discord.Interaction, x: int, member: discord.Member) -> None:
        await interaction.response.defer()
        raise ValueError("This is a test error.")

    @commands.command(name="text_error_check", help="Check the bot's error handling with text command.")
    async def text_error_check(self, ctx: commands.Context["HackspaceBot"], x: int = 7) -> None:
        raise ValueError("This is a test error from text command.")

    @commands.command(name="view_check", help="Check the bot's view error handling.")
    async def view_check(self, ctx: commands.Context["HackspaceBot"]) -> None:
        view = MyView(user=ctx.author)
        await ctx.send("Click the button to test error handling in views.", view=view)

    @app_commands.command(name="modal_check", description="Check the bot's modal error handling.")
    async def modal_check(self, interaction: discord.Interaction) -> None:
        modal = MyModal(title="Test Modal")
        await interaction.response.send_modal(modal)


async def setup(bot: "HackspaceBot") -> None:
    await bot.add_cog(Utility(bot))
