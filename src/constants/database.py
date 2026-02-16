"""Database and connection pool constants."""

from typing import Final


class Database:
    """Database configuration defaults.

    NOTE: These are compile-time defaults only. Runtime configuration
    should be obtained via VFSSettings (src/core/settings.py) which
    provides environment variable parsing, validation, and type coercion.
    """

    DEFAULT_URL: Final[str] = "postgresql://localhost:5432/vfs_bot"
    TEST_URL: Final[str] = "postgresql://localhost:5432/vfs_bot_test"
    POOL_SIZE: Final[int] = 10
    CONNECTION_TIMEOUT: Final[float] = 30.0
    QUERY_TIMEOUT: Final[float] = 30.0
    DEFAULT_CACHE_TTL: Final[int] = 3600


class Pools:
    """Connection pool sizes."""

    DATABASE: Final[int] = Database.POOL_SIZE
    HTTP_LIMIT: Final[int] = 50
    HTTP_LIMIT_PER_HOST: Final[int] = 20
    DNS_CACHE_TTL: Final[int] = 120
    KEEPALIVE_TIMEOUT: Final[int] = 30
