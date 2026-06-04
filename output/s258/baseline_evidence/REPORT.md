# COA Cleanroom vs Frappe Audit — for QBO Migration

**Audited:** 2026-06-04 against live `hq.bebang.ph`
**For:** Sam (CEO) — pre-QuickBooks Online migration sign-off
**Inputs:** `frappe_state.md`, `naming_inconsistencies.md`, `comparison_per_company.md` (all under `tmp/coa_audit/`)

---

## TL;DR

- **No, we are NOT ready to lift-and-shift.** 58 companies in Frappe, but only **6 are QBO-ready today**. **52 of 58 need work** before QBO import.
- **There is no single "cleanroom COA" file per company.** What we have is (a) one curated 217-account ERP spec at `docs/erp/CHART_OF_ACCOUNTS_ERP_COA_2025-12-23.csv`, (b) a 310-row working sheet `data/_FINAL/COA.csv`, and (c) a derived 114-account store template that was actually applied to 49 stores during seeding. The store template is now the de-facto SSOT for store entities. The Apex parents (BEI, BKI, III) still run on the raw Apex dump — the curated spec was never applied to them.
- **The big QBO blockers are concentrated in 9 companies:** BEI / BKI / III (Apex flat-tree dialect, 250-330 accounts each, will collide on QBO import), 4 stub stores (ROA, SMM, SMMM, SMS — 12 accounts, no Equity/Income/Expense), and 2 empty companies (BFC, BFI2 — 0 accounts).
- **The other 45 PARTIAL companies need a 1-field SQL update** (`default_inventory_account`) plus a duplicate Round Off cleanup on ROBDA + XMM. That is a sweep, not a project.
- **Naming inconsistencies that WILL break QBO:** 5 BLOCKER classes — Round Off (2 variants), Accounts Receivable (3), Accounts Payable (3), VAT Input (4), and the flat-tree Apex roots. These come almost entirely from BEI/BKI/III. Fix those three and 90% of the naming problem disappears.

---

## Cleanroom Status

**Where does the cleanroom live?**

There is no per-company cleanroom directory. Four artifacts are in play:

| File | Rows | Purpose | Authority |
|---|---:|---|---|
| `docs/erp/CHART_OF_ACCOUNTS_ERP_COA_2025-12-23.csv` | 217 | Canonical ERP COA spec, original cleanroom baseline | SSOT (baseline) |
| `data/_FINAL/COA.csv` | 310 | Working SSOT w/ Butch comments + Alyssa responses | SSOT (working) |
| `data/Finance_AP_AR/extractions/2026-01-16/raw/01_COA_BANK_DIRECTORY_ERP.xlsx` | 217 | Raw Apex export (Income Streams + Fund Details) | Source extract |
| `data/Finance_Validation_Package_2026-01-21/01_COA_FOR_VALIDATION.csv` | 359 | Finance validation copy w/ subsidiary flag | Validation snapshot |

**How many companies have an explicit cleanroom COA?**
- **3 group entities** (BEI, BKI, III) have explicit cleanroom specs — but the specs were never applied; the Apex CSV dumps still run in production.
- **49 store companies** are covered by a derived 114-account store template, applied in two waves (2026-03-03: 27 stores; 2026-04-13: 18 stores). This template is internally consistent across all 49 stores (30 Asset / 16 Liability / 6 Equity / 32 Income / 30 Expense = 114).
- **6 companies have NO cleanroom AND no live state:** BFC, BFI2 (empty) and ROA, SMM, SMMM, SMS (stub — seeding skipped them).

**Is it canonical or scratch?**
- Canonical: `docs/erp/CHART_OF_ACCOUNTS_ERP_COA_2025-12-23.csv` + `data/_FINAL/COA.csv` (treat as SSOT for BEI/BKI/III).
- De-facto canonical for stores: the 114-account template, best evidenced by the 6 HEALTHY companies (AYVER, BMI2, BDV, BAG, SMK, GHO).

---

## Frappe Live State

58 companies, 6,621 tabAccount rows. Status breakdown:

| Status | Count | Meaning | Companies |
|---|---:|---|---|
| HEALTHY | 6 | Full 5-root tree + all 10 critical fields populated | AYVER, BMI2, BDV, BAG, SMK, GHO |
| PARTIAL | 46 | Operational, but missing 1-3 critical fields (mostly `default_inventory_account`) | 43 store companies + BEI + BKI + III |
| MINIMAL | 4 | Stub 12-account COA, broken | ROA, SMM, SMMM, SMS |
| MISSING | 2 | Empty (0 accounts) | BFC, BFI2 |

**Critical gaps in numbers:**

- **50 of 58 companies missing `default_inventory_account`** — universal seeding miss. Blocks Frappe Stock posting but does NOT block QBO import.
- **9 companies missing `round_off_account` field setting:** BEI, BKI, BFC, BFI2, III, ROA, SMM, SMMM, SMS.
- **3 Apex-dialect parents have flat trees:** BEI = 153/331 accounts at root (46%); BKI = 284/325 (87%); III = 293/338 (87%). For QBO import these MUST be re-parented into the standard 5-root tree.
- **4 stub stores** (ROA, SMM, SMMM, SMS) have only Asset+Liability roots — no Equity / Income / Expense. QBO import would produce 4 empty company files.
- **2 empty companies** (BFC = Bebang Franchise Corp., BFI2 = Bebang FT Inc.) created 2026-05-02, never seeded.
- **III** is the worst: missing 7 of 10 critical fields (round_off_account, default_receivable_account, default_payable_account, default_expense_account, exchange_gain_loss_account, write_off_account, default_inventory_account).

---

## Naming Consistency

**5 BLOCKER classes for QBO import** (will create duplicate/orphan GL accounts):

| Class | Distinct stems | Detail | Owners |
|---|---:|---|---|
| Round Off | 2 | `Round Off` (Expense) x49 vs `ROUND OFF` (Liability) x2 | ROBDA, XMM |
| Accounts Receivable | 3 | `Accounts Receivable` x49 vs `ACCOUNTS RECEIVABLE` x5 vs `ACCOUNTS RECEIVABLE-OTHERS` x3 | BEI, BKI, III, ROBDA, XMM |
| Accounts Payable | 3 | `Accounts Payable` x53 vs `ACCOUNTS PAYABLE` x5 vs `ACCOUNTS PAYABLE - OTHERS` x3 | BEI, BKI, III, ROBDA, XMM |
| VAT Input | 4 | `1106210 - Input VAT - BKI Inter-Co` x49 vs `INPUT VAT - GOODS` / `INPUT VAT - IMPORTATION` / `INPUT VAT - SERVICES` x3 each | BEI, BKI, III |
| Apex flat-tree roots | n/a | 250-330 root-level accounts per company; UPPER case; number-prefixed | BEI, BKI, III |

**62 WARNING classes** (will not block QBO but will break consolidated reports): 11 Depreciation variants, 27 Salary/Wages variants, 19 Sales variants, 6 Rent variants, 3 Cost-of-Goods-Sold variants. All driven by Apex-dialect bleed-through from BEI/BKI/III into otherwise clean store COAs.

**The pattern:** **fix BEI, BKI, III -> 90% of naming inconsistency vanishes** because the cross-company variants almost exclusively trace back to those three.

**Two parallel dialects in production:**
- **Apex dialect** (BEI, BKI, III + partially ROBDA, XMM, and the 4 stubs): UPPER, number-prefixed, flat tree.
- **ERPNext dialect** (49 store companies): Title case, no number prefix, properly nested under Asset/Liability/Equity/Income/Expense.

Currency: 100% PHP across all 6,621 accounts. No anomalies.

---

## Bridge Consulting Context

Bridge is the external consultancy running the APEX -> QBO migration. Per the 2026-06-01 handover (`output/bridge_handover/`):

**They already have:**
- The 31-file Drive handover package (Commenter access for 6 `@bridge-ph.com` users).
- The canonical baseline COA spec (`CHART_OF_ACCOUNTS_ERP_COA_2025-12-23.csv`).
- The 217-row Apex source extract.
- The Finance Validation package COA (359 rows w/ subsidiary flag).

**They still need (4 items APEX still owes + our gaps):**
1. **A reconciled per-company COA export** — what is ACTUALLY in Frappe today vs the cleanroom spec, per company. The audit we just ran (`frappe_state.json` + `comparison_per_company.md`) is the input for this; we still owe Bridge a consolidated CSV.
2. **A go/no-go list for BFC + BFI2** — they cannot start QBO setup for two empty companies.
3. **A flat->nested re-parenting plan for BEI, BKI, III** — Bridge cannot start QBO import for these three until we decide which dialect wins. Today it is "raw Apex". The cleanroom says "ERPNext 217-acct nested".
4. **Status on the 4 stub stores** — are ROA/SMM/SMMM/SMS going live or being absorbed back into BEI parent for billing?

---

## The 3 Questions Sam Asked, Answered

### 1. Do we have cleanroom COA for all companies?

**PARTIAL — yes for the model, no for per-company artifacts.**

- 3 group co. cleanroom specs exist (BEI, BKI, III) but were never applied to live Frappe.
- 49 store companies share one derived 114-account template (the de-facto cleanroom for stores).
- **6 companies have NO cleanroom artifact AND no live state:** BFC, BFI2, ROA, SMM, SMMM, SMS.

**Count:** 52 of 58 covered by SOME cleanroom or applied template; **6 are uncovered**.

### 2. Is the same COA set in Frappe?

**NO — only 6 of 58 are healthy.**

- 6 HEALTHY (Frappe matches expected template).
- 46 PARTIAL (template applied but 1-3 critical fields unset, mostly `default_inventory_account`).
- 4 MINIMAL (template was supposed to be applied but the seed run skipped them).
- 2 MISSING (companies created post-seeding, never populated).

**Count:** **6 of 58 fully aligned. 52 need work.**

### 3. Are they the same everywhere?

**NO — two dialects coexist in production, with a delta of 22 BLOCKER and 62 WARNING naming classes.**

- Store companies (49): consistent with each other on the ERPNext 114-account template.
- Apex group entities (BEI, BKI, III): flat-tree, UPPER-case, number-prefixed — a completely different dialect that will create duplicate GL accounts on QBO import.
- Stubs and empties (6): do not match anything.

**Delta:** 22 BLOCKER + 62 WARNING naming classes across 58 companies. 9 companies (BEI, BKI, III, BFC, BFI2, ROA, SMM, SMMM, SMS) cannot migrate to QBO without structural work.

---

## Recommended Action Plan

### Phase A — Standardize the 45 sync-able companies (1-2 days, low risk)

**Goal:** Bring the 45 PARTIAL store companies + ROBDA + XMM to HEALTHY by closing the `default_inventory_account` gap. After this, 51 of 58 companies are QBO-ready.

| Step | Action | Companies | File / Script |
|---|---|---|---|
| A1 | Bulk-create `Stock In Hand - <ABBR>` leaf under Current Assets group per company; bind to `tabCompany.default_inventory_account` | All 45 SYNC companies (ARGW, AYEVO, AFT, AMM, AYSOL, UPTC, BFH, CTTM, DVCAL, EGC, FMA, L77, LCT, PTX, MPD, VGC, NAIA, ESM, ROBGS, ROBGT, ROBIM, ROBDA, SMBIC, SMCAL, SMCLK, SMEO, SMGC, SMMOA, SMMAR, SMNE, SMPUL, SJDM, SMSDN, SMSTR, SMTZ, SMTAY, SMV, SLGM, TGR, TTA, UMBGC, VMTAG, XMM) | New: `scripts/coa_fix/A1_seed_default_inventory.py` |
| A2 | Set `tabCompany.stock_received_but_not_billed` for L77 (point to existing `Stock Received But Not Billed - L77` Liability leaf) | L77 | Same script |
| A3 | Delete duplicate `ROUND OFF` (Liability root) accounts; keep canonical `Round Off` (Expense) | ROBDA, XMM | New: `scripts/coa_fix/A3_dedupe_round_off.py` |
| A4 | Re-extract the 6 HEALTHY companies COA from live Frappe -> write back to `data/_FINAL/COA_HEALTHY_REFERENCE.csv` as the de-facto store template SSOT | AYVER, BMI2, BDV, BAG, SMK, GHO | New: `scripts/coa_fix/A4_extract_healthy_template.py` |

**Acceptance:** 51 companies (6 already healthy + 45 fixed) report HEALTHY on re-run of `frappe_state.md` audit.

### Phase B — Fill the 6 hard gaps (3-5 days, medium risk)

**Goal:** Decide and execute on the 9 QBO-blocked companies. Splits into 3 sub-decisions.

**B1 — Decide BFC + BFI2 (1 day):** are these going live in QBO?
- If YES: seed BFI2 from BMI2 ERPNext template (114 accts); seed BFC from III/holdco pattern (114 accts).
- If NO: set `tabCompany.disabled = 1` on both. Bridge skips them.

**B2 — Rebuild the 4 stub stores (1 day):** apply the same 114-acct store template that the 49 healthy/partial stores got.
- Companies: ROA (Robinsons Antipolo), SMM (SM Manila), SMMM (SM Megamall), SMS (SM Southmall).
- Script: clone `scripts/canonical/migrate_49_stores.py` pattern, target only these 4.
- Acceptance: ROA, SMM, SMMM, SMS report HEALTHY post-run.

**B3 — Normalize the 3 Apex-dialect parents (2-3 days, the hard one):** BEI, BKI, III.
- Pre-work: extract current account list per company. Diff against `CHART_OF_ACCOUNTS_ERP_COA_2025-12-23.csv` (217-acct cleanroom).
- Decision required from Sam + Denise + Bridge: do we (a) re-parent in place (preserve account_name, change parent_account -> nested), (b) rename + re-parent (Title-case + nested) to fully match the store dialect, or (c) leave BEI/BKI/III as Apex in Frappe but transform during QBO export?
- Recommended: **option (c) — transformation layer in the QBO export script**. This avoids touching live GL entries on BEI/BKI/III (highest-volume companies, biggest blast radius). The 217-cleanroom serves as the QBO target spec, not as a live Frappe rewrite.
- Acceptance: a `tmp/coa_audit/qbo_export_BEI.csv` (and BKI, III) where every account is nested + Title-case + maps 1:1 onto the 217-cleanroom + collides with NO store-COA account name.

### Phase C — QBO Setup Handoff to Bridge (1 day, gating Phase B completion)

**Goal:** Deliver Bridge a single-source consolidated COA export they can import directly.

| Step | Deliverable | Format |
|---|---|---|
| C1 | Per-company COA export from live Frappe (58 files, ZIP) | CSV per company, QBO-compatible columns: AccountName, AccountType, DetailType, ParentAccount, AccountNumber |
| C2 | Master reconciliation sheet — every account stem across 58 companies + chosen canonical form + count of variants reconciled | XLSX |
| C3 | Validation report — BEI/BKI/III pre-export vs post-transformation diff; confirm zero account-name collisions across companies | MD |
| C4 | Sign-off package: Sam approves canonical names for the 5 BLOCKER classes (Round Off, AR, AP, VAT Input, top-of-tree under each root) | DOCX |

**Acceptance:** Bridge imports the package into QBO sandbox; zero duplicate-name errors; account counts per company match Frappe +/-5 (allowing for QBO Detail Type roll-ups).

---

## Decision Required From You

Before Phase B can start, I need three calls from you:

1. **BFC and BFI2 — go-live or deactivate?** They were created 2026-05-02 and have 0 accounts. Bridge cannot start QBO setup for them. If they are real entities for the franchise rollout, we seed; otherwise we set `disabled = 1`.

2. **BEI / BKI / III normalization strategy — (a) rewrite live Frappe COA, (b) keep Apex in Frappe + transform at QBO export.** I recommend (b) because it avoids touching live GL on the three highest-volume companies. But if Denise wants Frappe and QBO to mirror each other long-term, we have to do (a) and absorb the GL-rewrite risk.

3. **The 4 stub stores (ROA, SMM, SMMM, SMS) — confirm they go live as separate BEI-parented companies in QBO**, not absorbed back into BEI itself. The store template seeding skipped them on 2026-03-03; we need to know whether to seed them now or roll them up into BEI before QBO import.

Once those three are answered, Phase A can start in parallel (it is safe and reversible) and Phase B can sequence as a 3-5 day sprint.