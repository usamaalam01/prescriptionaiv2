"""Research evaluation ORM (schema: research) — DQ1–DQ4 evidence store."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.auth import uuid_pk


class EvaluationCase(Base):
    __tablename__ = "evaluation_cases"
    __table_args__ = {"schema": "research"}

    id: Mapped[str] = uuid_pk()
    case_code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    synthetic_prescription_ref: Mapped[str | None] = mapped_column(String(255))
    dataset_version: Mapped[str] = mapped_column(String(80), nullable=False, default="v1")
    ground_truth_status: Mapped[str] = mapped_column(String(40), nullable=False, default="pending")
    inclusion_status: Mapped[str] = mapped_column(String(40), nullable=False, default="included")
    exclusion_reason: Mapped[str | None] = mapped_column(Text)
    approved_reviewer_pseudonym: Mapped[str | None] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class GroundTruthRecord(Base):
    __tablename__ = "ground_truth_records"
    __table_args__ = {"schema": "research"}

    id: Mapped[str] = uuid_pk()
    evaluation_case_id: Mapped[str] = mapped_column(
        ForeignKey("research.evaluation_cases.id"), nullable=False, index=True
    )
    instruction_text: Mapped[str | None] = mapped_column(Text)
    medicine_name: Mapped[str | None] = mapped_column(String(255))
    strength: Mapped[str | None] = mapped_column(String(120))
    dosage_form: Mapped[str | None] = mapped_column(String(120))
    route: Mapped[str | None] = mapped_column(String(120))
    dose: Mapped[str | None] = mapped_column(String(120))
    frequency: Mapped[str | None] = mapped_column(String(120))
    duration: Mapped[str | None] = mapped_column(String(120))
    source: Mapped[str] = mapped_column(String(80), default="pharmacist_confirmed")
    version: Mapped[str] = mapped_column(String(40), default="1")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class EvaluationSnapshot(Base):
    __tablename__ = "evaluation_snapshots"
    __table_args__ = {"schema": "research"}

    id: Mapped[str] = uuid_pk()
    snapshot_code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    included_case_ids_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    excluded_cases_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    ground_truth_version: Mapped[str | None] = mapped_column(String(80))
    catalogue_version: Mapped[str | None] = mapped_column(String(80))
    ocr_config_json: Mapped[str | None] = mapped_column(Text)
    matching_algorithm_version: Mapped[str | None] = mapped_column(String(80))
    retrieval_config_json: Mapped[str | None] = mapped_column(Text)
    explanation_config_json: Mapped[str | None] = mapped_column(Text)
    metric_implementation_version: Mapped[str] = mapped_column(String(40), default="1.0.0")
    git_commit_hash: Mapped[str | None] = mapped_column(String(64))
    prescription_count: Mapped[int] = mapped_column(Integer, default=0)
    pharmacist_count: Mapped[int] = mapped_column(Integer, default=0)
    results_json: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class OcrEvaluationRun(Base):
    __tablename__ = "ocr_evaluation_runs"
    __table_args__ = {"schema": "research"}

    id: Mapped[str] = uuid_pk()
    snapshot_id: Mapped[str | None] = mapped_column(String(36), index=True)
    evaluation_case_id: Mapped[str] = mapped_column(
        ForeignKey("research.evaluation_cases.id"), nullable=False, index=True
    )
    engine_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    engine_version: Mapped[str | None] = mapped_column(String(80))
    raw_text: Mapped[str | None] = mapped_column(Text)
    structured_fields_json: Mapped[str | None] = mapped_column(Text)
    field_confidence_json: Mapped[str | None] = mapped_column(Text)
    processing_time_ms: Mapped[float | None] = mapped_column(Float)
    preprocessing_configuration_json: Mapped[str | None] = mapped_column(Text)
    error_status: Mapped[str | None] = mapped_column(String(80))
    cer: Mapped[float | None] = mapped_column(Float)
    wer: Mapped[float | None] = mapped_column(Float)
    metrics_json: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class RecommendationGoldStandard(Base):
    __tablename__ = "recommendation_gold_standards"
    __table_args__ = {"schema": "research"}

    id: Mapped[str] = uuid_pk()
    evaluation_case_id: Mapped[str] = mapped_column(
        ForeignKey("research.evaluation_cases.id"), nullable=False, index=True
    )
    reference_medicine: Mapped[str] = mapped_column(String(255), nullable=False)
    candidate_medicine: Mapped[str] = mapped_column(String(255), nullable=False)
    candidate_type: Mapped[str] = mapped_column(String(64), nullable=False)
    candidate_rank: Mapped[int | None] = mapped_column(Integer)
    same_active_ingredient: Mapped[bool | None] = mapped_column(Boolean)
    same_active_moiety: Mapped[bool | None] = mapped_column(Boolean)
    pharmacist_valid_candidate: Mapped[bool] = mapped_column(Boolean, nullable=False)
    pharmacist_reason: Mapped[str | None] = mapped_column(Text)
    evidence_source: Mapped[str | None] = mapped_column(String(120))
    reviewer_pseudonym: Mapped[str] = mapped_column(String(80), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class RecommendationEvaluationRun(Base):
    __tablename__ = "recommendation_evaluation_runs"
    __table_args__ = {"schema": "research"}

    id: Mapped[str] = uuid_pk()
    snapshot_id: Mapped[str | None] = mapped_column(String(36), index=True)
    condition: Mapped[str] = mapped_column(String(80), nullable=False)  # rules_only | rules_plus_mcs
    metrics_json: Mapped[str] = mapped_column(Text, nullable=False)
    availability: Mapped[str] = mapped_column(String(40), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class RagEvaluationRun(Base):
    __tablename__ = "rag_evaluation_runs"
    __table_args__ = {"schema": "research"}

    id: Mapped[str] = uuid_pk()
    snapshot_id: Mapped[str | None] = mapped_column(String(36), index=True)
    evaluation_case_id: Mapped[str | None] = mapped_column(String(36), index=True)
    retrieval_method: Mapped[str] = mapped_column(String(40), nullable=False)
    query: Mapped[str | None] = mapped_column(Text)
    retrieved_json: Mapped[str | None] = mapped_column(Text)
    explanation: Mapped[str | None] = mapped_column(Text)
    metrics_json: Mapped[str | None] = mapped_column(Text)
    availability: Mapped[str] = mapped_column(String(40), nullable=False)
    processing_time_ms: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ExplanationEvaluationAssignment(Base):
    __tablename__ = "explanation_evaluation_assignments"
    __table_args__ = {"schema": "research"}

    id: Mapped[str] = uuid_pk()
    participant_pseudonym: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    evaluation_case_id: Mapped[str | None] = mapped_column(String(36), index=True)
    condition: Mapped[str] = mapped_column(String(8), nullable=False)  # A | B | C
    order_index: Mapped[int] = mapped_column(Integer, default=0)
    payload_json: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PharmacistSurveyResponse(Base):
    __tablename__ = "pharmacist_survey_responses"
    __table_args__ = {"schema": "research"}

    id: Mapped[str] = uuid_pk()
    participant_pseudonym: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    condition: Mapped[str] = mapped_column(String(8), nullable=False)
    evaluation_case_id: Mapped[str | None] = mapped_column(String(36), index=True)
    likert_json: Mapped[str] = mapped_column(Text, nullable=False)
    free_text: Mapped[str | None] = mapped_column(Text)
    questionnaire_version: Mapped[str] = mapped_column(String(20), default="1.2")
    consent_confirmed: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
