"""Phase 2: consent + admin registration tables."""

from alembic import op
import sqlalchemy as sa

revision = "0003_phase2"
down_revision = "0002_phase1c"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS consent")
    op.execute("CREATE SCHEMA IF NOT EXISTS admin")

    op.add_column(
        "users",
        sa.Column("encrypted_pharmacist_registration_id", sa.Text()),
        schema="auth",
    )

    op.create_table(
        "participant_information_sheets",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("version", sa.String(20), nullable=False, unique=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("study_title", sa.String(500), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("effective_date", sa.String(40), nullable=False),
        sa.Column("is_current", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        schema="consent",
    )

    op.create_table(
        "consent_form_versions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("version", sa.String(20), nullable=False, unique=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("study_title", sa.String(500), nullable=False),
        sa.Column("effective_date", sa.String(40), nullable=False),
        sa.Column("is_current", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        schema="consent",
    )

    op.create_table(
        "consent_statement_versions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("form_id", sa.String(36), sa.ForeignKey("consent.consent_form_versions.id"), nullable=False),
        sa.Column("statement_number", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.UniqueConstraint("form_id", "statement_number"),
        schema="consent",
    )

    op.create_table(
        "user_pis_acknowledgements",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("auth.users.id"), nullable=False),
        sa.Column(
            "pis_id",
            sa.String(36),
            sa.ForeignKey("consent.participant_information_sheets.id"),
            nullable=False,
        ),
        sa.Column("pis_version", sa.String(20), nullable=False),
        sa.Column("scroll_acknowledged", sa.Boolean(), nullable=False),
        sa.Column("label_accepted", sa.Boolean(), nullable=False),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        schema="consent",
    )
    op.create_index(
        "ix_consent_user_pis_user_id",
        "user_pis_acknowledgements",
        ["user_id"],
        schema="consent",
    )

    op.create_table(
        "user_consents",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("auth.users.id"), nullable=False),
        sa.Column("form_id", sa.String(36), sa.ForeignKey("consent.consent_form_versions.id"), nullable=False),
        sa.Column("study_code", sa.String(100), nullable=False),
        sa.Column("pis_version", sa.String(20), nullable=False),
        sa.Column("consent_form_version", sa.String(20), nullable=False),
        sa.Column("consent_status", sa.String(30), nullable=False),
        sa.Column("age_over_18_confirmed", sa.Boolean(), nullable=False),
        sa.Column("all_statements_accepted", sa.Boolean(), nullable=False),
        sa.Column("electronic_affirmation_accepted", sa.Boolean(), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        schema="consent",
    )
    op.create_index("ix_consent_user_consents_user_id", "user_consents", ["user_id"], schema="consent")

    op.create_table(
        "user_consent_responses",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_consent_id", sa.String(36), sa.ForeignKey("consent.user_consents.id"), nullable=False),
        sa.Column(
            "statement_id",
            sa.String(36),
            sa.ForeignKey("consent.consent_statement_versions.id"),
            nullable=False,
        ),
        sa.Column("statement_number", sa.Integer(), nullable=False),
        sa.Column("accepted", sa.Boolean(), nullable=False),
        sa.UniqueConstraint("user_consent_id", "statement_id"),
        schema="consent",
    )

    op.create_table(
        "registration_requests",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("auth.users.id"), nullable=False, unique=True),
        sa.Column("requested_role", sa.String(32), nullable=False),
        sa.Column("age_over_18_confirmed", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        schema="admin",
    )

    op.create_table(
        "registration_decisions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "registration_id",
            sa.String(36),
            sa.ForeignKey("admin.registration_requests.id"),
            nullable=False,
        ),
        sa.Column("administrator_id", sa.String(36), sa.ForeignKey("auth.users.id"), nullable=False),
        sa.Column("decision", sa.String(20), nullable=False),
        sa.Column("confirmed_role", sa.String(32), nullable=False),
        sa.Column("reason", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        schema="admin",
    )

    op.execute("INSERT INTO config.phase_markers (phase) VALUES ('2') ON CONFLICT (phase) DO NOTHING")


def downgrade() -> None:
    op.drop_table("registration_decisions", schema="admin")
    op.drop_table("registration_requests", schema="admin")
    op.drop_table("user_consent_responses", schema="consent")
    op.drop_table("user_consents", schema="consent")
    op.drop_table("user_pis_acknowledgements", schema="consent")
    op.drop_table("consent_statement_versions", schema="consent")
    op.drop_table("consent_form_versions", schema="consent")
    op.drop_table("participant_information_sheets", schema="consent")
    op.drop_column("users", "encrypted_pharmacist_registration_id", schema="auth")
