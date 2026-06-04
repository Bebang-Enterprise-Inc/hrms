# C1 Prior Session Check — 5 COA Audit Items

**Date:** 2026-06-04
**Sources scanned:**
- `F:/Dropbox/Projects/BEI-ERP/data/_CLEANROOM/2026-04-09_s175_coa_restructure/` (all 8 files, full content)
- `F:/Dropbox/Projects/BEI-ERP/data/_CONSOLIDATED/01_FINANCE/DECISIONS.md` (full)
- `C:/Users/Sam/.claude/projects/F--Dropbox-Projects-BEI-ERP/*.jsonl` (229 transcripts scanned, top-300 by mtime, excluding current session)

---

## ITEM 1 — ROUND OFF account: case + root_type, ROBDA/XMM Liability duplicates

**STATUS: NOT FOUND** (no prior decision on naming case, root_type, or the duplicate cleanup)

**Negative evidence:**
- `DECISIONS.md`: no hit on `ROUND OFF`, `Round Off`, `ROBDA`, `XMM`, `Freeze Delight`, `Perpetual Food`.
- `02_LOCKED_DECISIONS.md` / `06_BUTCH_ANSWERS.md`: no Round Off topic. Butch's S175 questionnaire (OQ-1..OQ-5) does not touch Round Off.
- Transcript hits on `ROUND OFF / round_off` are exclusively (a) provisioning code creating `"Round Off"` in account-name lists, or (b) Frappe `LinkValidationError` traces complaining `Round Off Cost Center: Main - BFI2` is missing during Company.company_type changes. No decision on UPPER-vs-Title case, no decision on Expense-vs-Liability root_type, no mention of the ROBDA/XMM duplicates.

**Implication:** Open question. Sam must decide.

---

## ITEM 2 — BEI account suffix: `- BEI` vs `- Bebang Enterprise Inc.`, global rename?

**STATUS: NOT FOUND** (no global-rename decision; the two forms coexist by accident, not by policy)

**Evidence of coexistence (not decision):**
- `02_LOCKED_DECISIONS.md:141` and `06_BUTCH_ANSWERS.md:52`: live accounts using long form, e.g. `INPUT VAT - GOODS - Bebang Enterprise Inc.`, `INPUT VAT - SERVICES - Bebang Enterprise Inc.`, `CREDITABLE WITHHOLDING TAXES - Bebang Enterprise Inc.`, `ACCOUNTS PAYABLE - Bebang Enterprise Inc.`.
- Same files: short-form siblings `GR/IR CLEARING - BEI`, `4000234 MARKETING FEES - BEI`, `2104200 DUE TO BFC - BEI`, `Cash on Hand - BEI`.
- Transcripts (S196 / S199, 2026-04-15 → 2026-04-16, session `691feb38…`): renames touched **Company names** (corp-first → store-first → ALL CAPS, e.g. `SM MEGAMALL - BEBANG ENTERPRISE INC.`), driven by CEO directive *"operators don't know the fucking corp names"*. These renames operated on `tabCompany` and child `tabWarehouse`; no commit on renaming the ~338 `tabAccount` rows to a single suffix style.
- One assistant note (2026-04-15, `691feb38…`): explicitly classifies remaining `<Store> - BEI` warehouse cleanup as *"Cosmetic"* — i.e. nobody promoted it to a locked decision.

**Implication:** No global rename ever decided. Long form is Apex/legacy import; short form is Frappe abbr cascade. Both will persist until Sam decides.

---

## ITEM 3 — 4 BEI orphan parent_account references (STOCK ADJUSTMENT, GR/IR CLEARING, PPE, ADVANCES TO SSS)

**STATUS: NOT FOUND** (raised, flagged to Butch, never answered)

**Evidence:**
- `06_POST_EXECUTION_CORRECTIONS.md:89-102` (Correction 3): the 4 orphans are explicitly listed with their broken parents (`COST OF SALES - BEI`, `INVENTORY - BEI`, `NON-CURRENT ASSETS - BEI`, `NON-TRADE RECEIVABLES - BEI` — all "does not exist"). File concludes: *"Flagged to Butch for a separate data-quality follow-up task. Not in S175 scope, not blocking PR #523."*
- `06_BUTCH_ANSWERS.md`: Butch's only 5 answers cover Fork choice, BFC OR booklet, VAT payment mechanism, cutover trigger, input_vat_goods_account link, JV fee routing. **No answer on the 4 orphans.**
- `DECISIONS.md`: no orphan repoint decision (COA-001..COA-010 cover unrelated items).
- Transcript hits on orphan terminology refer to Docker container orphans (2026-04-14) and S233 canonical-resolver test orphans (2026-05-03), not these 4 accounts.

**Implication:** Open question for Butch (or Denise, post-resignation). Each of the 4 needs a destination parent in the canonical tree.

---

## ITEM 4 — VAT Input account structure: 4-stem split canonical, or consolidate?

**STATUS: NOT FOUND** as a structural decision (no "4-stem canonical" or "consolidate" decision exists)

**Evidence of fragments only:**
- `COA-005 (DECISIONS.md:51)` Butch 2026-02-09: *"Input VAT accounts (3 separate) — 1105103 (Goods), 1105104 (Services), 1105105 (Importation)"* — this is the **BEI/BKI/III** 3-account split, NOT the 4-stem-incl-1106210-store-Inter-Co structure.
- `S233` (transcript 2026-05-11, `a9ee5879…`): creates `1106210` as `Input VAT - BKI Inter-Co` across 49 stores (147 leaf accounts: `1104210` Inv-from-Commissary + `1106210` Input VAT BKI Inter-Co + `2103210` AP-Trade-BKI). This is an **operational implementation**, not a documented "canonical 4-stem" decision.
- `02_LOCKED_DECISIONS.md:141`: only decision is "link `INPUT VAT - GOODS - Bebang Enterprise Inc.` to BEI Settings." Silent on the 4-stem question.
- No transcript or doc says "consolidate Input VAT to one stem" and no transcript or doc says "the 4-stem split is the canonical end-state."

**Implication:** De facto state = 4-stem (1105103/04/05 BEI+BKI+III legacy + 1106210 49-store inter-co), but never blessed as canonical. Decision needed.

---

## ITEM 5 — DMD Holdings TIN re-verify (post Butch 2026-02-27 flag)

**STATUS: FOUND** (re-verify completed; DMD has its own TIN, NOT shared with III)

**Evidence:**
- `06_POST_EXECUTION_CORRECTIONS.md:70`: *"DMD Holdings shared TIN 634-954-873-00000 with Irresistible Infusions Inc. Butch corrected DMD's TIN on that date. Recommend re-verifying live."*
- `bei_company_register_team_completed_2026-04-10.csv` row 16: `DMD HOLDINGS INC., DHI, Holdings, TIN 649-154-841-00000, RDO 041, VAT Registered, Andrew Rodel Manansala, Uptown Mall (TIN: 649-154-841-00001, RDO 044)`. Distinct from III's `634-954-873-00000`.
- Transcript `f1bd2139…` 2026-05-05 confirms operational: location_id 2548 ("DMD HOLDINGS INC.") owns UP Town Mall BGC; UPTC vs Uptown BGC confusion *"RESOLVED (Feb 12)"*.
- Transcript `agent-a3bff4b404c2e2572.jsonl` 2026-05-03 and `517586f9…` 2026-05-22 reuse the same DMD TIN `649-154-841-00000`.

**Summary:** DMD owns TIN `649-154-841-00000` (HO) + branch TIN `649-154-841-00001` for UP Town Mall BGC, distinct from III (`634-954-873-00000`). Re-verify is effectively closed by the 2026-04-10 team-completed register and three downstream sessions consuming that value.

---

## Roll-up

| Item | Status | Date locked | Source |
|------|--------|-------------|--------|
| 1 ROUND OFF naming/root_type/duplicates | NOT FOUND | — | — |
| 2 BEI suffix global rename | NOT FOUND | — | — |
| 3 4 BEI orphan parent_account | NOT FOUND (flagged to Butch, no answer) | — | `06_POST_EXECUTION_CORRECTIONS.md:89-102` |
| 4 VAT 4-stem canonical vs consolidate | NOT FOUND | — | — |
| 5 DMD Holdings TIN re-verify | FOUND | 2026-04-10 (team register) | `bei_company_register_team_completed_2026-04-10.csv:16` |

**Total found:** 1
**Total not found:** 4
