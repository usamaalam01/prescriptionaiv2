"""Phase 1b: config.phase_markers + schemas."""

from alembic import op
import sqlalchemy as sa

revision = "0001_phase1b"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS config")
    op.create_table(
        "phase_markers",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("phase", sa.String(length=32), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("phase"),
        schema="config",
    )
    op.execute("INSERT INTO config.phase_markers (phase) VALUES ('1b')")


def downgrade() -> None:
    op.drop_table("phase_markers", schema="config")
