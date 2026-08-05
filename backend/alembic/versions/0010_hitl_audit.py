"""HITL field-edit audit trail table."""

from alembic import op
import sqlalchemy as sa

revision = "0010_hitl_audit"
down_revision = "0009_summary_analytics"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS audit")
    op.create_table(
        "hitl_audit_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "session_id",
            sa.String(36),
            sa.ForeignKey("prescription.review_sessions.id"),
            nullable=False,
        ),
        sa.Column("medicine_id", sa.String(36), nullable=True),
        sa.Column(
            "pharmacist_user_id",
            sa.String(36),
            sa.ForeignKey("auth.users.id"),
            nullable=False,
        ),
        sa.Column("event_type", sa.String(80), nullable=False),
        sa.Column("field_name", sa.String(40), nullable=True),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        schema="audit",
    )
    op.create_index(
        "ix_audit_hitl_session",
        "hitl_audit_events",
        ["session_id"],
        schema="audit",
    )
    op.create_index(
        "ix_audit_hitl_medicine",
        "hitl_audit_events",
        ["medicine_id"],
        schema="audit",
    )
    op.create_index(
        "ix_audit_hitl_pharmacist",
        "hitl_audit_events",
        ["pharmacist_user_id"],
        schema="audit",
    )


def downgrade() -> None:
    op.drop_index("ix_audit_hitl_pharmacist", table_name="hitl_audit_events", schema="audit")
    op.drop_index("ix_audit_hitl_medicine", table_name="hitl_audit_events", schema="audit")
    op.drop_index("ix_audit_hitl_session", table_name="hitl_audit_events", schema="audit")
    op.drop_table("hitl_audit_events", schema="audit")
