"""retain devices device_info during storage migration

Revision ID: 676e54a5dbaf
Revises: fc532120ca03
Create Date: 2026-07-07 05:23:45.727614+00:00

"""
from typing import Sequence, Union

# revision identifiers, used by Alembic.
revision: str = '676e54a5dbaf'
down_revision: Union[str, Sequence[str], None] = 'fc532120ca03'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Keep the legacy column until storage backfill/cutover is completed.
    return None


def downgrade() -> None:
    return None
