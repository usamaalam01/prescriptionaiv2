"""Milestone 3b: pipeline JSON columns + prescription medicines for pharmacist verification."""

from alembic import op
import sqlalchemy as sa

revision = "0005_phase3_pipeline"
down_revision = "0004_phase3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("review_sessions", sa.Column("pipeline_json", sa.Text()), schema="prescription")
    op.add_column("ocr_jobs", sa.Column("pipeline_json", sa.Text()), schema="ocr")

    op.create_table(
        "prescription_medicines",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "session_id",
            sa.String(36),
            sa.ForeignKey("prescription.review_sessions.id"),
            nullable=False,
        ),
        sa.Column("item_number", sa.Integer(), nullable=False),
        sa.Column("ai_medicine_name", sa.String(255), nullable=False),
        sa.Column("ai_strength", sa.String(100)),
        sa.Column("ai_form", sa.String(100)),
        sa.Column("ai_dose", sa.String(100)),
        sa.Column("ai_route", sa.String(100)),
        sa.Column("ai_frequency", sa.String(100)),
        sa.Column("ai_duration", sa.String(100)),
        sa.Column("source_span", sa.Text()),
        sa.Column("parser_confidence", sa.Float(), nullable=False, server_default="0"),
        sa.Column("formulary_matched", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("formulary_id", sa.String(100)),
        sa.Column("formulary_warnings_json", sa.Text()),
        sa.Column("pharmacist_status", sa.String(40), nullable=False, server_default="extracted"),
        sa.Column("pharmacist_medicine_name", sa.String(255)),
        sa.Column("pharmacist_strength", sa.String(100)),
        sa.Column("pharmacist_form", sa.String(100)),
        sa.Column("pharmacist_dose", sa.String(100)),
        sa.Column("pharmacist_route", sa.String(100)),
        sa.Column("pharmacist_frequency", sa.String(100)),
        sa.Column("pharmacist_duration", sa.String(100)),
        sa.Column("pharmacist_reason", sa.Text()),
        sa.Column("verified_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        schema="prescription",
    )
    op.create_index(
        "ix_prescription_medicines_session_id",
        "prescription_medicines",
        ["session_id"],
        schema="prescription",
    )
    op.execute(
        "INSERT INTO config.phase_markers (phase) VALUES ('3-pipeline') ON CONFLICT (phase) DO NOTHING"
    )


def downgrade() -> None:
    op.drop_table("prescription_medicines", schema="prescription")
    op.drop_column("ocr_jobs", "pipeline_json", schema="ocr")
    op.drop_column("review_sessions", "pipeline_json", schema="prescription")
