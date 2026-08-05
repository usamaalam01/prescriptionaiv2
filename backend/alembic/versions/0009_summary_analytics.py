"""Cache Summary Analytics on review sessions."""

from alembic import op
import sqlalchemy as sa

revision = "0009_summary_analytics"
down_revision = "0008_verified_indication"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "review_sessions",
        sa.Column("analytics_json", sa.Text(), nullable=True),
        schema="prescription",
    )
    op.add_column(
        "review_sessions",
        sa.Column("analytics_fingerprint", sa.String(64), nullable=True),
        schema="prescription",
    )
    op.add_column(
        "review_sessions",
        sa.Column("analytics_updated_at", sa.DateTime(timezone=True), nullable=True),
        schema="prescription",
    )


def downgrade() -> None:
    op.drop_column("review_sessions", "analytics_updated_at", schema="prescription")
    op.drop_column("review_sessions", "analytics_fingerprint", schema="prescription")
    op.drop_column("review_sessions", "analytics_json", schema="prescription")
