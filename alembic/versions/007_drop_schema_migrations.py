"""Drop legacy schema_migrations table

Revision ID: 007
Revises: 006
Create Date: 2026-02-09

The schema_migrations table was a legacy artifact from the old in-code
migration system. All schema management is now handled exclusively by Alembic.
"""

from typing import Sequence, Union

import sqlalchemy as sa  # noqa: F401

from alembic import op

revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Drop legacy schema_migrations table."""
    op.execute("DROP TABLE IF EXISTS schema_migrations CASCADE")


def downgrade() -> None:
    """Downgrade not supported — dropping legacy schema_migrations is irreversible."""
    raise RuntimeError("Downgrade not supported")
