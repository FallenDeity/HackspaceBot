from __future__ import annotations

from typing import TYPE_CHECKING, Generic, List, TypeVar, Union

import discord
from discord import PartialEmoji
from discord.ext.commands.context import Context

from src.views.paginators import BasePaginator, FileLike, PageLike

if TYPE_CHECKING:
    from src.core.bot import HackspaceBot
    from src.views import BaseView


__all__: tuple[str, ...] = (
    "ButtonBasedPaginator",
    "EmbedButtonPaginator",
    "FileButtonPaginator",
    "StringButtonPaginator",
)


T = TypeVar("T", bound=PageLike)


class ButtonBasedPaginator(Generic[T], BasePaginator[T]):
    async def send_page(
        self, ctx_or_inter: Context[HackspaceBot] | discord.Interaction[discord.Client], page: T
    ) -> None:
        self.previous_page_callback.disabled = self.goto_first_page_callback.disabled = self.current_page == 0
        self.next_page_callback.disabled = self.goto_last_page_callback.disabled = (
            self.current_page == len(self.pages) - 1
        )
        return await super().send_page(ctx_or_inter, page)

    @discord.ui.button(emoji=PartialEmoji.from_str("⏪"))
    async def goto_first_page_callback(self, inter: discord.Interaction, _: discord.ui.Button[BaseView]) -> None:
        await inter.response.defer()
        self.current_page = 0
        page = self.pages[self.current_page]
        await self.send_page(inter, page)

    @discord.ui.button(emoji=PartialEmoji.from_str("◀️"))
    async def previous_page_callback(self, inter: discord.Interaction, _: discord.ui.Button[BaseView]) -> None:
        await inter.response.defer()
        await self.previous_page(inter)

    @discord.ui.button(emoji=PartialEmoji.from_str("▶️"))
    async def next_page_callback(self, inter: discord.Interaction, _: discord.ui.Button[BaseView]) -> None:
        await inter.response.defer()
        await self.next_page(inter)

    @discord.ui.button(emoji=PartialEmoji.from_str("⏩"))
    async def goto_last_page_callback(self, inter: discord.Interaction, _: discord.ui.Button[BaseView]) -> None:
        await inter.response.defer()
        self.current_page = len(self.pages) - 1
        page = self.pages[self.current_page]
        await self.send_page(inter, page)

    @discord.ui.button(emoji=PartialEmoji.from_str("🗑️"))
    async def stop_paginator_callback(self, inter: discord.Interaction, _: discord.ui.Button[BaseView]) -> None:
        await inter.response.defer()
        await self.stop_paginator()


class EmbedButtonPaginator(ButtonBasedPaginator[discord.Embed]):
    def __init__(
        self,
        user: Union[discord.User, discord.Member],
        pages: List[discord.Embed],
        *,
        attachments: List[discord.File] | None = None,
    ) -> None:
        super().__init__(user, pages, attachments=attachments)


class FileButtonPaginator(ButtonBasedPaginator[FileLike]):
    def __init__(self, user: Union[discord.User, discord.Member], pages: List[FileLike]) -> None:
        super().__init__(user, pages)


class StringButtonPaginator(ButtonBasedPaginator[str]):
    def __init__(
        self,
        user: Union[discord.User, discord.Member],
        pages: List[str],
        *,
        attachments: List[discord.File] | None = None,
    ) -> None:
        super().__init__(user, pages, attachments=attachments)
