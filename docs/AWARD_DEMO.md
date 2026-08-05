# Award / viva demo script — PharmaAssist

**Positioning (say this first):**  
PharmaAssist is a **pharmacist decision-support HITL** prototype. It uses **local FDA NDC + DrugBank + FDA SPL** data for verification. It is **not** clinical care and never auto-dispenses.

---

## 0. Prep (2 min)

1. Start API + UI (or Docker: `docker compose up --build`).
2. Login: `pharmacist` / `ChangeMePharm!234`.
3. If prompted, set a personal password (seed accounts force change).
4. Confirm Analyzer banner shows **Catalog ready** (~41k medicines).

Optional: open **Medicine catalog explorer** → search `Cetirizine` → show DrugBank + FDA_NDC + FDA_SPL chips.
Optional: hit `http://127.0.0.1:8000/health` — show catalog + component readiness.

---

## 1. Dataset differentiator (1 min)

- Catalog Explorer → `Augmentin` vs `amoxicillin and clavulanate potassium`.
- Point: brand alias vs product strengths live on the generic combo — HITL must pick the verified catalog drug.

---

## 2. OCR → HITL cascade (4 min)

1. Upload `data/test_prescriptions/curated_hitl_test_rx_ocr_friendly.png` (or a clinic Rx).
2. **Run full pipeline** — show OCR job status (`queued` → `running` → `completed`), then Vision extraction (or labelled MOCK if Vision unavailable).
3. HITL table:
   - Drug typeahead → **FDA/DrugBank source badges**
   - Unlock strength → dose → frequency
   - Indication **optional** but dataset-only when used
4. Confirm a row → show **HITL audit trail** (field corrected / row confirmed).

---

## 3. Therapeutic alternatives + analytics (2 min)

- After confirm, open alternatives — pharmacist accept/reject with reason (never auto-applied).
- Summary Analytics — OCR vs pharmacist corrections (research metrics).

---

## 4. Production / research honesty (1 min)

- Fail-closed production guards (weak secrets / mock OCR banned in prod).
- Audit schema for HITL + therapeutic decisions.
- Encrypted Rx retention: cancel / confirm-all / timed purge (`TEMP_FILE_RETENTION_HOURS`).
- Explicit decision-support disclaimer on every journey screen.

**Close:** “Human confirmation is mandatory; FDA/DrugBank provenance is the evidence, not the decision.”

---

Screen-record shot list: [`RECORDED_DEMO.md`](RECORDED_DEMO.md)
