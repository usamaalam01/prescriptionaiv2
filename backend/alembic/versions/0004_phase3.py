"""Milestone 3: prescription sessions + OCR job tables."""

from alembic import op
import sqlalchemy as sa

revision = "0004_phase3"
down_revision = "0003_phase2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS prescription")
    op.execute("CREATE SCHEMA IF NOT EXISTS ocr")
    op.execute("CREATE SCHEMA IF NOT EXISTS security")

    op.create_table(
        "review_sessions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("pharmacist_user_id", sa.String(36), sa.ForeignKey("auth.users.id"), nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("original_filename", sa.String(255), nullable=False),
        sa.Column("content_type", sa.String(100), nullable=False),
        sa.Column("file_size_bytes", sa.Integer(), nullable=False),
        sa.Column("storage_object_key", sa.String(500)),
        sa.Column("selected_ocr_engine", sa.String(40)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("cancelled_at", sa.DateTime(timezone=True)),
        sa.Column("temporary_deleted_at", sa.DateTime(timezone=True)),
        schema="prescription",
    )
    op.create_index(
        "ix_prescription_review_sessions_pharmacist_user_id",
        "review_sessions",
        ["pharmacist_user_id"],
        schema="prescription",
    )

    op.create_table(
        "temporary_file_records",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "session_id",
            sa.String(36),
            sa.ForeignKey("prescription.review_sessions.id"),
            nullable=False,
        ),
        sa.Column("object_key", sa.String(500), nullable=False),
        sa.Column("encrypted", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        schema="security",
    )

    op.create_table(
        "ocr_jobs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "session_id",
            sa.String(36),
            sa.ForeignKey("prescription.review_sessions.id"),
            nullable=False,
        ),
        sa.Column("engine", sa.String(40), nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("raw_text", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("character_count", sa.Integer(), nullable=False),
        sa.Column("processing_ms", sa.Integer(), nullable=False),
        sa.Column("is_mock", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("warnings_json", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        schema="ocr",
    )
    op.create_index("ix_ocr_jobs_session_id", "ocr_jobs", ["session_id"], schema="ocr")
    op.execute("INSERT INTO config.phase_markers (phase) VALUES ('3') ON CONFLICT (phase) DO NOTHING")


def downgrade() -> None:
    op.drop_table("ocr_jobs", schema="ocr")
    op.drop_table("temporary_file_records", schema="security")
    op.drop_table("review_sessions", schema="prescription")
