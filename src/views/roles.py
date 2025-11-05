import base64
import re
import typing as t

import discord
from discord.ui.item import Item

from src.views import BaseView

__all__ = (
    "DynamicRoleSelect",
    "ReactionRolesSetup",
)


def _encode_roles(role_ids: list[int]) -> str:
    """Encode a list of role IDs directly with Base85 (no struct)."""
    data = b"".join(r.to_bytes(8, "big") for r in role_ids)
    return base64.b85encode(data).decode()


def _decode_roles(encoded: str) -> list[int]:
    """Decode Base85 back to role IDs (8 bytes per ID)."""
    data = base64.b85decode(encoded)
    return [int.from_bytes(data[i : i + 8], "big") for i in range(0, len(data), 8)]


class DynamicRoleSelect(discord.ui.DynamicItem[discord.ui.RoleSelect[discord.ui.View]], template=r"^(?P<data>.+)$"):
    def __init__(self, *, roles: list[int]):
        print("Encoding roles:", roles)
        self.roles = roles
        super().__init__(
            discord.ui.RoleSelect(
                custom_id=_encode_roles(roles),
                placeholder="Select your roles",
                min_values=1,
                max_values=1,
            )
        )

    @classmethod
    async def from_custom_id(
        cls: type[t.Self], interaction: discord.Interaction, item: Item[t.Any], match: re.Match[str]
    ) -> t.Self:
        print("Decoding roles from custom_id:", match.group("data"))
        return cls(roles=_decode_roles(match.group("data")))

    async def callback(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        if interaction.guild is None:
            await interaction.followup.send(content="This interaction can only be used in a guild.", ephemeral=True)
            return
        selected = self.item.values[0]
        if selected.id not in (self.roles or []):
            await interaction.followup.send(content="You cannot select this role.", ephemeral=True)
            return
        member = interaction.guild.get_member(interaction.user.id) or await interaction.guild.fetch_member(
            interaction.user.id
        )
        role = interaction.guild.get_role(selected.id) or await interaction.guild.fetch_role(selected.id)

        if role in member.roles:
            await interaction.followup.send(content=f"You already have the role: {role.mention}", ephemeral=True)
            return

        for check_role in self.roles:
            r = interaction.guild.get_role(check_role) or await interaction.guild.fetch_role(check_role)
            if r in member.roles:
                await member.remove_roles(r, reason="User selected a different role via DynamicRoleSelect")

        await member.add_roles(role, reason="User selected role via DynamicRoleSelect")
        await interaction.followup.send(content=f"You have been given the role: {role.mention}", ephemeral=True)


class ReactionRolesSetup(BaseView):
    @discord.ui.select(
        cls=discord.ui.RoleSelect,
        placeholder="Select a role",
        min_values=1,
        max_values=10,
        custom_id="reaction_roles_setup_select",
    )
    async def role_select(
        self, interaction: discord.Interaction, select: discord.ui.RoleSelect["ReactionRolesSetup"]
    ) -> None:
        await interaction.response.defer()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger, custom_id="reaction_roles_setup_cancel")
    async def cancel_button(
        self, interaction: discord.Interaction, button: discord.ui.Button["ReactionRolesSetup"]
    ) -> None:
        await interaction.response.defer()
        await interaction.delete_original_response()
        self.stop()

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.success, custom_id="reaction_roles_setup_confirm")
    async def confirm_button(
        self, interaction: discord.Interaction, button: discord.ui.Button["ReactionRolesSetup"]
    ) -> None:
        await interaction.response.defer()
        selected_roles = self.role_select.values
        embed = discord.Embed(
            title="Reaction Roles Setup",
            description=f"Selected Roles: {', '.join(role.mention for role in selected_roles)}",
            color=discord.Color.blurple(),
        )
        embed.timestamp = discord.utils.utcnow()
        embed.set_thumbnail(url=interaction.client.user.display_avatar)  # type: ignore
        embed.set_footer(text="Please use the select menu below to assign yourself roles.")
        await interaction.edit_original_response(content="Reaction roles have been set up successfully.", view=None)

        view = discord.ui.View(timeout=None)
        view.add_item(DynamicRoleSelect(roles=[role.id for role in selected_roles]))
        await interaction.channel.send(embed=embed, view=view)  # type: ignore

        self.stop()
