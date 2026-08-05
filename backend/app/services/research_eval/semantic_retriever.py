"""U1 — real semantic FAISS retriever for the DQ3 research path.

Reuses the prebuilt index shipped in ``DATA_DIR`` (``rag_index.faiss`` +
``rag_chunks.pkl``, ~10k FDA SPL chunks, ``all-MiniLM-L6-v2`` embeddings,
FAISS ``IndexFlatL2``) — no rebuild. Query embedding happens per call; the
index/chunks/model are loaded once per process via an ``lru_cache`` singleton
(mirrors the loader pattern in ``datasets/catalog_store.py``).

The heavy stack (faiss + sentence-transformers + torch) is imported lazily
inside the loader so the app stays importable when ``ENABLE_SEMANTIC_RAG`` is
off or the deps are absent. Retrieval logic is ported from the old prescription
project's ``rag_engine.retrieve_evidence`` (over-fetch → search → dedup → map).

Accepted limitations (DQ3-scoped; revisited in U1b):
- ``lru_cache`` is not atomic, so a cold-start race could load the model twice;
  harmless (objects are read-only after load), just wasteful on first hits.
- The dedup key ``(drug_name, section, text[:100])`` can collapse two genuinely
  distinct labels that share a boilerplate 100-char prefix (ported behaviour).
- If the flag is ON but the index/deps fail to load, the caller falls back to the
  legacy toy hash-cosine retriever over the same corpus (degraded, not incorrect).
"""

from __future__ import annotations

import logging
import pickle
from functools import lru_cache
from typing import Any

from app.core.config import settings
from app.services.datasets.paths import rag_chunks_path, rag_faiss_path
from app.services.research_eval.evidence_retrievers import (
    EvidenceRetriever,
    RetrievedEvidence,
)

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _load_index_and_model() -> tuple[Any, list[dict[str, Any]], Any]:
    """Load the FAISS index, aligned chunks, and embedding model once per process.

    Raises on any failure (missing artefacts, uninstalled deps); callers guard
    with try/except and fall back to the toy retriever.
    """
    import faiss  # heavy; imported lazily
    from sentence_transformers import SentenceTransformer

    faiss_path = rag_faiss_path()
    chunks_path = rag_chunks_path()
    if not faiss_path.exists() or not chunks_path.exists():
        raise FileNotFoundError(
            f"Semantic RAG artefacts missing: {faiss_path} / {chunks_path}"
        )

    index = faiss.read_index(str(faiss_path))
    with open(chunks_path, "rb") as f:
        chunks = pickle.load(f)

    model_name = settings.RAG_EMBEDDING_MODEL
    try:
        model = SentenceTransformer(model_name)
    except Exception as exc:  # self-heal a corrupt/partial HF snapshot, then retry once
        logger.warning(
            "Embedding model load failed (%s: %s); forcing a clean re-download of '%s'.",
            type(exc).__name__, exc, model_name,
        )
        from huggingface_hub import snapshot_download

        repo_id = model_name if "/" in model_name else f"sentence-transformers/{model_name}"
        local_dir = snapshot_download(repo_id, force_download=True)
        model = SentenceTransformer(local_dir)

    logger.info(
        "Semantic RAG loaded: %d vectors, %d chunks, model=%s",
        index.ntotal, len(chunks), model_name,
    )
    return index, chunks, model


class SemanticFaissSplRetriever(EvidenceRetriever):
    """Semantic FDA-SPL retriever over the prebuilt MiniLM/FAISS index.

    ``retrieve`` embeds the query, over-fetches (guarding against class members
    ranking slightly higher), dedups by (drug_name, section, text-prefix), and
    maps each chunk to ``RetrievedEvidence`` with an L2→(0,1] similarity score.
    """

    def retrieve(self, query: str, *, top_k: int = 5) -> list[RetrievedEvidence]:
        index, chunks, model = _load_index_and_model()
        if not query or not chunks or top_k <= 0:
            return []

        query_vec = model.encode([query]).astype("float32")
        # search_k must be >= 1 (faiss asserts k>0); over-fetch to survive dedup.
        search_k = min(len(chunks), max(1, top_k, top_k * 12))
        distances, indices = index.search(query_vec, search_k)

        out: list[RetrievedEvidence] = []
        seen: set[tuple] = set()
        for dist, idx in zip(distances[0].tolist(), indices[0].tolist()):
            if idx < 0 or idx >= len(chunks):
                continue
            chunk = chunks[idx]
            key = (chunk.get("drug_name"), chunk.get("section"), (chunk.get("text") or "")[:100])
            if key in seen:
                continue
            seen.add(key)
            # Old chunks are keyed chunk_id=0 unless a long section was split, so use
            # the FAISS index position as a stable unique citation id.
            out.append(
                RetrievedEvidence(
                    record_id=f"chunk-{idx}",
                    section=str(chunk.get("section") or "unknown"),
                    text=str(chunk.get("text") or ""),
                    # L2 distance → bounded similarity (smaller distance = closer = higher score)
                    score=1.0 / (1.0 + float(dist)),
                    spl_set_id=None,
                    provenance="fda_spl",
                )
            )
            if len(out) >= top_k:
                break
        return out
