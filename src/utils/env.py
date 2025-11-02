import logging
import os
import typing as t

import attrs
from dotenv import load_dotenv

__all__: tuple[str, ...] = ("EnvVar", "Environment", "ENV")


MISSING = object()
T = t.TypeVar("T")


logger = logging.getLogger(__name__)


load_dotenv()


@attrs.define(kw_only=True)
class EnvVar(t.Generic[T]):
    name: str
    value: str | t.Any = attrs.field(default=MISSING)
    cast: t.Callable[[str], T]
    required: bool = False

    def __attrs_post_init__(self) -> None:
        self.value = os.getenv(self.name, self.value)
        if self.value is MISSING and self.required:
            raise RuntimeError(f"Required environment variable '{self.name}' is not set.")
        try:
            self.value = self.cast(self.value)
            logger.info(f"`{self.name}` environment variable loaded from environment")
        except Exception as e:
            raise RuntimeError(f"Failed to cast environment variable '{self.name}' to {self.cast.__name__}: {e}") from e

    def __str__(self) -> str:
        if self.cast is str:
            return self.value
        return str(self.value)

    def __get__(self, instance: t.Any, owner: t.Any) -> T:
        return self.cast(self.value)


@attrs.define(kw_only=True)
class Environment:
    DISCORD_TOKEN: EnvVar[str] = attrs.field(
        default=EnvVar(name="DISCORD_TOKEN", required=True, cast=str),
    )


ENV = Environment()
