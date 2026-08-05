# Recorded demo checklist — PharmaAssist (≈3–4 min)

Screen-record this sequence. Keep the decision-support disclaimer visible.

## Before record
- [ ] API + UI running; catalog ready (~41k)
- [ ] Password already changed for `pharmacist` (skip forced-change UI on camera)
- [ ] Test Rx open: `data/test_prescriptions/curated_hitl_test_rx_ocr_friendly.png`
- [ ] Browser zoom 110–125%; hide bookmarks bar

## Shot list
1. **Stance (10s)** — Home: say “decision-support HITL, not clinical care.”
2. **Catalog (40s)** — `/catalog` → search Cetirizine → show FDA_NDC / DrugBank / SPL chips + strengths.
3. **Augmentin point (20s)** — lookup Augmentin vs amoxicillin and clavulanate potassium.
4. **OCR queue (45s)** — Analyzer upload → Run pipeline → show `queued → running → completed`.
5. **HITL cascade (60s)** — confirm Drug → Strength → Dose → Frequency (indication optional) with source badges.
6. **Audit (20s)** — HITL audit trail after Confirm.
7. **Alts / analytics (30s)** — alternatives never auto-applied; summary metrics.
8. **Honesty (20s)** — `/health` retention hours + production framing; cancel/session deletes encrypted image.

## Narration close
“Human confirmation is mandatory; FDA/DrugBank provenance is the evidence, not the decision.”

Full viva talk track: [`AWARD_DEMO.md`](AWARD_DEMO.md) · Architecture canvas: `pharmaassist-viva-architecture.canvas.tsx`
