"""Research evaluation schema and DQ1–DQ4 evidence tables."""

from alembic import op
import sqlalchemy as sa

revision = "0012_research_evaluation"
down_revision = "0011_sprint1_candidate_decisions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS research")

    op.create_table(
        "evaluation_cases",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("case_code", sa.String(64), nullable=False),
        sa.Column("synthetic_prescription_ref", sa.String(255), nullable=True),
        sa.Column("dataset_version", sa.String(80), nullable=False, server_default="v1"),
        sa.Column("ground_truth_status", sa.String(40), nullable=False, server_default="pending"),
        sa.Column("inclusion_status", sa.String(40), nullable=False, server_default="included"),
        sa.Column("exclusion_reason", sa.Text(), nullable=True),
        sa.Column("approved_reviewer_pseudonym", sa.String(80), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.UniqueConstraint("case_code"),
        schema="research",
    )
    op.create_index(
        "ix_research_evaluation_cases_case_code",
        "evaluation_cases",
        ["case_code"],
        schema="research",
    )

    op.create_table(
        "ground_truth_records",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("evaluation_case_id", sa.String(36), sa.ForeignKey("research.evaluation_cases.id"), nullable=False),
        sa.Column("instruction_text", sa.Text(), nullable=True),
        sa.Column("medicine_name", sa.String(255), nullable=True),
        sa.Column("strength", sa.String(120), nullable=True),
        sa.Column("dosage_form", sa.String(120), nullable=True),
        sa.Column("route", sa.String(120), nullable=True),
        sa.Column("dose", sa.String(120), nullable=True),
        sa.Column("frequency", sa.String(120), nullable=True),
        sa.Column("duration", sa.String(120), nullable=True),
        sa.Column("source", sa.String(80), server_default="pharmacist_confirmed"),
        sa.Column("version", sa.String(40), server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        schema="research",
    )
    op.create_index(
        "ix_research_gt_case",
        "ground_truth_records",
        ["evaluation_case_id"],
        schema="research",
    )

    op.create_table(
        "evaluation_snapshots",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("snapshot_code", sa.String(64), nullable=False),
        sa.Column("included_case_ids_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("excluded_cases_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("ground_truth_version", sa.String(80), nullable=True),
        sa.Column("catalogue_version", sa.String(80), nullable=True),
        sa.Column("ocr_config_json", sa.Text(), nullable=True),
        sa.Column("matching_algorithm_version", sa.String(80), nullable=True),
        sa.Column("retrieval_config_json", sa.Text(), nullable=True),
        sa.Column("explanation_config_json", sa.Text(), nullable=True),
        sa.Column("metric_implementation_version", sa.String(40), server_default="1.0.0"),
        sa.Column("git_commit_hash", sa.String(64), nullable=True),
        sa.Column("prescription_count", sa.Integer(), server_default="0"),
        sa.Column("pharmacist_count", sa.Integer(), server_default="0"),
        sa.Column("results_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.UniqueConstraint("snapshot_code"),
        schema="research",
    )
    op.create_index(
        "ix_research_snapshot_code",
        "evaluation_snapshots",
        ["snapshot_code"],
        schema="research",
    )

    op.create_table(
        "ocr_evaluation_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("snapshot_id", sa.String(36), nullable=True),
        sa.Column("evaluation_case_id", sa.String(36), sa.ForeignKey("research.evaluation_cases.id"), nullable=False),
        sa.Column("engine_id", sa.String(64), nullable=False),
        sa.Column("engine_version", sa.String(80), nullable=True),
        sa.Column("raw_text", sa.Text(), nullable=True),
        sa.Column("structured_fields_json", sa.Text(), nullable=True),
        sa.Column("field_confidence_json", sa.Text(), nullable=True),
        sa.Column("processing_time_ms", sa.Float(), nullable=True),
        sa.Column("preprocessing_configuration_json", sa.Text(), nullable=True),
        sa.Column("error_status", sa.String(80), nullable=True),
        sa.Column("cer", sa.Float(), nullable=True),
        sa.Column("wer", sa.Float(), nullable=True),
        sa.Column("metrics_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        schema="research",
    )
    op.create_index("ix_research_ocr_case", "ocr_evaluation_runs", ["evaluation_case_id"], schema="research")
    op.create_index("ix_research_ocr_engine", "ocr_evaluation_runs", ["engine_id"], schema="research")

    op.create_table(
        "recommendation_gold_standards",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("evaluation_case_id", sa.String(36), sa.ForeignKey("research.evaluation_cases.id"), nullable=False),
        sa.Column("reference_medicine", sa.String(255), nullable=False),
        sa.Column("candidate_medicine", sa.String(255), nullable=False),
        sa.Column("candidate_type", sa.String(64), nullable=False),
        sa.Column("candidate_rank", sa.Integer(), nullable=True),
        sa.Column("same_active_ingredient", sa.Boolean(), nullable=True),
        sa.Column("same_active_moiety", sa.Boolean(), nullable=True),
        sa.Column("pharmacist_valid_candidate", sa.Boolean(), nullable=False),
        sa.Column("pharmacist_reason", sa.Text(), nullable=True),
        sa.Column("evidence_source", sa.String(120), nullable=True),
        sa.Column("reviewer_pseudonym", sa.String(80), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        schema="research",
    )
    op.create_index(
        "ix_research_gold_case",
        "recommendation_gold_standards",
        ["evaluation_case_id"],
        schema="research",
    )

    op.create_table(
        "recommendation_evaluation_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("snapshot_id", sa.String(36), nullable=True),
        sa.Column("condition", sa.String(80), nullable=False),
        sa.Column("metrics_json", sa.Text(), nullable=False),
        sa.Column("availability", sa.String(40), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        schema="research",
    )

    op.create_table(
        "rag_evaluation_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("snapshot_id", sa.String(36), nullable=True),
        sa.Column("evaluation_case_id", sa.String(36), nullable=True),
        sa.Column("retrieval_method", sa.String(40), nullable=False),
        sa.Column("query", sa.Text(), nullable=True),
        sa.Column("retrieved_json", sa.Text(), nullable=True),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.Column("metrics_json", sa.Text(), nullable=True),
        sa.Column("availability", sa.String(40), nullable=False),
        sa.Column("processing_time_ms", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        schema="research",
    )

    op.create_table(
        "explanation_evaluation_assignments",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("participant_pseudonym", sa.String(80), nullable=False),
        sa.Column("evaluation_case_id", sa.String(36), nullable=True),
        sa.Column("condition", sa.String(8), nullable=False),
        sa.Column("order_index", sa.Integer(), server_default="0"),
        sa.Column("payload_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        schema="research",
    )
    op.create_index(
        "ix_research_xai_participant",
        "explanation_evaluation_assignments",
        ["participant_pseudonym"],
        schema="research",
    )

    op.create_table(
        "pharmacist_survey_responses",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("participant_pseudonym", sa.String(80), nullable=False),
        sa.Column("condition", sa.String(8), nullable=False),
        sa.Column("evaluation_case_id", sa.String(36), nullable=True),
        sa.Column("likert_json", sa.Text(), nullable=False),
        sa.Column("free_text", sa.Text(), nullable=True),
        sa.Column("questionnaire_version", sa.String(20), server_default="1.2"),
        sa.Column("consent_confirmed", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        schema="research",
    )
    op.create_index(
        "ix_research_survey_participant",
        "pharmacist_survey_responses",
        ["participant_pseudonym"],
        schema="research",
    )


def downgrade() -> None:
    for table in (
        "pharmacist_survey_responses",
        "explanation_evaluation_assignments",
        "rag_evaluation_runs",
        "recommendation_evaluation_runs",
        "recommendation_gold_standards",
        "ocr_evaluation_runs",
        "evaluation_snapshots",
        "ground_truth_records",
        "evaluation_cases",
    ):
        op.drop_table(table, schema="research")
    op.execute("DROP SCHEMA IF EXISTS research CASCADE")
