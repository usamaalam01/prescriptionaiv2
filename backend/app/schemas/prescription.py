from datetime import datetime

from pydantic import BaseModel, Field


class ReviewSessionOut(BaseModel):
    id: str
    status: str
    original_filename: str
    content_type: str
    file_size_bytes: int
    selected_ocr_engine: str | None = None
    temporary_deleted_at: datetime | None = None

    model_config = {"from_attributes": True}


class OcrRunIn(BaseModel):
    engine: str = Field(
        default="pipeline",
        pattern="^(pipeline|mock|paddleocr|tesseract|trocr|hybrid)$",
    )


class OcrJobOut(BaseModel):
    id: str
    session_id: str
    engine: str
    status: str
    raw_text: str
    confidence: float
    character_count: int
    processing_ms: int
    is_mock: bool
    warnings: list[str] = []
    pipeline: dict | None = None


class MedicineOut(BaseModel):
    id: str
    item_number: int
    ai_medicine_name: str
    ai_strength: str | None
    ai_form: str | None
    ai_dose: str | None
    ai_route: str | None
    ai_frequency: str | None
    ai_duration: str | None
    source_span: str | None
    parser_confidence: float
    formulary_matched: bool
    formulary_id: str | None
    formulary_warnings: list[str] = []
    pharmacist_status: str
    pharmacist_medicine_name: str | None = None
    pharmacist_strength: str | None = None
    pharmacist_form: str | None = None
    pharmacist_dose: str | None = None
    pharmacist_route: str | None = None
    pharmacist_frequency: str | None = None
    pharmacist_duration: str | None = None
    pharmacist_reason: str | None = None

    model_config = {"from_attributes": True}


class MedicineVerifyIn(BaseModel):
    status: str
    medicine_name: str | None = None
    strength: str | None = None
    form: str | None = None
    dose: str | None = None
    route: str | None = None
    frequency: str | None = None
    duration: str | None = None
    reason: str | None = None
