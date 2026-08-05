from pydantic import BaseModel, Field


class CitationOut(BaseModel):
    source: str
    source_id: str
    title: str
    url: str
    excerpt: str


class AlternativeSuggestionOut(BaseModel):
    id: str
    session_id: str
    medicine_id: str
    rank: int
    source_medicine: str
    alternative_medicine_name: str
    strength: str | None = None
    form: str | None = None
    route: str | None = None
    relationship: str
    rationale: str
    contraindications_note: str
    confidence: float
    explanation: str
    citations: list[CitationOut] = []
    knowledge_source: str
    is_mock_knowledge: bool

    model_config = {"from_attributes": True}


class AlternativeFeedbackIn(BaseModel):
    decision: str = Field(
        pattern="^(noted|accepted_for_discussion|rejected|needs_more_evidence)$",
    )
    note: str | None = None


class AlternativeFeedbackOut(BaseModel):
    id: str
    suggestion_id: str
    session_id: str
    decision: str
    note: str | None = None

    model_config = {"from_attributes": True}


class EvaluationSnapshotOut(BaseModel):
    phase: str
    disclaimer: str
    sessions_total: int
    ocr_jobs_total: int
    medicines_extracted_total: int
    formulary_matched_total: int
    formulary_match_rate: float | None
    verification_by_status: dict[str, int]
    pharmacist_reviewed_total: int
    override_or_correction_rate: float | None
    avg_ocr_confidence: float | None
    avg_parser_confidence: float | None
    alternative_suggestions_total: int
    alternative_feedback_by_decision: dict[str, int]
    knowledge_mode: str


class FieldCorrectionIn(BaseModel):
    field: str = Field(pattern="^(drug|route|strength|dose|frequency|indication)$")
    # Empty string allowed to clear optional indication
    value: str = Field(default="", max_length=255)
