"""Add booked_date column to appointment_requests table

Revision ID: 011
Revises: 010
Create Date: 2026-02-25 12:34:00.000000

Add booked_date column to store the actual date when appointment was booked,
enabling the frontend AppointmentCalendar to display booked appointment dates.
"""

from typing import Sequence, Union

import sqlalchemy as sa  # noqa: F401

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "011"
down_revision: Union[str, None] = "010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add booked_date column to appointment_requests table."""
    op.execute("""
        ALTER TABLE appointment_requests
        ADD COLUMN IF NOT EXISTS booked_date TEXT DEFAULT NULL
    """)


def downgrade() -> None:
    """Remove booked_date column from appointment_requests table."""
    op.execute("""
        ALTER TABLE appointment_requests
        DROP COLUMN IF EXISTS booked_date
    """)
