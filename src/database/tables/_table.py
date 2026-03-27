import abc
import typing as t

if t.TYPE_CHECKING:
    from src.database.client import Database


__all__: tuple[str, ...] = ("Table",)


class Table(abc.ABC):
    """Base class for all database tables."""

    def __init__(self, db: "Database") -> None:
        self.db = db

    @abc.abstractmethod
    async def setup(self) -> None:
        """Hook for post-migration setup."""

    @abc.abstractmethod
    async def seed_defaults(self) -> None:
        """Hook for default row seeding."""

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """The name of the table."""
