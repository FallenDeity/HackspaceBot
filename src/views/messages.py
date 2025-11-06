import re
import typing as t

import discord

from src.utils.constants import ButtonEmoji

__all__: tuple[str, ...] = ("DynamicDeleteButton",)


class DynamicDeleteButton(
    discord.ui.DynamicItem[discord.ui.Button[discord.ui.View]], template=r"user:(?P<user_id>\d+)$"
):
    def __init__(self, *, user_id: int):
        self.user_id = user_id
        super().__init__(
            discord.ui.Button(
                style=discord.ButtonStyle.gray,
                label="Delete",
                custom_id=f"user:{user_id}",
                emoji=discord.PartialEmoji.from_str(ButtonEmoji.STOP),
            )
        )

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.user_id

    @classmethod
    async def from_custom_id(
        cls: type[t.Self], interaction: discord.Interaction, item: discord.ui.Item[t.Any], match: re.Match[str]
    ) -> t.Self:
        return cls(user_id=int(match.group("user_id")))

    async def callback(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        await interaction.delete_original_response()
