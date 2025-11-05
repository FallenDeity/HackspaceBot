import traceback
import typing as t

import discord
from discord.ext import commands

if t.TYPE_CHECKING:
    from src.core.bot import HackspaceBot


__all__: tuple[str, ...] = (
    "build_error_embed",
    "build_view_error_embed",
)


def _build_error_details(ctx_or_inter: commands.Context["HackspaceBot"] | discord.Interaction) -> str:
    command_name = ctx_or_inter.command.qualified_name if ctx_or_inter.command else None
    command_params = ctx_or_inter.args[2:] if isinstance(ctx_or_inter, commands.Context) else ctx_or_inter.namespace

    if isinstance(ctx_or_inter, commands.Context) and ctx_or_inter.command is not None:
        command_params = dict(zip(ctx_or_inter.command.clean_params.keys(), command_params))

    user = ctx_or_inter.author if isinstance(ctx_or_inter, commands.Context) else ctx_or_inter.user
    timestamp = (
        ctx_or_inter.message.created_at if isinstance(ctx_or_inter, commands.Context) else ctx_or_inter.created_at
    )
    details = (
        "```yaml\n"
        f"Command: {command_name}\n"
        f"Username: {user} (ID: {user.id})\n"
        f"Timestamp: {timestamp}\n"
        f"Parameters: {command_params}\n"
        f"Guild: {ctx_or_inter.guild} (ID: {ctx_or_inter.guild.id if ctx_or_inter.guild else 'N/A'})\n"
        f"Channel: {ctx_or_inter.channel} (ID: {ctx_or_inter.channel.id if ctx_or_inter.channel else 'N/A'})\n"
        "```"
    )
    return details


def _build_view_error_details(
    interaction: discord.Interaction, item: discord.ui.Item[discord.ui.View] | discord.ui.Modal
) -> str:
    user = interaction.user
    timestamp = interaction.created_at
    message_link = interaction.message.jump_url if interaction.message else "N/A"
    jump_url = f"[Jump to Message]({message_link})" if interaction.message else "N/A"
    details = (
        f"{jump_url}\n"
        "```yaml\n"
        f"View Item: {item}\n"
        f"Username: {user} (ID: {user.id})\n"
        f"Timestamp: {timestamp}\n"
        f"Guild: {interaction.guild} (ID: {interaction.guild.id if interaction.guild else 'N/A'})\n"
        f"Channel: {interaction.channel} (ID: {interaction.channel.id if interaction.channel else 'N/A'})\n"
        "```"
    )
    return details


def _build_traceback_chunks(tb: str) -> list[str]:
    chunks: list[str] = []
    string: list[str] = []
    for line in tb.splitlines():
        if sum(len(s) for s in string) + len(line) > 1024:
            chunks.append("\n".join(string))
            string.clear()
        string.append(line)
    if string:
        chunks.append("\n".join(string))
    if not chunks:
        chunks.append("No output.")
    return chunks


def build_error_embed(
    ctx_or_inter: commands.Context["HackspaceBot"] | discord.Interaction, exception: Exception
) -> tuple[list[discord.Embed], str, str]:
    tb = "".join(traceback.format_exception(type(exception), exception, exception.__traceback__))
    chunks = _build_traceback_chunks(tb)
    description = _build_error_details(ctx_or_inter)
    return (
        [
            discord.Embed(
                title="Error Traceback",
                description=f"{description}\n```py\n{chunk}```",
                color=discord.Color.red(),
            )
            for chunk in chunks
        ],
        description,
        tb,
    )


def build_view_error_embed(
    interaction: discord.Interaction, exception: Exception, item: discord.ui.Item[discord.ui.View] | discord.ui.Modal
) -> tuple[list[discord.Embed], str, str]:
    tb = "".join(traceback.format_exception(type(exception), exception, exception.__traceback__))
    chunks = _build_traceback_chunks(tb)
    description = _build_view_error_details(interaction, item)
    return (
        [
            discord.Embed(
                title="View Error Traceback",
                description=f"{description}\n```py\n{chunk}```",
                color=discord.Color.red(),
            )
            for chunk in chunks
        ],
        description,
        tb,
    )
