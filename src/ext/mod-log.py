from __future__ import annotations

import datetime
import io
import typing as t

import discord
from discord.ext import commands
from PIL import Image, ImageDraw, ImageFont

from . import BaseCog

if t.TYPE_CHECKING:
    from src.core.bot import HackspaceBot


class ModLog(BaseCog, hidden=True):
    """Logs for community server."""

    @staticmethod
    async def merge_images(img1: discord.Asset, img2: discord.Asset) -> io.BytesIO:
        asset1 = img1.with_size(256)
        asset2 = img2.with_size(256)
        image1 = Image.open(io.BytesIO(await asset1.read()))
        image2 = Image.open(io.BytesIO(await asset2.read()))
        write1 = ImageDraw.Draw(image1)
        write2 = ImageDraw.Draw(image2)
        write1.text(
            (5, 5),
            "Before",
            fill=(255, 255, 255),
            font=ImageFont.truetype("res/fonts/Roboto-Bold.ttf", 20),
        )
        write2.text(
            (5, 5),
            "After",
            fill=(255, 255, 255),
            font=ImageFont.truetype("res/fonts/Roboto-Bold.ttf", 20),
        )
        img = Image.new("RGBA", (512, 256))
        img.paste(image1, (0, 0), image1)
        img.paste(image2, (256, 0), image2)
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)
        return buffer

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        embed = discord.Embed(
            title="Join",
            description=f"{member} has joined the server",
            color=discord.Color.green(),
        )
        embed.add_field(name="Name", value=f"{member} [{member.id}]\n{member.mention}", inline=True)
        embed.add_field(
            name="Joined",
            value=f"{discord.utils.format_dt(member.joined_at, style='D')}",  # type: ignore
            inline=True,
        )
        embed.add_field(
            name="Account Created On",
            value=f"{discord.utils.format_dt(member.created_at, style='D')}",
            inline=True,
        )
        embed.add_field(name="Member Count", value=len(member.guild.members), inline=True)
        embed.set_thumbnail(url=member.display_avatar)
        embed.timestamp = discord.utils.utcnow()
        await self.bot.sys_log(embed=embed)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member) -> None:
        embed = discord.Embed(
            title="Leave",
            description=f"{member} has left the server",
            color=discord.Color.red(),
        )
        embed.set_thumbnail(url=member.display_avatar)
        embed.timestamp = discord.utils.utcnow()
        await self.bot.sys_log(embed=embed)

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message) -> None:
        if after.author.bot or isinstance(after.channel, (discord.DMChannel, discord.GroupChannel)):
            return
        embed = discord.Embed(
            title="Edit Message",
            description=f"{after.author} edited their message in {after.channel.mention}."
            f"\n[Go to message]({after.jump_url})",
            color=discord.Color.blue(),
        )
        embed.set_thumbnail(url=after.author.display_avatar)
        embed.timestamp = discord.utils.utcnow()
        if len(after.content) > 1024 or len(before.content) > 1024:
            buffer = io.BytesIO()
            message = f"Before:\n {before.content}\nAfter:\n {after.content}"
            buffer.write(bytes(message, "utf-8"))
            buffer.seek(0)
            file = discord.File(buffer, filename="message_edit.txt")
            await self.bot.sys_log(embed=embed, file=file)
            return
        embed.add_field(name="Before", value=before.content if before.content else "No content")
        embed.add_field(name="After", value=after.content if after.content else "No content")
        await self.bot.sys_log(embed=embed)

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message) -> None:
        if message.author.bot or isinstance(message.channel, (discord.DMChannel, discord.GroupChannel)):
            return
        embed = discord.Embed(
            title="Delete Message",
            description=f"{message.author} deleted their message in {message.channel.mention}",
            color=discord.Color.red(),
        )
        embed.set_thumbnail(url=message.author.display_avatar)
        embed.timestamp = discord.utils.utcnow()
        if len(message.content) > 1024:
            buffer = io.BytesIO()
            message_content = f"Message:\n{message.content}"
            buffer.write(bytes(message_content, "utf-8"))
            buffer.seek(0)
            file = discord.File(buffer, filename="message_delete.txt")
            await self.bot.sys_log(embed=embed, file=file)
            return
        embed.add_field(name="Message", value=message.content if message.content else "No content")
        await self.bot.sys_log(embed=embed)

    @commands.Cog.listener()
    async def on_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState,
    ) -> None:
        if before.channel == after.channel or (before.channel is None and after.channel is None):
            return
        if before.channel is None and after.channel is not None:
            embed = discord.Embed(
                title="Join Voice",
                description=f"{member} has joined {after.channel.mention}",
                color=discord.Color.green(),
            )
            embed.set_thumbnail(url=member.display_avatar)
            embed.timestamp = discord.utils.utcnow()
            await self.bot.sys_log(embed=embed)
        elif after.channel is None and before.channel is not None:
            embed = discord.Embed(
                title="Leave Voice",
                description=f"{member} has left {before.channel.mention}",
                color=discord.Color.red(),
            )
            embed.set_thumbnail(url=member.display_avatar)
            embed.timestamp = discord.utils.utcnow()
            await self.bot.sys_log(embed=embed)
        elif before.mute != after.mute:
            valid_channel = t.cast(discord.VoiceChannel | discord.StageChannel, after.channel or before.channel)
            embed = discord.Embed(
                title="Mute",
                description=f"{member} has {'unmuted' if after.mute else 'muted'} {valid_channel.mention}",
                color=discord.Color.blue(),
            )
            embed.set_thumbnail(url=member.display_avatar)
            embed.timestamp = discord.utils.utcnow()
            await self.bot.sys_log(embed=embed)
        elif before.deaf != after.deaf:
            valid_channel = t.cast(discord.VoiceChannel | discord.StageChannel, after.channel or before.channel)
            embed = discord.Embed(
                title="Deaf",
                description=f"{member} has {'undeafed' if after.deaf else 'deafed'} {valid_channel.mention}",
                color=discord.Color.blue(),
            )
            embed.set_thumbnail(url=member.display_avatar)
            embed.timestamp = discord.utils.utcnow()
            await self.bot.sys_log(embed=embed)
        else:
            before_channel = t.cast(discord.VoiceChannel | discord.StageChannel, before.channel)
            after_channel = t.cast(discord.VoiceChannel | discord.StageChannel, after.channel)
            embed = discord.Embed(
                title="Move Voice",
                description=f"{member} has moved from {before_channel.mention} to {after_channel.mention}",
                color=discord.Color.blue(),
            )
            embed.set_thumbnail(url=member.display_avatar)
            embed.timestamp = discord.utils.utcnow()
            await self.bot.sys_log(embed=embed)

    @commands.Cog.listener()
    async def on_user_update(self, before: discord.User, after: discord.User) -> None:
        embed = discord.Embed(title="Update User", color=discord.Color.blue())
        embed.set_thumbnail(url=after.display_avatar)
        embed.timestamp = discord.utils.utcnow()
        if before.display_name != after.display_name:
            embed.description = f"{after.mention} has updated their name."
            embed.add_field(name="Before", value=before.display_name)
            embed.add_field(name="After", value=after.display_name)
            await self.bot.sys_log(embed=embed)
        elif before.avatar != after.avatar:
            embed.description = f"{after.mention} has updated their avatar."
            before_avatar = before.avatar or before.default_avatar
            after_avatar = after.avatar or after.default_avatar
            img = await self.bot.loop.run_in_executor(None, self.merge_images, before_avatar, after_avatar)
            file = discord.File(await img, filename="avatar_update.png")
            embed.set_image(url="attachment://avatar_update.png")
            await self.bot.sys_log(embed=embed, file=file)
        elif before.discriminator != after.discriminator:
            embed.description = f"{after.mention} has updated their discriminator."
            embed.add_field(name="Before", value=f"{before.discriminator}")
            embed.add_field(name="After", value=f"{after.discriminator}")
            await self.bot.sys_log(embed=embed)
        else:
            return

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member) -> None:
        embed = discord.Embed(title="Update Member", color=discord.Color.blue())
        embed.set_thumbnail(url=after.display_avatar)
        embed.timestamp = discord.utils.utcnow()
        if before.nick != after.nick:
            embed.description = f"{after.mention} has updated their nickname."
            embed.add_field(name="Before", value=before.nick)
            embed.add_field(name="After", value=after.nick)
            await self.bot.sys_log(embed=embed)
        elif before.roles != after.roles:
            embed.description = f"{after.mention} has updated their roles."
            embed.add_field(name="Before", value=", ".join([role.mention for role in before.roles]))
            embed.add_field(name="After", value=", ".join([role.mention for role in after.roles]))
            await self.bot.sys_log(embed=embed)
        elif before.guild_avatar != after.guild_avatar:
            embed.description = f"{after.mention} has updated their guild avatar."
            before_guild_avatar = before.guild_avatar or before.default_avatar
            after_guild_avatar = after.guild_avatar or after.default_avatar
            img = await self.bot.loop.run_in_executor(None, self.merge_images, before_guild_avatar, after_guild_avatar)
            file = discord.File(await img, filename="guild_avatar.png")
            embed.set_image(url="attachment://guild_avatar.png")
            await self.bot.sys_log(embed=embed, file=file)
        else:
            pass

    @commands.Cog.listener()
    async def on_member_ban(self, guild: discord.Guild, user: discord.Member) -> None:
        embed = discord.Embed(
            title="Ban",
            description=f"{user} has been banned from {guild.name}",
            color=discord.Color.red(),
        )
        embed.set_thumbnail(url=user.display_avatar)
        embed.timestamp = discord.utils.utcnow()
        await self.bot.sys_log(embed=embed)

    @commands.Cog.listener()
    async def on_member_unban(self, guild: discord.Guild, user: discord.Member) -> None:
        embed = discord.Embed(
            title="Unban",
            description=f"{user} has been unbanned from {guild.name}",
            color=discord.Color.green(),
        )
        embed.set_thumbnail(url=user.display_avatar)
        embed.timestamp = discord.utils.utcnow()
        await self.bot.sys_log(embed=embed)

    @commands.Cog.listener()
    async def on_guild_update(self, before: discord.Guild, after: discord.Guild) -> None:
        embed = discord.Embed(title="Update Guild", color=discord.Color.blue())
        embed.set_thumbnail(url=after.icon)
        embed.timestamp = discord.utils.utcnow()
        if before.description != after.description:
            embed.description = f"{after.name} has updated their description."
            embed.add_field(name="Before", value=before.description)
            embed.add_field(name="After", value=after.description)
            await self.bot.sys_log(embed=embed)
        elif before.name != after.name:
            embed.description = f"{after.name} has updated their name."
            embed.add_field(name="Before", value=before.name)
            embed.add_field(name="After", value=after.name)
            await self.bot.sys_log(embed=embed)
        elif before.icon != after.icon:
            embed.description = f"{after.name} has updated their icon."
            embed.add_field(name="Before", value=before.icon)
            embed.add_field(name="After", value=after.icon)
            await self.bot.sys_log(embed=embed)
        elif before.roles != after.roles:
            embed.description = f"Roles updated for {after.name}."
            embed.add_field(name="Before", value=", ".join([role.mention for role in before.roles]))
            embed.add_field(name="After", value=", ".join([role.mention for role in after.roles]))
            await self.bot.sys_log(embed=embed)
        else:
            pass

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel: discord.TextChannel) -> None:
        embed = discord.Embed(
            title="Create Channel",
            description=f"{channel.mention} has been created.",
            color=discord.Color.blue(),
        )
        embed.set_thumbnail(url=channel.guild.icon)
        embed.timestamp = discord.utils.utcnow()
        await self.bot.sys_log(embed=embed)

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel: discord.TextChannel) -> None:
        embed = discord.Embed(
            title="Delete Channel",
            description=f"{channel.name} has been deleted.",
            color=discord.Color.red(),
        )
        embed.set_thumbnail(url=channel.guild.icon)
        embed.timestamp = discord.utils.utcnow()
        await self.bot.sys_log(embed=embed)

    @commands.Cog.listener()
    async def on_guild_channel_update(self, before: discord.TextChannel, after: discord.TextChannel) -> None:
        embed = discord.Embed(title="Update Channel", color=discord.Color.blue())
        embed.set_thumbnail(url=after.guild.icon)
        embed.timestamp = discord.utils.utcnow()
        if before.name != after.name:
            embed.description = f"{after.mention} has updated their name."
            embed.add_field(name="Before", value=before.name)
            embed.add_field(name="After", value=after.name)
            await self.bot.sys_log(embed=embed)
        elif before.topic != after.topic:
            embed.description = f"{after.mention} has updated their topic."
            embed.add_field(name="Before", value=before.topic)
            embed.add_field(name="After", value=after.topic)
            await self.bot.sys_log(embed=embed)
        elif before.position != after.position:
            embed.description = f"{after.mention} has updated their position."
            embed.add_field(name="Before", value=before.position)
            embed.add_field(name="After", value=after.position)
            await self.bot.sys_log(embed=embed)
        elif before.category != after.category:
            embed.description = f"{after.mention} has updated their category."
            before_category = before.category.mention if before.category else "No Category"
            after_category = after.category.mention if after.category else "No Category"
            embed.add_field(name="Before", value=before_category)
            embed.add_field(name="After", value=after_category)
            await self.bot.sys_log(embed=embed)
        else:
            pass

    @commands.Cog.listener()
    async def on_guild_channel_pins_update(self, channel: discord.TextChannel, last_pin: datetime.datetime) -> None:
        embed = discord.Embed(
            title="Update Channel",
            description=f"{channel.mention} has updated their pins.",
            color=discord.Color.blue(),
        )
        embed.set_thumbnail(url=channel.guild.icon)
        embed.timestamp = discord.utils.utcnow()
        embed.add_field(name="Last Pin", value=last_pin)
        await self.bot.sys_log(embed=embed)

    @commands.Cog.listener()
    async def on_guild_emojis_update(
        self,
        guild: discord.Guild,
        before: list[discord.Emoji],
        after: list[discord.Emoji],
    ) -> None:
        embed = discord.Embed(
            title="Update Emojis",
            description=f"{guild.name} has updated their emojis.",
            color=discord.Color.blue(),
        )
        embed.set_thumbnail(url=guild.icon)
        embed.timestamp = discord.utils.utcnow()
        embed.add_field(name="Before", value=", ".join([str(i) for i in before]))
        embed.add_field(name="After", value=", ".join([str(i) for i in after]))
        await self.bot.sys_log(embed=embed)

    @commands.Cog.listener()
    async def on_guild_stickers_update(
        self,
        guild: discord.Guild,
        before: list[discord.Sticker],
        after: list[discord.Sticker],
    ) -> None:
        embed = discord.Embed(
            title="Update Stickers",
            description=f"{guild.name} has updated their stickers.",
            color=discord.Color.blue(),
        )
        embed.set_thumbnail(url=guild.icon)
        embed.timestamp = discord.utils.utcnow()
        embed.add_field(name="Before", value=", ".join([sticker.name for sticker in before]))
        embed.add_field(name="After", value=", ".join([sticker.name for sticker in after]))
        await self.bot.sys_log(embed=embed)

    @commands.Cog.listener()
    async def on_guild_integrations_update(self, guild: discord.Guild) -> None:
        embed = discord.Embed(
            title="Update Integrations",
            description=f"{guild.name} has updated their integrations.",
            color=discord.Color.blue(),
        )
        embed.set_thumbnail(url=guild.icon)
        embed.timestamp = discord.utils.utcnow()
        await self.bot.sys_log(embed=embed)

    @commands.Cog.listener()
    async def on_integration_create(self, integration: discord.Integration) -> None:
        embed = discord.Embed(
            title="Create Integration",
            description=f"{integration.name} has been created.",
            color=discord.Color.blue(),
        )
        embed.set_thumbnail(url=integration.guild.icon)
        embed.timestamp = discord.utils.utcnow()
        await self.bot.sys_log(embed=embed)

    @commands.Cog.listener()
    async def on_integration_delete(self, integration: discord.Integration) -> None:
        embed = discord.Embed(
            title="Delete Integration",
            description=f"{integration.name} has been deleted.",
            color=discord.Color.red(),
        )
        embed.set_thumbnail(url=integration.guild.icon)
        embed.timestamp = discord.utils.utcnow()
        await self.bot.sys_log(embed=embed)

    @commands.Cog.listener()
    async def on_guild_role_create(self, role: discord.Role) -> None:
        embed = discord.Embed(
            title="Create Role",
            description=f"{role.mention} has been created.",
            color=discord.Color.blue(),
        )
        embed.set_thumbnail(url=role.guild.icon)
        embed.timestamp = discord.utils.utcnow()
        await self.bot.sys_log(embed=embed)

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role: discord.Role) -> None:
        embed = discord.Embed(
            title="Delete Role",
            description=f"{role.mention} has been deleted.",
            color=discord.Color.red(),
        )
        embed.set_thumbnail(url=role.guild.icon)
        embed.timestamp = discord.utils.utcnow()
        await self.bot.sys_log(embed=embed)

    @commands.Cog.listener()
    async def on_guild_role_update(self, before: discord.Role, after: discord.Role) -> None:
        embed = discord.Embed(title="Update Role", color=discord.Color.blue())
        embed.set_thumbnail(url=after.guild.icon)
        embed.timestamp = discord.utils.utcnow()
        if before.name != after.name:
            embed.description = f"{after.mention} has updated their name."
            embed.add_field(name="Before", value=before.name)
            embed.add_field(name="After", value=after.name)
            await self.bot.sys_log(embed=embed)
        elif before.color != after.color:
            embed.description = f"{after.mention} has updated their color."
            embed.add_field(name="Before", value=before.color)
            embed.add_field(name="After", value=after.color)
            await self.bot.sys_log(embed=embed)
        elif before.hoist != after.hoist:
            embed.description = f"{after.mention} has updated their hoist."
            embed.add_field(name="Before", value=before.hoist)
            embed.add_field(name="After", value=after.hoist)
            await self.bot.sys_log(embed=embed)
        elif before.mentionable != after.mentionable:
            embed.description = f"{after.mention} has updated their mentionable."
            embed.add_field(name="Before", value=before.mentionable)
            embed.add_field(name="After", value=after.mentionable)
            await self.bot.sys_log(embed=embed)
        elif before.permissions != after.permissions:
            embed.description = f"{after.mention} has updated their permissions."
            embed.add_field(name="Before", value=before.permissions)
            embed.add_field(name="After", value=after.permissions)
            await self.bot.sys_log(embed=embed)
        else:
            pass


async def setup(bot: HackspaceBot) -> None:
    await bot.add_cog(ModLog(bot))
