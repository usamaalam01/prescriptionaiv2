"""Sprint 1: enrich therapeutic decision audit fields (nullable; preserve rows)."""

from alembic import op
import sqlalchemy as sa

revision = "0011_sprint1_candidate_decisions"
down_revision = "0010_hitl_audit"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "therapeutic_decisions",
        sa.Column("candidate_type", sa.String(64), nullable=True),
        schema="clinical",
    )
    op.add_column(
        "therapeutic_decisions",
        sa.Column("override_reason", sa.Text(), nullable=True),
        schema="clinical",
    )
    op.add_column(
        "therapeutic_decisions",
        sa.Column("reviewer_pseudonym", sa.String(80), nullable=True),
        schema="clinical",
    )
    op.add_column(
        "therapeutic_decisions",
        sa.Column("algorithm_version", sa.String(80), nullable=True),
        schema="clinical",
    )
    op.add_column(
        "therapeutic_decisions",
        sa.Column("catalogue_version", sa.String(80), nullable=True),
        schema="clinical",
    )
    op.add_column(
        "therapeutic_decisions",
        sa.Column("evidence_ids_json", sa.Text(), nullable=True),
        schema="clinical",
    )
    op.create_index(
        "ix_clinical_ta_decision_candidate_type",
        "therapeutic_decisions",
        ["candidate_type"],
        schema="clinical",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_clinical_ta_decision_candidate_type",
        table_name="therapeutic_decisions",
        schema="clinical",
    )
    op.drop_column("therapeutic_decisions", "evidence_ids_json", schema="clinical")
    op.drop_column("therapeutic_decisions", "catalogue_version", schema="clinical")
    op.drop_column("therapeutic_decisions", "algorithm_version", schema="clinical")
    op.drop_column("therapeutic_decisions", "reviewer_pseudonym", schema="clinical")
    op.drop_column("therapeutic_decisions", "override_reason", schema="clinical")
    op.drop_column("therapeutic_decisions", "candidate_type", schema="clinical")
