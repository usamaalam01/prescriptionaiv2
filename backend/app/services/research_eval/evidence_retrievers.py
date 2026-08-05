"""Evidence retrieval interface for DQ3 (keyword production + experimental FAISS)."""

from __future__ import annotations

import hashlib
import os
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
from typing import Any

# Clinical evidence namespace — never include specification PDF.
CLINICAL_EVIDENCE = "clinical_evidence"
MEDICINE_REFERENCE = "medicine_reference"
PROJECT_DOCUMENTS = "project_documents"

INSUFFICIENT_EVIDENCE = "Insufficient evidence — pharmacist review required."


@dataclass
class RetrievedEvidence:
    record_id: str
    section: str
    text: str
    score: float
    spl_set_id: str | None = None
    namespace: str = CLINICAL_EVIDENCE
    provenance: str = "fda_spl"


class EvidenceRetriever(ABC):
    namespace: str = CLINICAL_EVIDENCE

    @abstractmethod
    def retrieve(self, query: str, *, top_k: int = 5) -> list[RetrievedEvidence]:
        ...


class KeywordSPLRetriever(EvidenceRetriever):
    """Production baseline: keyword overlap over FDA SPL-like corpus chunks."""

    def __init__(self, corpus: list[dict[str, Any]] | None = None):
        self.corpus = corpus or []

    def retrieve(self, query: str, *, top_k: int = 5) -> list[RetrievedEvidence]:
        q = set((query or "").lower().split())
        scored: list[RetrievedEvidence] = []
        for row in self.corpus:
            text = str(row.get("text") or "")
            toks = set(text.lower().split())
            if not q or not toks:
                continue
            overlap = len(q & toks) / max(len(q), 1)
            if overlap <= 0:
                continue
            scored.append(
                RetrievedEvidence(
                    record_id=str(row.get("id") or row.get("spl_set_id") or ""),
                    section=str(row.get("section") or "unknown"),
                    text=text,
                    score=float(overlap),
                    spl_set_id=row.get("spl_set_id"),
                    provenance=str(row.get("provenance") or "fda_spl"),
                )
            )
        scored.sort(key=lambda x: x.score, reverse=True)
        return scored[:top_k]


class FAISSSPLRetriever(EvidenceRetriever):
    """
    Experimental reviewer-mode retriever.
    Uses FAISS when available; otherwise bag-of-words cosine over hashing (same corpus).
    Feature flag: RESEARCH_FAISS_ENABLED=1
    """

    def __init__(self, corpus: list[dict[str, Any]] | None = None):
        self.corpus = corpus or []
        self._index = None
        self._vectors: list[list[float]] | None = None
        self._faiss = None
        if os.environ.get("RESEARCH_FAISS_ENABLED", "").strip() in {"1", "true", "True"}:
            try:
                import faiss  # type: ignore

                self._faiss = faiss
            except Exception:
                self._faiss = None
        self._build()

    def _embed(self, text: str, dim: int = 64) -> list[float]:
        vec = [0.0] * dim
        for tok in (text or "").lower().split():
            h = int(hashlib.md5(tok.encode()).hexdigest(), 16)
            vec[h % dim] += 1.0
        norm = sum(v * v for v in vec) ** 0.5
        if norm:
            vec = [v / norm for v in vec]
        return vec

    def _build(self) -> None:
        if not self.corpus:
            return
        self._vectors = [self._embed(str(r.get("text") or "")) for r in self.corpus]
        if self._faiss is not None and self._vectors:
            import numpy as np

            arr = np.array(self._vectors, dtype="float32")
            index = self._faiss.IndexFlatIP(arr.shape[1])
            index.add(arr)
            self._index = index

    def retrieve(self, query: str, *, top_k: int = 5) -> list[RetrievedEvidence]:
        if not self.corpus or not self._vectors:
            return []
        qv = self._embed(query)
        if self._index is not None:
            import numpy as np

            D, I = self._index.search(np.array([qv], dtype="float32"), min(top_k, len(self.corpus)))
            out: list[RetrievedEvidence] = []
            for score, idx in zip(D[0].tolist(), I[0].tolist()):
                if idx < 0:
                    continue
                row = self.corpus[idx]
                out.append(
                    RetrievedEvidence(
                        record_id=str(row.get("id") or row.get("spl_set_id") or ""),
                        section=str(row.get("section") or "unknown"),
                        text=str(row.get("text") or ""),
                        score=float(score),
                        spl_set_id=row.get("spl_set_id"),
                        provenance=str(row.get("provenance") or "fda_spl"),
                    )
                )
            return out
        # Fallback: dense cosine without FAISS
        scored: list[tuple[float, int]] = []
        for i, v in enumerate(self._vectors):
            score = sum(a * b for a, b in zip(qv, v))
            if score > 0:
                scored.append((score, i))
        scored.sort(reverse=True)
        out = []
        for score, i in scored[:top_k]:
            row = self.corpus[i]
            out.append(
                RetrievedEvidence(
                    record_id=str(row.get("id") or row.get("spl_set_id") or ""),
                    section=str(row.get("section") or "unknown"),
                    text=str(row.get("text") or ""),
                    score=float(score),
                    spl_set_id=row.get("spl_set_id"),
                    provenance=str(row.get("provenance") or "fda_spl"),
                )
            )
        return out


def evidence_to_dict(items: list[RetrievedEvidence]) -> list[dict[str, Any]]:
    return [asdict(x) for x in items]


def build_explanation_from_evidence(query: str, evidence: list[RetrievedEvidence]) -> str:
    if not evidence:
        return INSUFFICIENT_EVIDENCE
    lines = [
        f"Decision-support summary for pharmacist review (query: {query}).",
        "Claims are bound only to retrieved evidence IDs below.",
    ]
    for e in evidence:
        cite = e.record_id or e.spl_set_id or "unknown"
        snippet = (e.text or "")[:280]
        lines.append(f"[{cite}] ({e.section}): {snippet}")
    lines.append(
        "This is not a clinical source of truth. Pharmacist confirmation required."
    )
    return "\n".join(lines)


def citation_coverage(explanation: str, evidence: list[RetrievedEvidence]) -> float:
    if not evidence:
        return 1.0 if INSUFFICIENT_EVIDENCE in (explanation or "") else 0.0
    ids = [e.record_id or e.spl_set_id or "" for e in evidence]
    ids = [i for i in ids if i]
    if not ids:
        return 0.0
    hit = sum(1 for i in ids if i in (explanation or ""))
    return hit / len(ids)


def unsupported_claim_rate(explanation: str, evidence: list[RetrievedEvidence]) -> float:
    """Heuristic: sentences without a bracketed evidence id are unsupported."""
    if INSUFFICIENT_EVIDENCE in (explanation or ""):
        return 0.0
    sentences = [s.strip() for s in (explanation or "").split(".") if s.strip()]
    if not sentences:
        return 0.0
    ids = [e.record_id or e.spl_set_id or "" for e in evidence]
    unsupported = 0
    for s in sentences:
        if "[" in s and "]" in s:
            continue
        if any(i and i in s for i in ids):
            continue
        if s.lower().startswith("decision-support") or "pharmacist" in s.lower():
            continue
        unsupported += 1
    return unsupported / len(sentences)
