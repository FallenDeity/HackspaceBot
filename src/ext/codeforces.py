from __future__ import annotations

import asyncio
import collections
import datetime
import enum
import logging
import typing as t

import attrs
import discord
import humanfriendly
from discord import app_commands
from discord.ext import tasks

from src.utils.ansi import AnsiBuilder, Colors, Styles
from src.utils.constants import CODEFORCES_ORGS, Campus
from src.views.paginators.advanced import CategoryEntry, EmbedCategoryPaginator
from src.views.paginators.button import EmbedButtonPaginator

from . import BaseCog

if t.TYPE_CHECKING:
    from src.core.bot import HackspaceBot


logger = logging.getLogger(__name__)


class ContestType(enum.StrEnum):
    CF = "CF"
    IOI = "IOI"
    ICPC = "ICPC"


class ContestPhase(enum.StrEnum):
    BEFORE = "BEFORE"
    CODING = "CODING"
    PENDING_SYSTEM_TEST = "PENDING_SYSTEM_TEST"
    SYSTEM_TEST = "SYSTEM_TEST"
    FINISHED = "FINISHED"


@attrs.define(kw_only=True, eq=True, frozen=True, slots=True)
class CFContest:
    id: int
    name: str
    type: ContestType
    phase: ContestPhase
    frozen: bool
    durationSeconds: int
    freezeDurationSeconds: int | None = None
    startTimeSeconds: int | None = None
    relativeTimeSeconds: int | None = None
    preparedBy: str | None = None
    websiteUrl: str | None = None
    description: str | None = None
    difficulty: t.Literal[1, 2, 3, 4, 5] | None = None
    kind: str | None = None
    icpcRegion: str | None = None
    country: str | None = None
    city: str | None = None
    season: str | None = None


@attrs.define(kw_only=True, eq=True, frozen=True, slots=True)
class CFUser:
    handle: str
    contribution: int
    rank: str
    rating: int
    maxRank: str
    maxRating: int
    lastOnlineTimeSeconds: int
    registrationTimeSeconds: int
    friendOfCount: int
    avatar: str
    titlePhoto: str
    email: str | None = None
    vkId: int | None = None
    openId: str | None = None
    firstName: str | None = None
    lastName: str | None = None
    country: str | None = None
    city: str | None = None
    organization: str | None = None


class CodeForcesCog(BaseCog):
    _lock: asyncio.Lock = asyncio.Lock()

    _upcoming_contests: list[CFContest] = []
    _ongoing_contests: list[CFContest] = []
    _finished_pending_contests: list[CFContest] = []

    _campus_leaderboards: t.DefaultDict[Campus, list[CFUser]] = collections.defaultdict(list)

    async def _fetch_ranked_contests(self) -> list[CFContest]:
        url = "https://codeforces.com/api/contest.list?gym=false"
        async with self.bot.client.get(url) as resp:
            data = await resp.json()
            contests = [CFContest(**contest) for contest in data["result"]]
            logger.info(f"Fetched {len(contests)} ranked contests.")
            return contests

    async def _fetch_ranked_contest(self, contest_id: int) -> CFContest | None:
        url = f"https://codeforces.com/api/contest.standings?contestId={contest_id}&from=1&count=1"
        async with self.bot.client.get(url) as resp:
            data = await resp.json()
            if "result" not in data:
                return None
            contest_data = data["result"]["contest"]
            contest = CFContest(**contest_data)
            logger.info(f"Fetched details for contest: {contest.name} (ID: {contest.id}).")
            return contest

    async def _fetch_user_rated_list(self) -> list[CFUser]:
        url = "https://codeforces.com/api/user.ratedList?includeRetired=false"
        async with self.bot.client.get(url) as resp:
            data = await resp.json()
            users = [CFUser(**user) for user in data["result"]]
            logger.info(f"Fetched {len(users)} rated users.")
            return users

    async def _rating_published(self, contest: CFContest) -> bool:
        url = f"https://codeforces.com/api/contest.ratingChanges?contestId={contest.id}"
        async with self.bot.client.get(url) as resp:
            data = await resp.json()
            logger.info(f"Fetched rating changes for contest: {contest.name} (ID: {contest.id}).")
            if "result" not in data or not data["result"]:
                return False
            return True

    async def _refresh_campus_leaderboards(self) -> None:
        users = await self._fetch_user_rated_list()
        campus_leaderboards: t.DefaultDict[Campus, list[CFUser]] = collections.defaultdict(list)

        user_online_cutoff = datetime.datetime.now(datetime.timezone.utc).timestamp() - (180 * 24 * 3600)  # 180 days
        for user in users:
            if user.lastOnlineTimeSeconds < user_online_cutoff:
                continue
            for campus, org_ids in CODEFORCES_ORGS.items():
                if user.organization and any(org_id.casefold() == user.organization.casefold() for org_id in org_ids):
                    campus_leaderboards[campus].append(user)
                    break
        for campus in campus_leaderboards:
            campus_leaderboards[campus].sort(key=lambda u: u.rating, reverse=True)

        async with self._lock:
            self._campus_leaderboards = campus_leaderboards
            logger.info(f"Refreshed campus leaderboards for {len(campus_leaderboards)} campuses.")

    @tasks.loop(hours=1)
    async def update_upcoming_contests(self) -> None:
        contests = await self._fetch_ranked_contests()
        now = datetime.datetime.now(datetime.timezone.utc).timestamp()
        upcoming = [c for c in contests if c.phase == ContestPhase.BEFORE and (c.startTimeSeconds or 0) > now]
        ongoing = [
            c
            for c in contests
            if c.phase == ContestPhase.CODING
            or (
                c.phase in (ContestPhase.PENDING_SYSTEM_TEST, ContestPhase.SYSTEM_TEST)
                and (now - (c.startTimeSeconds or 0)) < 7 * 24 * 3600  # active within a week
            )
        ]
        async with self._lock:
            self._upcoming_contests = upcoming
            self._ongoing_contests += [i for i in ongoing if not discord.utils.get(self._ongoing_contests, id=i.id)]

    @tasks.loop(seconds=30)
    async def check_ongoing_contests(self) -> None:
        now = datetime.datetime.now(datetime.timezone.utc).timestamp()
        async with self._lock:
            to_move = [contest for contest in self._upcoming_contests if (contest.startTimeSeconds or 0) <= now]
            self._ongoing_contests += [
                contest for contest in to_move if not discord.utils.get(self._ongoing_contests, id=contest.id)
            ]
            self._upcoming_contests = [
                contest for contest in self._upcoming_contests if not discord.utils.get(to_move, id=contest.id)
            ]

    @tasks.loop(minutes=5)
    async def refresh_ongoing_contests(self) -> None:
        now = datetime.datetime.now(datetime.timezone.utc).timestamp()
        max_age = 7 * 24 * 3600  # 7 days

        async with self._lock:
            stale = [contest for contest in self._ongoing_contests if (now - (contest.startTimeSeconds or 0)) > max_age]
            self._ongoing_contests = [
                contest for contest in self._ongoing_contests if not discord.utils.get(stale, id=contest.id)
            ]
            ongoing_contests = self._ongoing_contests.copy()

        updated_contests = await asyncio.gather(
            *(self._fetch_ranked_contest(contest.id) for contest in ongoing_contests)
        )

        async with self._lock:
            for updated in updated_contests:
                if updated is None:
                    continue
                if updated.phase == ContestPhase.FINISHED:
                    self._ongoing_contests = [c for c in self._ongoing_contests if c.id != updated.id]
                    if not discord.utils.get(self._finished_pending_contests, id=updated.id):
                        self._finished_pending_contests.append(updated)
                else:
                    for idx, contest in enumerate(self._ongoing_contests):
                        if contest.id == updated.id:
                            self._ongoing_contests[idx] = updated
                            break

    @tasks.loop(minutes=10)
    async def update_campus_leaderboards(self) -> None:
        async with self._lock:
            pending_contests = self._finished_pending_contests.copy()

        results = await asyncio.gather(*(self._rating_published(contest) for contest in pending_contests))
        to_remove = [contest for contest, published in zip(pending_contests, results) if published]

        if to_remove:
            await self._refresh_campus_leaderboards()

            async with self._lock:
                self._finished_pending_contests = [c for c in self._finished_pending_contests if c not in to_remove]

    async def cog_load(self) -> None:
        await super().cog_load()
        # await self._refresh_campus_leaderboards()

    def _build_user_pages(
        self,
        campus: Campus,
        users: list[CFUser],
    ) -> list[discord.Embed]:
        entries: list[discord.Embed] = []
        per_page = 10
        total_pages = (len(users) + per_page - 1) // per_page
        for page in range(total_pages):
            start_idx = page * per_page
            end_idx = start_idx + per_page
            embed = discord.Embed(
                title=f"CodeForces Leaderboard - {campus} Campus",
                description=f"Top CodeForces users from {campus} campus",
                color=discord.Color.blue(),
            )
            for rank, user in enumerate(users[start_idx:end_idx], start=start_idx + 1):
                embed.add_field(
                    name=f"\\#{rank} - {user.firstName} {user.lastName} ({user.handle})",
                    value=f"Rating: `{user.rating}` | Max Rating: `{user.maxRating}` | Rank: `{user.rank}` | [View Profile](https://codeforces.com/profile/{user.handle})",
                    inline=False,
                )
            embed.set_thumbnail(
                url="https://cdn.discordapp.com/attachments/1434976754597892178/1436123161702961354/codeforces-logo.jpg"
            )
            embed.set_footer(text=f"Page {page + 1} of {total_pages}", icon_url=self.bot.user.display_avatar)
            embed.timestamp = discord.utils.utcnow()
            entries.append(embed)
        return entries

    @app_commands.command(name="leaderboard")
    async def campus_leaderboard(
        self, interaction: discord.Interaction[HackspaceBot], campus: Campus | None = None
    ) -> None:
        """
        Display the CodeForces leaderboard for a specific campus or all campuses.

        Parameters
        ----------
        campus : Campus | None
            The campus to display the leaderboard for. If None, displays leaderboards for all campuses.
        """
        async with self._lock:
            leaderboard = self._campus_leaderboards.copy()

        if not leaderboard:
            await interaction.edit_original_response(content="No leaderboard data available yet.")
            return

        if campus:
            users = leaderboard.get(campus, [])
            if not users:
                await interaction.edit_original_response(content=f"No users found for {campus} campus.")
                return
            pages = self._build_user_pages(campus, users)
            paginator = EmbedButtonPaginator(user=interaction.user, pages=pages)
            await paginator.start_paginator(interaction)
            return

        categories: list[CategoryEntry[discord.Embed]] = []
        for campus in leaderboard:
            users = leaderboard[campus]
            pages = self._build_user_pages(campus, users)
            categories.append(CategoryEntry(category_title=campus, pages=pages))

        paginator = EmbedCategoryPaginator(user=interaction.user, pages=categories)
        await paginator.start_paginator(interaction)

    @app_commands.command(name="upcoming_contests")
    async def upcoming_contests(self, interaction: discord.Interaction[HackspaceBot]) -> None:
        """
        Display the list of upcoming CodeForces contests.
        """
        async with self._lock:
            upcoming = self._upcoming_contests.copy()

        if not upcoming:
            await interaction.edit_original_response(content="There are no upcoming CodeForces contests at the moment.")
            return

        entries: list[discord.Embed] = []
        for n, contest in enumerate(upcoming, start=1):
            embed = discord.Embed(
                title=contest.name,
                description=(
                    AnsiBuilder.from_string(f"Contest ID: {contest.id} ({contest.type})\n", Colors.BLUE, Styles.BOLD)
                    + AnsiBuilder.from_string(
                        f"Duration: {humanfriendly.format_timespan(contest.durationSeconds)}\n",
                        Colors.BLUE,
                        Styles.BOLD,
                    )
                ),
                color=discord.Color.green(),
            )
            if contest.startTimeSeconds:
                start_time = datetime.datetime.fromtimestamp(contest.startTimeSeconds, tz=datetime.timezone.utc)
                embed.add_field(
                    name="Start Time (UTC)", value=f"{discord.utils.format_dt(start_time, style='F')}", inline=True
                )

            embed.add_field(name="\u200b", value="\u200b", inline=True)

            url = contest.websiteUrl or "https://codeforces.com/contests"
            embed.add_field(name="Contest Link", value=f"[Go to Contest]({url})", inline=True)

            embed.set_thumbnail(
                url="https://cdn.discordapp.com/attachments/1434976754597892178/1436123161702961354/codeforces-logo.jpg"
            )
            embed.set_footer(text=f"Page {n} of {len(upcoming)}", icon_url=self.bot.user.display_avatar)
            embed.timestamp = discord.utils.utcnow()
            entries.append(embed)

        paginator = EmbedButtonPaginator(user=interaction.user, pages=entries)
        await paginator.start_paginator(interaction)


async def setup(bot: HackspaceBot) -> None:
    await bot.add_cog(CodeForcesCog(bot))
