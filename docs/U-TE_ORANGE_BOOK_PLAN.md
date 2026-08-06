# U-TE — FDA Orange Book therapeutic-equivalence layer (D3-02 regulatory / DQ2 gold standard)

## Goal
Add the FDA Orange Book `TE_Code` as the **authoritative regulatory therapeutic-equivalence signal**,
which NDC/DrugBank/SPL do not encode (validated by the supervisor). MCS (U5) is chemical *support*;
Orange Book is the *regulatory backbone*.

## Feasibility (probed — decisions this settles)
- Data present: `data/orange/products.txt` (48,501 rows), patent.txt, exclusivity.txt.
- TE distribution: **A\*=21,784** (equivalent), B\*=69 (not), empty=26,649 (innovator/single-source).
- Catalogue has **no `Appl_No`** — only `product_ndc`. So the crosswalk is by **normalised
  Ingredient + DF;Route + Strength** (strategy **a**), not NDC→application_number (strategy b, deferred).
- **Crosswalk coverage is good in the direction that matters:** **73% of Orange Book ingredients
  (2,020/2,739) are covered by the catalogue** via the `aliases` table (base + salt-stripped). (Only 21%
  of the 41k catalogue medicines match OB, because the catalogue is a much larger, messier NDC/SPL
  superset — expected and fine.)

## The TE model to encode
Group products by **Ingredient + Dosage Form + Route + Strength** (a pharmaceutical-equivalence group)
against the **RLD/RS** reference. Then:
- `A*` code ⇒ therapeutically equivalent / substitutable (AB, AA, AP, AT, AN, AO…).
- `B*` code ⇒ **not** equivalent.
- empty ⇒ single-source / innovator — **no equivalence to assert**.
- **Subletter is safety-critical:** `AB1 ≠ AB2 ≠ AB3` — substitutable only within the same subletter.
- **Filter `DISCN`** (discontinued) out of live "available equivalent" claims.

## Approach

### 1. Ingest Orange Book into the catalogue (read-only tables)
- `scripts/build_orange_book.py` (mirrors `build_smiles_table.py`): parse `products.txt` (+ optionally
  patent/exclusivity) into new tables in `medicine_catalog.sqlite3`:
  - `orange_products` (ingredient, df_route, trade_name, applicant, strength, appl_type, appl_no,
    product_no, te_code, approval_date, rld, rs, type, applicant_full_name) — keyed (appl_no, product_no).
  - Normalised helper columns: `ing_key`, `df`, `route`, `strength_key` for the crosswalk.
- Reproducible; the tables live inside the (gitignored) catalogue sqlite, rebuilt by the script.

### 2. TE service — `app/services/therapeutic/orange_book.py`
- `te_status_for(ingredient, dosage_form, route, strength)` → resolves the PE group and returns:
  `{ te_code, is_substitutable (A* and not DISCN), subletter_group, rld/rs reference, applicants,
     discontinued, single_source }`. `lru_cache`-backed loader over the sqlite tables.
- Normalisation reuses the existing salt-strip + name keys (shared with `smiles_catalog`) so keys match.
- Read-only, gated by `ENABLE_ORANGE_BOOK` (default on when the table exists; graceful when absent).

### 3. Surface in the recommendation engine (`therapeutic/evaluate.py`)
- Attach a `therapeutic_equivalence` block to each candidate: the FDA `TE_Code`, substitutable flag,
  subletter group, RLD reference, and the honesty note ("FDA TE rating; subletter-scoped; not a
  substitution instruction — pharmacist verifies"). **Does not auto-substitute or hard-gate** (HITL);
  it's authoritative *evidence*, surfaced alongside the score.
- New XAI/source consideration: TE is regulatory provenance, shown like the FDA source cards.

### 4. DQ2 gold standard (closes the D7-03/04 "no defensible relevant set" gap)
- Provide `orange_book_gold(reference_medicine)` → the set of A-rated products in the same PE group as
  the pharmacist-relevant set, so DQ2 Precision@K / Recall@K have a **regulatory ground truth** instead
  of a re-sorted pharmacist list. Offer it as an alternative gold source in the DQ2 harness.

### 5. Re-document as an approved scope addition (A10-style)
- The approved spec named RDKit-MCS for DQ2, not Orange Book. Record U-TE as an approved *scope addition*
  (the supervisor asked for it), same governance route as the platform/graph changes.

## Validation
1. Ingest is read-only + idempotent; `/health`+`/ready` catalog stays green; TE tables queryable.
2. `te_status_for` on known groups: METFORMIN 500MG TABLET;ORAL → RLD (GLUCOPHAGE, TE empty) + A-rated
   generics; a subletter case (different AB1/AB2) kept separate; a DISCN row flagged discontinued; an
   empty-TE single-source correctly reports "no A-rated equivalent".
3. Crosswalk match-rate report (catalogue medicine → OB group) matches the ~73% OB-ingredient coverage.
4. A therapeutic-alternatives run surfaces the FDA TE code on candidates that resolve to an OB group.
5. DQ2 gold-standard path returns the A-group; flag-off / OB-absent degrades gracefully.
6. Regression: research + therapeutic suites unchanged.

## Clears / reframes
- **D3-02 (regulatory TE):** Orange Book becomes the authoritative TE signal (MCS = support).
- **D7-03 / D7-04 (DQ2 gold standard):** a defensible regulatory relevant-set.
- New capability beyond the approved spec → documented as an A10-style scope addition.

## Honest caveats
- **US-only, systemic drugs:** 2,739 ingredients; foreign/compounded/OTC-monograph drugs aren't covered.
- **Crosswalk is name+form+route+strength** — normalisation mismatches (OB `500MG` vs NDC `2 mg/1`) will
  miss some; report unmatched rather than guess.
- **Not auto-substitution:** TE is decision-support evidence; the pharmacist remains the decision-maker
  (HITL). Subletter and DISCN rules must be honoured or the "equivalent" claim is unsafe.
- Strategy (b) (precise NDC→Appl_No) remains available later if higher-precision joins are needed.
