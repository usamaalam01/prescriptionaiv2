"""Add pharmacist_verified_indication on prescription medicines."""

from alembic import op
import sqlalchemy as sa

revision = "0008_verified_indication"
down_revision = "0007_phase5_therapeutic"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "prescription_medicines",
        sa.Column("pharmacist_verified_indication", sa.String(255), nullable=True),
        schema="prescription",
    )


def downgrade() -> None:
    op.drop_column("prescription_medicines", "pharmacist_verified_indication", schema="prescription")
