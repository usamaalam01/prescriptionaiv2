# Evaluation protocol (research layer)

## Dataset inclusion / exclusion

- Include only synthetic prescription evaluation cases with pseudonymous `case_code`.
- Exclude cases with missing pharmacist-confirmed ground truth from DQ1 aggregates.
- Record `exclusion_reason` on `research.evaluation_cases`.
- No patient-identifying information in evaluation stores.

## Ground-truth process

1. Pharmacist confirms instruction text and structured fields (medicine, strength, form, route, dose, frequency, duration).
2. Store as `GroundTruthRecord` with `source=pharmacist_confirmed`.
3. Aggregate metrics must link to an immutable `EvaluationSnapshot`.

## OCR comparison (DQ1)

- Engines evaluated independently under a common schema (`engine_id`, version, raw text, fields, confidence, latency, preprocessing, error).
- Production primary remains Google Vision; TrOCR is not overwritten by Vision.
- **Normalisation before WER/CER:** lowercase; collapse whitespace; strip punctuation except letters, digits, `%`, `.`, `/`, `-` (`ocr_metrics.normalise_for_error_rate`).
- Metrics return availability states; never display unavailable as zero.

## Recommendation gold standard (DQ2)

- Pharmacist records valid/invalid candidates with type, ranks, moiety flags, reason codes.
- Recall@K denominator = all valid gold candidates for the case.
- Compare rules-only vs rules+MCS (MCS supporting only).
- Display: structural similarity does not establish clinical interchangeability.

## RAG comparison (DQ3)

- Shared `EvidenceRetriever` interface; identical query and corpus for keyword and FAISS.
- Namespaces: `clinical_evidence`, `medicine_reference`, `project_documents`.
- Specification PDF must never enter `clinical_evidence`.
- Empty retrieval → `Insufficient evidence — pharmacist review required.`
- BERTScore optional; if missing → `DEPENDENCY_UNAVAILABLE` / `NOT_CALCULATED`.

## Explanation conditions (DQ4)

- A: score only; B: SHAP/LIME + components; C: B + FDA/DrugBank provenance.
- SHAP/LIME explain the additive scoring function; contributions reconcile to score where applicable.
- Counterbalanced condition order by participant pseudonym seed.

## Pharmacist questionnaire

- Collected **outside** PharmaAssist (e.g. Microsoft Forms v1.2 / other approved platform).
- Five-point Likert constructs as in Spec / `RESEARCH_QUESTIONNAIRE_GUIDE.md`.
- Optional free text; no names, emails, registration numbers, workplaces, or IPs in imports.
- Application role: import pseudonymised exports into `research.pharmacist_survey_responses` for summary/export only.
- In-app: explanation Conditions A/B/C may be previewed; the questionnaire itself is not an app form.

## Missing-data handling

Use `AVAILABLE | NOT_CALCULATED | INSUFFICIENT_GROUND_TRUTH | INSUFFICIENT_SAMPLE | DEPENDENCY_UNAVAILABLE | NOT_VERIFIABLE`.

## Privacy & reproducibility

- Pseudonyms only; immutable snapshots with case lists, versions, optional git hash.
- Counts derived from stored rows — never manual aggregate entry.

## Limitations

- Simulated OCR engines used when live APIs unavailable.
- FAISS may fall back to dense hashing without the FAISS package.
- Study evidence incomplete until 25–30 GT cases and pharmacist responses are deposited.
