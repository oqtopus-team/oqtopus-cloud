"""add_jobs_indexes

Revision ID: 0e01e14a4bba
Revises: fc532120ca03
Create Date: 2026-07-24 06:23:47.955159+00:00

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '0e01e14a4bba'
down_revision: Union[str, Sequence[str], None] = 'fc532120ca03'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Monitoring dashboard's per-status queue backlog query
    # (WHERE status IN (...) GROUP BY device_id, status); status leads so the
    # filter can range-scan it, and the index alone covers all selected columns.
    op.create_index("ix_jobs_status_device_id", "jobs", ["status", "device_id"])
    # Monitoring dashboard's job wait-time query
    # (WHERE running_at >= ... GROUP BY device_id), which today full-scans
    # jobs on every scrape since running_at has no index.
    op.create_index(
        "ix_jobs_running_at_device_id_submitted_at",
        "jobs",
        ["running_at", "device_id", "submitted_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_jobs_running_at_device_id_submitted_at", table_name="jobs")
    op.drop_index("ix_jobs_status_device_id", table_name="jobs")
