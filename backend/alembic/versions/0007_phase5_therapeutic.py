"""Milestone 5: therapeutic alternatives evaluation + decisions + audit."""

from alembic import op
import sqlalchemy as sa

revision = "0007_phase5_therapeutic"
down_revision = "0006_phase4_alternatives"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS clinical")
    op.execute("CREATE SCHEMA IF NOT EXISTS audit")

    op.create_table(
        "therapeutic_evaluations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("prescription_id", sa.String(36), sa.ForeignKey("prescription.review_sessions.id"), nullable=False),
        sa.Column("pharmacist_user_id", sa.String(36), sa.ForeignKey("auth.users.id"), nullable=False),
        sa.Column("result_json", sa.Text(), nullable=False),
        sa.Column("dataset_version", sa.String(80), nullable=False),
        sa.Column("rules_engine_version", sa.String(80), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        schema="clinical",
    )
    op.create_index(
        "ix_clinical_ta_eval_prescription",
        "therapeutic_evaluations",
        ["prescription_id"],
        schema="clinical",
    )

    op.create_table(
        "therapeutic_decisions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "evaluation_id",
            sa.String(36),
            sa.ForeignKey("clinical.therapeutic_evaluations.id"),
            nullable=False,
        ),
        sa.Column("prescription_item_id", sa.String(36), nullable=False),
        sa.Column("candidate_drug_id", sa.String(80), nullable=False),
        sa.Column("candidate_name", sa.String(255), nullable=False),
        sa.Column("action", sa.String(40), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("note", sa.Text()),
        sa.Column("pharmacist_user_id", sa.String(36), sa.ForeignKey("auth.users.id"), nullable=False),
        sa.Column("payload_json", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        schema="clinical",
    )

    op.create_table(
        "therapeutic_audit_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("evaluation_id", sa.String(36), nullable=False),
        sa.Column("event_type", sa.String(80), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        schema="audit",
    )


def downgrade() -> None:
    op.drop_table("therapeutic_audit_events", schema="audit")
    op.drop_table("therapeutic_decisions", schema="clinical")
    op.drop_table("therapeutic_evaluations", schema="clinical")
