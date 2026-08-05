"""Milestone 4: therapeutic alternatives + pharmacist feedback tables."""

from alembic import op
import sqlalchemy as sa

revision = "0006_phase4_alternatives"
down_revision = "0005_phase3_pipeline"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS clinical")

    op.create_table(
        "alternative_suggestions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "session_id",
            sa.String(36),
            sa.ForeignKey("prescription.review_sessions.id"),
            nullable=False,
        ),
        sa.Column(
            "medicine_id",
            sa.String(36),
            sa.ForeignKey("prescription.prescription_medicines.id"),
            nullable=False,
        ),
        sa.Column("rank", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("source_medicine", sa.String(255), nullable=False),
        sa.Column("alternative_medicine_name", sa.String(255), nullable=False),
        sa.Column("strength", sa.String(100)),
        sa.Column("form", sa.String(100)),
        sa.Column("route", sa.String(100)),
        sa.Column("relationship", sa.String(60), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("contraindications_note", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0"),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("citations_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("knowledge_source", sa.String(80), nullable=False),
        sa.Column("is_mock_knowledge", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        schema="clinical",
    )
    op.create_index(
        "ix_clinical_alt_suggestions_session",
        "alternative_suggestions",
        ["session_id"],
        schema="clinical",
    )
    op.create_index(
        "ix_clinical_alt_suggestions_medicine",
        "alternative_suggestions",
        ["medicine_id"],
        schema="clinical",
    )

    op.create_table(
        "alternative_feedback",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "suggestion_id",
            sa.String(36),
            sa.ForeignKey("clinical.alternative_suggestions.id"),
            nullable=False,
        ),
        sa.Column(
            "session_id",
            sa.String(36),
            sa.ForeignKey("prescription.review_sessions.id"),
            nullable=False,
        ),
        sa.Column(
            "pharmacist_user_id",
            sa.String(36),
            sa.ForeignKey("auth.users.id"),
            nullable=False,
        ),
        sa.Column("decision", sa.String(40), nullable=False),
        sa.Column("note", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        schema="clinical",
    )
    op.create_index(
        "ix_clinical_alt_feedback_suggestion",
        "alternative_feedback",
        ["suggestion_id"],
        schema="clinical",
    )


def downgrade() -> None:
    op.drop_table("alternative_feedback", schema="clinical")
    op.drop_table("alternative_suggestions", schema="clinical")
