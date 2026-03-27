from ._table import Table
from .config import Config
from .contest_notifications import ContestNotifications
from .feature_flags import FeatureFlags
from .migrations import Migrations

TABLES: tuple[type[Table], ...] = (
    Config,
    FeatureFlags,
    ContestNotifications,
    Migrations,
)

__all__: tuple[str, ...] = (
    "Table",
    "Config",
    "FeatureFlags",
    "ContestNotifications",
    "Migrations",
    "TABLES",
)
