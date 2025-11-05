import datetime
import enum
import random
import typing as t

import discord
import humanfriendly

if t.TYPE_CHECKING:
    from src.core.bot import HackspaceBot


__all__: tuple[str, ...] = (
    "Channels",
    "DEVELOPER_IDS",
    "PRESENCE_MAP",
)


DEVELOPER_IDS: tuple[int, ...] = (656838010532265994,)


class Channels(enum.IntEnum):
    LOGS = 1434971795739639970


class ButtonEmoji(enum.StrEnum):
    PREVIOUS = "<:ArrowLeft:989134685068202024>"
    NEXT = "<:rightArrow:989136803284004874>"
    STOP = "<:dustbin:989150297333043220>"
    LAST = "<:DoubleArrowRight:989134892384256011>"
    FIRST = "<:DoubleArrowLeft:989134953142956152>"


def format_uptime(bot: "HackspaceBot") -> str:
    return humanfriendly.format_timespan(bot.uptime.total_seconds(), max_units=2)  # type: ignore


def format_time() -> str:
    now = datetime.datetime.now(datetime.timezone.utc)
    return now.strftime("%H:%M UTC")


PRESENCE_MAP: dict[discord.ActivityType, list[t.Callable[["HackspaceBot"], str]]] = {
    discord.ActivityType.playing: [
        lambda bot: f"with {len(bot.users)} innovators in {len(bot.guilds)} hackspace",
        lambda bot: f"the debug game (uptime: {format_uptime(bot)})",
        lambda bot: f"with code at {format_time()}",
        lambda bot: f"{random.choice(['Python', 'Rust', 'C++', 'Go', 'JS'])} wizardry live",
        lambda bot: f"{len(bot.users)//10} simultaneous caffeine dependencies",
    ],
    discord.ActivityType.watching: [
        lambda bot: f"{len(bot.users)} bringing ideas to life",
        lambda bot: f"{len(bot.users)} hackers building things",
        lambda bot: f"for commits since {format_time()}",
        lambda bot: f"the LEDs blink in {random.choice(['red', 'green', 'blue', 'white'])}",
        lambda bot: "progress bars crawl across screens",
    ],
    discord.ActivityType.listening: [
        lambda bot: f"{format_uptime(bot)} worth of keypresses",
        lambda bot: f"{len(bot.users)} keyboards clacking in unison",
        lambda bot: f"the hum of {len(bot.users)} machines",
        lambda bot: "debug logs whispering secrets",
        lambda bot: f"{random.randint(10,99)}% CPU jazz",
    ],
    discord.ActivityType.competing: [
        lambda bot: f"who compiles first at {format_time()}",
        lambda bot: f"for uptime records ({format_uptime(bot)})",
        lambda bot: "in Hack Club's invisible leaderboard",
        lambda bot: "against entropy and memory leaks",
        lambda bot: f"for {random.randint(100,999)} consecutive successful builds",
    ],
    discord.ActivityType.streaming: [
        lambda bot: f"live coding sessions with {len(bot.users)} hackers",
        lambda bot: "hackathons around the world",
        lambda bot: "workshops on building cool stuff",
        lambda bot: "the future of technology unfold",
        lambda bot: "open source projects in action",
    ],
}
