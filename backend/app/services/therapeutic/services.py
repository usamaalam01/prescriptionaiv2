"""Named service facades for therapeutic alternatives (spec-aligned entry points)."""

from app.services.therapeutic.evaluate import evaluate_prescription
from app.services.therapeutic.identity import normalize_name, resolve_identity
from app.services.therapeutic.indication import normalize_indication_text, normalize_mechanism
from app.services.therapeutic.retriever import retrieve_candidates
from app.services.therapeutic.safety import screen_candidate
from app.services.therapeutic.scoring import calculate_evidence_match_score
from app.services.therapeutic.seed_data import (
    DATASET_VERSION,
    DEMO_LABEL,
    DRUGBANK_RECORDS,
    FDA_NDC_RECORDS,
    FDA_SPL_RECORDS,
    RULES_ENGINE_VERSION,
    get_drugbank,
    get_ndc,
    get_spl,
)
from app.services.therapeutic.xai import DISCLAIMER, build_source_claims, explain_candidate


class DrugBankNormalizer:
    @staticmethod
    def normalize(record_id: str) -> dict | None:
        return get_drugbank(record_id)

    @staticmethod
    def all_records() -> dict:
        return DRUGBANK_RECORDS


class FDASPLNormalizer:
    @staticmethod
    def normalize(record_id: str) -> dict | None:
        return get_spl(record_id)

    @staticmethod
    def all_records() -> dict:
        return FDA_SPL_RECORDS


class FDANDCNormalizer:
    """Product/formulation only — never therapeutic equivalence proof."""

    @staticmethod
    def normalize(record_id: str) -> dict | None:
        return get_ndc(record_id)

    @staticmethod
    def all_records() -> dict:
        return FDA_NDC_RECORDS


class DrugIdentityResolver:
    resolve = staticmethod(resolve_identity)
    normalize_name = staticmethod(normalize_name)


class IndicationNormalizer:
    normalize = staticmethod(normalize_indication_text)
    normalize_mechanism = staticmethod(normalize_mechanism)


class TherapeuticCandidateRetriever:
    retrieve = staticmethod(retrieve_candidates)


class SafetyScreeningService:
    screen = staticmethod(screen_candidate)


class EvidenceComparisonService:
    @staticmethod
    def compare_route_and_form(safety_result: dict) -> dict:
        return {
            "route_comparison": safety_result.get("route_comparison") or {},
            "dosage_form_comparison": safety_result.get("dosage_form_comparison") or {},
        }


class EvidenceScoreService:
    calculate = staticmethod(calculate_evidence_match_score)


class CandidateRankingService:
    @staticmethod
    def rank_eligible(eligible_rows: list, top_n: int = 5) -> list:
        """eligible_rows: list of (payload, cand, safety, score, claims) tuples."""
        eligible_rows = sorted(
            eligible_rows,
            key=lambda row: (
                -int(bool(row[1]["indication_relationship"].get("overlap"))),
                -int(row[2]["status"] == "eligible_for_pharmacist_review"),
                -row[3]["evidence_coverage"]["coverage_percentage"],
                -int(bool(row[1]["class_relationship"].get("related"))),
                -int(bool(row[1]["mechanism_relationship"].get("related"))),
                -row[3]["total_score"],
            ),
        )
        return eligible_rows[:top_n]


class XAIExplanationService:
    explain = staticmethod(explain_candidate)
    disclaimer = DISCLAIMER


class SourceProvenanceService:
    build_claims = staticmethod(build_source_claims)

    @staticmethod
    def assert_claims_have_sources(claims: list[dict]) -> bool:
        allowed = {"DrugBank", "FDA_SPL", "FDA_NDC"}

        def _dataset_ok(value: str | None) -> bool:
            if not value:
                return False
            if value in allowed:
                return True
            parts = {p.strip() for p in value.replace("+", ",").replace("/", ",").split(",") if p.strip()}
            return bool(parts) and parts.issubset(allowed)

        return all(_dataset_ok(c.get("source_dataset")) and c.get("source_record_id") for c in claims)


class PharmacistDecisionService:
    ALLOWED = {"accept_for_review", "reject", "request_more_evidence"}

    @staticmethod
    def validate(action: str, reason: str) -> None:
        if action not in PharmacistDecisionService.ALLOWED:
            raise ValueError("Unsupported pharmacist action")
        if action in {"reject", "request_more_evidence"} and not (reason or "").strip():
            raise ValueError("Reason is required for reject or request_more_evidence")


class RecommendationAuditService:
    @staticmethod
    def envelope(*, evaluation_id: str, event_type: str, payload: dict) -> dict:
        return {
            "evaluation_id": evaluation_id,
            "event_type": event_type,
            "payload": payload,
            "dataset_version": DATASET_VERSION,
            "rules_engine_version": RULES_ENGINE_VERSION,
            "demo_label": DEMO_LABEL,
        }


__all__ = [
    "DrugBankNormalizer",
    "FDASPLNormalizer",
    "FDANDCNormalizer",
    "DrugIdentityResolver",
    "IndicationNormalizer",
    "TherapeuticCandidateRetriever",
    "SafetyScreeningService",
    "EvidenceComparisonService",
    "EvidenceScoreService",
    "CandidateRankingService",
    "XAIExplanationService",
    "SourceProvenanceService",
    "PharmacistDecisionService",
    "RecommendationAuditService",
    "evaluate_prescription",
]
