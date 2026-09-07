"""retain devices device_info during storage migration

Revision ID: 676e54a5dbaf
Revises: fc532120ca03
Create Date: 2026-07-07 05:23:45.727614+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '676e54a5dbaf'
down_revision: Union[str, Sequence[str], None] = 'fc532120ca03'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Keep the legacy column until storage backfill/cutover is completed,
    # but allow new storage-backed rows to omit the duplicated DB payload.
    op.alter_column(
        "devices",
        "device_info",
        existing_type=sa.Text(),
        nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "devices",
        "device_info",
        existing_type=sa.Text(),
        nullable=False,
    )
