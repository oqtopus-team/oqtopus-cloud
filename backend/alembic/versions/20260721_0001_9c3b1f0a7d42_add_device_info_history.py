"""add device info history

Revision ID: 9c3b1f0a7d42
Revises: 676e54a5dbaf
Create Date: 2026-07-21 00:01:00.000000+00:00

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

from oqtopus_cloud.common.model_util import DateTimeTz

# revision identifiers, used by Alembic.
revision: str = "9c3b1f0a7d42"
down_revision: Union[str, Sequence[str], None] = "676e54a5dbaf"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "device_info_history",
        sa.Column(
            "id",
            sa.Integer().with_variant(mysql.BIGINT(unsigned=True), "mysql"),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column("device_id", sa.String(length=64), nullable=False),
        sa.Column(
            "calibrated_at",
            sa.DateTime().with_variant(mysql.TIMESTAMP(fsp=6), "mysql"),
            nullable=False,
        ),
        sa.Column("n_qubits", sa.Integer(), nullable=False),
        sa.Column("n_couplings", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            DateTimeTz(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=True,
        ),
        sa.Column(
            "updated_at",
            DateTimeTz(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "device_id",
            "calibrated_at",
            name="uq_device_info_history_device_calibrated_at",
        ),
    )
    op.create_index(
        "ix_device_info_history_device_calibrated_at",
        "device_info_history",
        ["device_id", "calibrated_at"],
    )

    bind = op.get_bind()
    if bind.dialect.name == "mysql":
        op.execute(
            "ALTER TABLE device_info_history "
            "MODIFY updated_at TIMESTAMP NULL "
            "DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"
        )


def downgrade() -> None:
    op.drop_index(
        "ix_device_info_history_device_calibrated_at",
        table_name="device_info_history",
    )
    op.drop_table("device_info_history")
