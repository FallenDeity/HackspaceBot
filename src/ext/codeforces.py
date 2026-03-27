from __future__ import annotations

import asyncio
import collections
import datetime
import enum
import logging
import typing as t
from pathlib import Path

import attrs
import discord
import humanfriendly
from discord import app_commands
from discord.ext import tasks

from src.utils.ansi import AnsiBuilder, Colors, Styles
from src.utils.constants import CODEFORCES_ORGS, Campus, Channels, ConfigKey, Paths, Roles
from src.utils.features import FeatureKey
from src.views.paginators.advanced import CategoryEntry, EmbedCategoryPaginator
from src.views.paginators.button import EmbedButtonPaginator

from . import BaseCog

if t.TYPE_CHECKING:
    from src.core.bot import HackspaceBot


logger = logging.getLogger(__name__)
CODEFORCES_LOGO_PATH = Path(Paths.RESOURCES) / "codeforces-logo.jpg"
CODEFORCES_LOGO_FILENAME = CODEFORCES_LOGO_PATH.name
CODEFORCES_LOGO_ATTACHMENT_URL = f"attachment://{CODEFORCES_LOGO_FILENAME}"


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


class CodeForcesCog(BaseCog, name="CodeForces"):
    """Commands related to CodeForces contests and users."""

    _lock: asyncio.Lock = asyncio.Lock()

    _upcoming_contests: list[CFContest] = []
    _ongoing_contests: list[CFContest] = []
    _finished_pending_contests: list[CFContest] = []

    _campus_leaderboards: t.DefaultDict[Campus, list[CFUser]] = collections.defaultdict(list)

    async def _notification_milestones(self) -> list[int]:
        raw = await self.bot.db.config.get(ConfigKey.CONTEST_NOTIFICATION_MILESTONES)
        values = t.cast(list[t.Any], raw)
        normalized = sorted({value for value in values if isinstance(value, int) and value > 0}, reverse=True)
        return normalized

    async def _send_notification(self, contest: CFContest, *, announcement: bool) -> bool:
        channel_obj = self.bot.get_channel(Channels.CONTESTS) or await self.bot.fetch_channel(Channels.CONTESTS)
        if not isinstance(channel_obj, discord.TextChannel):
            logger.warning("Contest notification channel is unavailable.")
            return False

        contest_url = contest.websiteUrl or f"https://codeforces.com/contest/{contest.id}"

        if contest.startTimeSeconds is None:
            start_relative = "Unknown"
            start_display = "Unknown"
            start_dt = None
        else:
            start_dt = datetime.datetime.fromtimestamp(contest.startTimeSeconds, tz=datetime.timezone.utc)
            start_relative = discord.utils.format_dt(start_dt, style="R")
            start_display = discord.utils.format_dt(start_dt, style="F")

        if announcement:
            title = f"New CodeForces Contest · {contest.name}"
            summary = AnsiBuilder.from_string("ANNOUNCEMENT\n", Colors.GREEN, Styles.BOLD) + AnsiBuilder.from_string(
                f"Contest #{contest.id} is now on the radar.", Colors.BLUE, Styles.BOLD
            )
            color = discord.Color.blurple()
        else:
            title = f"CodeForces Reminder · {contest.name}"
            summary = AnsiBuilder.from_string("REMINDER\n", Colors.YELLOW, Styles.BOLD) + AnsiBuilder.from_string(
                f"Contest #{contest.id} starts {start_relative}.", Colors.BLUE, Styles.BOLD
            )
            color = discord.Color.orange()

        embed = discord.Embed(
            title=title,
            url=contest_url,
            description=summary,
            color=color,
        )
        embed.set_author(name="CodeForces", url="https://codeforces.com/", icon_url=CODEFORCES_LOGO_ATTACHMENT_URL)
        embed.set_thumbnail(url=CODEFORCES_LOGO_ATTACHMENT_URL)
        embed.add_field(name="Contest ID", value=f"`#{contest.id}`", inline=True)
        embed.add_field(name="Type", value=f"`{contest.type}`", inline=True)
        embed.add_field(name="Phase", value=f"`{contest.phase}`", inline=True)
        embed.add_field(name="Duration", value=humanfriendly.format_timespan(contest.durationSeconds), inline=True)
        embed.add_field(name="Starts In", value=start_relative, inline=True)
        embed.add_field(name="Start Time (UTC)", value=start_display, inline=True)
        if start_dt is not None:
            embed.timestamp = start_dt
        else:
            embed.timestamp = discord.utils.utcnow()
        embed.set_footer(text="HackspaceBot · CodeForces Alerts", icon_url=self.bot.user.display_avatar)

        view = discord.ui.View()
        view.add_item(discord.ui.Button(label="Open Contest", style=discord.ButtonStyle.link, url=contest_url))
        view.add_item(
            discord.ui.Button(
                label="All Contests",
                style=discord.ButtonStyle.link,
                url="https://codeforces.com/contests",
            )
        )
        logo_file = discord.File(CODEFORCES_LOGO_PATH, filename=CODEFORCES_LOGO_FILENAME)
        await channel_obj.send(content=f"<@&{Roles.CONTESTS}>", embed=embed, view=view, file=logo_file)
        return True

    async def _evaluate_notifications(self) -> None:
        logger.info("Evaluating upcoming contest notifications...")
        now = int(datetime.datetime.now(datetime.timezone.utc).timestamp())
        notifications_enabled = await self.bot.features.is_enabled(FeatureKey.CODEFORCES_NOTIFICATIONS)
        milestones = await self._notification_milestones()

        async with self._lock:
            contests = self._upcoming_contests.copy()

        for contest in contests:
            start_time = contest.startTimeSeconds
            if start_time is None:
                continue

            current_state = await self.bot.db.contest_notifications.upsert_contest(contest.id, start_time)

            sent = set(current_state.milestones_sent)
            missed = set(current_state.milestones_missed)
            time_until_start = start_time - now

            if current_state.announced_at is None:
                if notifications_enabled:
                    await self._send_notification(contest, announcement=True)
                await self.bot.db.contest_notifications.mark_announced(contest.id)

            if due_unsent := [m for m in milestones if time_until_start <= m and m not in sent and m not in missed]:
                latest_due = min(due_unsent)
                older_due = [m for m in due_unsent if m != latest_due]
                missed.update(older_due)

                sent_ok = await self._send_notification(contest, announcement=False) if notifications_enabled else False
                (sent if sent_ok else missed).add(latest_due)

                await self.bot.db.contest_notifications.update_milestone_sets(
                    contest.id,
                    list(sent),
                    list(missed),
                )

            if start_time <= now:
                await self.bot.db.contest_notifications.delete(contest.id)
        logger.info("Finished evaluating contest notifications.")

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
        logger.info("Refreshing campus leaderboards...")
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

    @tasks.loop(minutes=5)
    async def notify_upcoming_contests(self) -> None:
        await self._evaluate_notifications()

    async def cog_load(self) -> None:
        await super().cog_load()
        await self._refresh_campus_leaderboards()

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
                display_name = " ".join(part for part in (user.firstName, user.lastName) if part) or user.handle
                rank_badge = {1: "🥇", 2: "🥈", 3: "🥉"}.get(rank, "🏅")
                embed.add_field(
                    name=f"{rank_badge} #{rank} · {display_name}",
                    value="\n".join(
                        [
                            f"Handle: [`{user.handle}`](https://codeforces.com/profile/{user.handle})",
                            f"Rating: `{user.rating}` · Max: `{user.maxRating}`",
                            f"CF Rank: `{user.rank}`",
                        ]
                    ),
                    inline=False,
                )
            embed.set_thumbnail(url=CODEFORCES_LOGO_ATTACHMENT_URL)
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
        await interaction.response.defer()

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
            paginator = EmbedButtonPaginator(
                user=interaction.user,
                pages=pages,
                attachments=[discord.File(CODEFORCES_LOGO_PATH, filename=CODEFORCES_LOGO_FILENAME)] * len(pages),
            )
            await paginator.start_paginator(interaction)
            return

        categories: list[CategoryEntry[discord.Embed]] = []
        for campus in leaderboard:
            users = leaderboard[campus]
            pages = self._build_user_pages(campus, users)
            categories.append(
                CategoryEntry(
                    category_title=campus,
                    pages=pages,
                    attachments=[discord.File(CODEFORCES_LOGO_PATH, filename=CODEFORCES_LOGO_FILENAME)] * len(pages),
                )
            )

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

            embed.set_thumbnail(url=CODEFORCES_LOGO_ATTACHMENT_URL)
            embed.set_footer(text=f"Page {n} of {len(upcoming)}", icon_url=self.bot.user.display_avatar)
            embed.timestamp = discord.utils.utcnow()
            entries.append(embed)

        attachments = [discord.File(CODEFORCES_LOGO_PATH, filename=CODEFORCES_LOGO_FILENAME) for _ in entries]
        paginator = EmbedButtonPaginator(user=interaction.user, pages=entries, attachments=attachments)
        await paginator.start_paginator(interaction)

    @app_commands.command(
        name="dry_run",
        description="Preview CodeForces notifications due now and expected in the selected horizon.",
    )
    @app_commands.checks.has_any_role(Roles.ADMIN, Roles.MODERATOR)
    async def dry_run(
        self, interaction: discord.Interaction[HackspaceBot], horizon_hours: app_commands.Range[int, 1, 168] = 24
    ) -> None:
        await interaction.response.defer(ephemeral=True)

        visible = await self.bot.features.is_enabled(FeatureKey.CODEFORCES_DRY_RUN_VISIBLE)
        if not visible:
            await interaction.edit_original_response(content="Dry run visibility is currently disabled.")
            return

        async with self._lock:
            contests = self._upcoming_contests.copy()

        milestones = await self._notification_milestones()

        now = int(datetime.datetime.now(datetime.timezone.utc).timestamp())
        horizon_seconds = int(horizon_hours) * 3600

        pages: list[discord.Embed] = []
        now_dt = datetime.datetime.fromtimestamp(now, tz=datetime.timezone.utc)
        now_full = discord.utils.format_dt(now_dt, style="F")
        horizon_until = discord.utils.format_dt(now_dt + datetime.timedelta(seconds=horizon_seconds), style="F")

        for contest in contests:
            contest_id = int(contest.id)
            start_time = contest.startTimeSeconds
            if start_time is None:
                continue

            start_dt = datetime.datetime.fromtimestamp(int(start_time), tz=datetime.timezone.utc)
            start_relative = discord.utils.format_dt(start_dt, style="R")
            start_full = discord.utils.format_dt(start_dt, style="F")

            state = await self.bot.db.contest_notifications.get_state(contest_id)
            sent: set[int] = set(state.milestones_sent) if state else set()
            missed: set[int] = set(state.milestones_missed) if state else set()
            time_until_start = int(start_time) - now

            now_actions: list[str] = []
            future_actions: list[str] = []

            if state is None or state.announced_at is None:
                now_actions.append("Announce contest")

            due_unsent = [m for m in milestones if time_until_start <= m and m not in sent and m not in missed]
            if due_unsent:
                latest_due = min(due_unsent)
                for older in [m for m in due_unsent if m != latest_due]:
                    now_actions.append(f"Mark {humanfriendly.format_timespan(older)} milestone as missed")
                now_actions.append(f"Send {humanfriendly.format_timespan(latest_due)} reminder")

            for milestone in milestones:
                if milestone in sent or milestone in missed:
                    continue
                trigger_time = int(start_time) - milestone
                if now < trigger_time <= now + horizon_seconds:
                    trigger_dt = datetime.datetime.fromtimestamp(trigger_time, tz=datetime.timezone.utc)
                    trigger_relative = discord.utils.format_dt(trigger_dt, style="R")
                    trigger_full = discord.utils.format_dt(trigger_dt, style="F")
                    future_actions.append(
                        (
                            f"{humanfriendly.format_timespan(milestone)} reminder: "
                            f"{trigger_relative} ({trigger_full})"
                        )
                    )

            if not now_actions and not future_actions:
                continue

            contest_url = contest.websiteUrl or f"https://codeforces.com/contest/{contest.id}"
            embed = discord.Embed(
                title=f"Dry Run · Contest #{contest.id}",
                url=contest_url,
                description=f"**{contest.name}**\nStarts: {start_relative} ({start_full})",
                color=discord.Color.blurple(),
            )
            embed.set_author(
                name="CodeForces",
                url="https://codeforces.com/",
                icon_url=CODEFORCES_LOGO_ATTACHMENT_URL,
            )
            embed.set_thumbnail(url=CODEFORCES_LOGO_ATTACHMENT_URL)
            embed.add_field(name="Type", value=f"`{contest.type}`", inline=True)
            embed.add_field(name="Phase", value=f"`{contest.phase}`", inline=True)
            embed.add_field(name="Duration", value=humanfriendly.format_timespan(contest.durationSeconds), inline=True)

            embed.add_field(
                name="NOW",
                value="\n".join(f"• {action}" for action in now_actions) if now_actions else "Nothing due right now.",
                inline=False,
            )
            embed.add_field(
                name=f"FUTURE (next {horizon_hours}h)",
                value=(
                    "\n".join(f"• {action}" for action in future_actions)
                    if future_actions
                    else "No upcoming reminders."
                ),
                inline=False,
            )
            embed.add_field(name="Window", value=f"Now: {now_full}\nUntil: {horizon_until}", inline=False)
            embed.timestamp = discord.utils.utcnow()
            pages.append(embed)

        if not pages:
            await interaction.edit_original_response(
                content="No notifications are due now or forecast in the selected horizon."
            )
            return

        total_pages = len(pages)
        for index, embed in enumerate(pages, start=1):
            embed.set_footer(text=f"Contest {index}/{total_pages} · Dry Run", icon_url=self.bot.user.display_avatar)

        attachments = [discord.File(CODEFORCES_LOGO_PATH, filename=CODEFORCES_LOGO_FILENAME) for _ in pages]
        paginator = EmbedButtonPaginator(user=interaction.user, pages=pages, attachments=attachments)
        await paginator.start_paginator(interaction)


async def setup(bot: HackspaceBot) -> None:
    await bot.add_cog(CodeForcesCog(bot))
