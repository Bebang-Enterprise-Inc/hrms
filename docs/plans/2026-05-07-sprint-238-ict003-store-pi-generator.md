---
sprint_id: S238
sprint_title: ICT-003 Store-Side Purchase Invoice Generator
plan_branch: s238-ict003-store-pi-generator
status: PLANNED_AUDITED_v2_1
version: 2.1
created_date: 2026-05-07
revised_date: 2026-05-07
audit_pr: 729
prior_amendment_pr: 730
amendment_branch: s238-ict003-pi-generator-amendment-v2-1
canonical_scope: in
canonical_model_reference: docs/STORE_COMPANY_CANONICAL.md
canonical_preflight: required
depends_on: none
supersedes: docs/plans/2026-05-05-sprint-236-intercompany-auto-trade.md
evidence_committed:
  - output/s238/SUMMARY.md
  - output/s238/verification/before_state.json
  - output/s238/verification/after_state.json
  - output/s238/verification/aranetatrial_pi.json
  - output/s238/verification/historical_si_regression.json
  - output/s238/verification/canonical_post_check.log
evidence_transient:
  - tmp/s238/probe_*.py
  - tmp/s238/probe_*.json
  - tmp/s238/seed_dry_run_*.log
sprint_registry_row: |
  | `S238` | Sprint 238 | `s238-ict003-store-pi-generator` | #729 (v1) + #730 (v2) + v2.1 PR pending | PLANNED_AUDITED_v2_1 2026-05-07 — ICT-003 Store-Side PI Generator (~57 units, 11 v1 CRITs + 4 v2 CRITs fixed) | `docs/plans/2026-05-07-sprint-238-ict003-store-pi-generator.md` |
---

# S238 — ICT-003 Store-Side Purchase Invoice Generator (v2.1 — Re-Audited)

> **Canonical model reference:** `docs/STORE_COMPANY_CANONICAL.md`
> **Supersedes:** `docs/plans/2026-05-05-sprint-236-intercompany-auto-trade.md` (S236 v2 — wrong architecture, see Design Rationale).

---

## v2 → v2.1 Re-Audit Amendments (2026-05-07)

`/audit-plan-bei-erp` ran a SECOND pass on v2 (PR #730 merged at SHA `9392b1d09`). 5 parallel auditors verified all 11 v1 CRIT fixes were correctly applied — but **2 NEW architectural CRITs were introduced by v2's mirror logic** + 2 minor text-drift CRITs. Full report: `output/plan-audit/s238-v2-amendment-audit/AUDIT_SUMMARY.md`.

**v2.1 applies the 4 NEW CRIT fixes WITHOUT changing scope.** The architectural pattern (hook on `Sales Invoice on_submit` → separate Draft PI on per-store books, `is_internal_*=0` everywhere, no canonical changes, no S206 collision) is preserved exactly.

### NEW CRITICAL fixes applied (4)

| # | v2 Bug | v2.1 Fix |
|---|---|---|
| **CRIT-1** | `pi.bei_legal_entity = si.bei_legal_entity` mirrored BKI's legal entity onto a per-store-Co PI → triggers production **P10-D04 server script** (`p10_d04_legal_entity_issuance_guard.py:25-32` deployed on Purchase Invoice) which throws `"Legal Entity must match Company for issuance"`. Same failure mode as **S203 incident hrms#610** (2026-04-17), this time on PI side. | Phase 3-T1 code skeleton: `pi.bei_legal_entity = buyer_company` (NOT `si.bei_legal_entity`). Matches existing pattern at `erp_sync.py:2045, 2112`. `pi.bei_store_label` mirror is fine — store label is the same on both sides. |
| **CRIT-2** | `pi_item.cost_center = si_item.cost_center` mirrored BKI's cost_center onto per-store-Co PI items → ERPNext rejects (`Cost Center.company == doc.company` validation). 3-way confirmed by code-verifier + frappe-backend + ph-finance. **Worse**: savepoint silently swallows error → 0 PIs ever created, hook "works" but produces nothing. | NEW helper `_resolve_per_store_cost_center(buyer_company, buyer_warehouse)` reading `Warehouse.custom_cost_center` (pattern from `store.py:5276-5281`) with fallback to `Company.cost_center`. `_mirror_items` calls helper instead of mirroring SI's value. |
| **CRIT-3** | Phase 3-T5 verify text says "All 5 must pass" but v2 expanded unit tests to 8 (Test 6 cancel cascade, Test 7 EWT filter, Test 8 has_field guard). Silent skip if 5/8 pass. | Phase 3-T5: "All 8 must pass". |
| **CRIT-4** | Test Data Seeding Contract section still references `Stock in Hand` parent group (the v1 wrong-name) — directly contradicts B5 fix elsewhere. Authoritative-section drift would mislead executing agent. | Test Data Seeding Contract section: replace `Stock in Hand` reference with dynamic per-store parent group lookup, consistent with B5. |

### Top WARNINGs applied

- **W2 try/except on cascade**: `cascade_cancel_store_pi` wrapped in try/except per S168 reference pattern (`commissary.py:1317-1353`). On PI cleanup failure: log error, allow SI cancel to complete (fail-soft, not fail-hard).
- **W3 silent-skip log**: generator's "Customer is not a per-store Company" exit path now emits a Sentry breadcrumb so the 251/839 SIs that don't match any Company are visible (vs. silently swallowed).
- **W4 verify-script contradiction**: Phase 3 verify script's `auto_submit_store_pi` MUST_CONTAIN replaced with `MUST_NOT_CONTAIN` (B11 removed the toggle).
- **W7 has_field guards on S192/S203 fields**: `pi.bei_legal_entity` and `pi.bei_store_label` assignments wrapped in `if frappe.get_meta("Purchase Invoice").has_field(...)` (matches `erp_sync.py:2044-2047` pattern).
- **W9 scheduler registration**: `scripts/s238/check_si_pi_pairing.py` registered as Frappe `scheduler_event.weekly` in `hrms/hooks.py` (vs. manual run).

### Production prerequisite (W1 — Sam-action)

`BEI Settings.bki_sales_naming_series` is currently **NULL** in production. Phase 0-T4 HARD STOP triggers immediately. **BEFORE execute kickoff:** Sam confirms with Finance the BIR-registered naming series prefix and sets the value via Frappe Desk OR via `/frappe-bulk-edits`. Documented in Phase 0-T0 (NEW pre-flight task).

### Stale claims fixed

- Plan's reference to `billing.py:1472` and `erp_sync.py:2146` as "raw SQL pattern" — corrected to cite `commissary.py:879` only (the other two use `frappe.db.rollback(save_point=)` Pattern B, not raw SQL Pattern A).
- 839 historical SI breakdown clarified: 560 Submitted + 49 Draft + 230 Cancelled. Q1 Input VAT recovery applies to 560 Submitted only (~PHP 1.58M aggregate per ph-finance W11), not all 839.
- 251 of 839 SIs have non-matching Customer.name (W10) — closeout SUMMARY language updated.

### One v1 finding REFUTED — re-confirmed in v2 audit

PH Finance v1 CRIT-6 (BKI Title Case casing) was refuted in v1 + re-refuted in v2 audit. **3-way confirmed** by system-arch + code-verifier + frappe-backend production probe (560 SI rows where `company='BEBANG KITCHEN INC.'` uppercase). Plan's filter is correct. **No v2.1 change.**

### Phase budget impact

| Phase | v2 | v2.1 | Δ rationale |
|---|---:|---:|---|
| Phase 0 — Boot + state probe | 6 | 7 | +1: NEW Phase 0-T0 pre-flight check `bki_sales_naming_series` set (Sam-action prerequisite) |
| Phase 1 — Account seeder | 7 | 7 | unchanged |
| Phase 2 — Supplier + Custom Field + Toggle | 5 | 5 | unchanged |
| Phase 3 — PI generator implementation | 14 | 16 | +2: NEW `_resolve_per_store_cost_center` helper (CRIT-2), correct `bei_legal_entity` (CRIT-1), `has_field` guards (W7), try/except on cascade (W2), silent-skip log (W3), verify-script MUST_NOT_CONTAIN flip (W4) |
| Phase 4 — local-frappe trial | 8 | 8 | unchanged |
| Phase 5 — 5-store regression + S206 sanity | 5 | 5 | unchanged |
| Phase 6 — Closeout | 5 | 6 | +1: drift-detection script registered as scheduler_event (W9) |
| **Total** | **50** | **57** | **+7 units** |

57 units — well under 80-unit ceiling. No phase exceeds 16 units. Single-session executable.

---

## v1 → v2 Audit Amendments (2026-05-07)

`/audit-plan-bei-erp` ran 5 parallel auditors (frappe-backend, ph-finance, deployment-qa, system-arch, code-verifier) on v1 (PR #729, merged at SHA `c1920c9ec`). Verdict: architecturally sound, but 11 CRITICAL implementation-detail bugs + ~14 WARNINGs. Full report: `output/plan-audit/s238-ict003-store-pi-generator/AUDIT_SUMMARY.md`.

**v2 applies the audit fixes WITHOUT changing scope.** The architectural pattern (hook on `Sales Invoice on_submit` → separate Draft PI on per-store books, `is_internal_*=0` everywhere, no canonical changes, no S206 collision) is preserved exactly. The amendments are mechanical bug fixes within that scope.

### CRITICAL fixes applied (11)

| # | Audit blocker | v2 fix |
|---|---|---|
| **B1** | `frappe.db.rollback_to_savepoint()` doesn't exist in this Frappe build (showstopper — would crash production on first failure path) | Phase 3-T1 code skeleton replaced with `frappe.db.sql("ROLLBACK TO SAVEPOINT s238_pi_gen")`. Pattern matches existing `commissary.py:879`, `billing.py:1472`, `erp_sync.py:2146`. |
| **B2** | Missing `pi.set_warehouse` for `update_stock=1` — ARANETA trial fails immediately on "Warehouse is mandatory" | `build_store_pi` resolves per-store warehouse via `resolve_warehouse_company` and sets `pi.set_warehouse`. Per canonical model, Warehouse.docname == Company.name == buyer_company, so direct assignment works. |
| **B3** | No `Sales Invoice on_cancel` cascade — orphan Draft PIs forever (4-way confirmed across deployment-qa, frappe-backend, system-arch, code-verifier) | NEW `cascade_cancel_store_pi` function in generator module + new `Sales Invoice on_cancel` hook in hooks.py. Reference pattern: `commissary.py:1317-1353` (S168's `_delete_orphan_draft_si_on_se_cancel`). |
| **B4** | Account resolution `LIKE %name%` silently picks wrong account on duplicate matches | Replace with EXACT-match by `account_number` (numbered prefix per BEI CoA convention). Seed scripts assign deterministic numbers; resolver looks up by number. |
| **B5** | Plan's parent group `Stock in Hand` doesn't exist in production CoA — actual is `Stock Assets - <ABBR>` (per code-verifier production probe of ARANETA / AYALA EVO / SM TANZA) | Phase 0-T4 expands to survey ALL 49 per-store CoA parent groups and write to `before_state.json`. Phase 1-T1 seed script uses dynamic parent-group lookup via `_find_parent_group()` pattern from `s206_seed_intercompany_accounts.py:82`. |
| **B6** | Stale ICT-008 reference: plan said `4000003 SALES — BKI TO STORES`; actual production = `4000210 - DELIVERIES - BKI` | Plan updated. DECISIONS.md ICT-008 amendment is OUT OF SCOPE for this sprint (separate doc fix); flagged in closeout SUMMARY as a follow-up data-fix. |
| **B7** | `bill_no=si.name` may not be BIR-authorized if `bki_sales_naming_series` unset | Phase 0-T4 verifies `BEI Settings.bki_sales_naming_series` is set; HARD STOP if not. Generator additionally guards: only fires when `si.naming_series` matches the BIR-authorized series. |
| **B8** | `posting_time` not mirrored + Denise can edit `posting_date` during Draft review → SLE timestamp drift + PFRS 15 period-match break | `build_store_pi` sets `pi.set_posting_time=1, pi.posting_time=si.posting_time`. NEW: validate hook on Purchase Invoice rejects `posting_date` edits when `bki_si_reference` is set (plus `read_only=1` on the field for non-Administrator users). |
| **B9** | Tax row construction unspecified — VAT mismatch risk in BIR cross-checks | Phase 3-T3 expanded with explicit pseudocode: iterate `si.taxes`, filter to `account_head LIKE 'Output VAT%'` only (skip EWT-deduct rows), set `charge_type='Actual'`, mirror `tax_amount`, map to per-store Input VAT account. |
| **B10** | `pi.cost_center` not set — per-store P&L attribution lost | Mirror `si.items[i].cost_center` to `pi.items[i].cost_center` per line. Reuse `_resolve_store_cost_center` from `commissary.py:1166-1172` if SI line lacks cost_center. |
| **B11** | `auto_submit_store_pi=1` transaction race — books split if PI submit fails inside SI's on_submit chain | v2 EXCLUDES the `auto_submit_store_pi` toggle entirely from Phase 2 install. Default = always create as Draft. Auto-submit deferred to a future sprint with proper queued-job design (out of scope for v1 ship). |

### High-priority WARNINGs applied

- Strike `(or production)` from Phase 4-T2; trial locked to local-frappe ONLY.
- Phase 6 declares deploy mode `skip_build=false, no_cache=true` (MEMORY lesson #2).
- `build_store_pi` ALSO sets `pi.inter_company_invoice_reference = si.name` so existing G-046 dashboard at `procurement.py:4707/4731/4765` keeps reporting correctly.
- NEW Phase 6-T6: post-merge L1 smoke check (one real BKI SI, verify Draft PI auto-creates).
- NEW `scripts/s238/check_si_pi_pairing.py` — weekly reconciliation report finding SIs without paired PIs (catches silent hook failures).
- Generator guards with `frappe.get_meta("Purchase Invoice").has_field("bki_si_reference")` to prevent firing during the deployment window before the Custom Field installs.
- Mirror `pi.bei_legal_entity` and `pi.bei_store_label` from SI (S192/S203 server-side guards).
- Standardize on `companies` (lowercase fieldname) in code; "Allowed To Transact With" only in prose/labels.
- Closeout SUMMARY surfaces 839 historical SIs Q1 2026 Input VAT recovery (~6-7 figures across 49 entities) as a follow-up sprint candidate.

### One audit finding REFUTED

PH Finance flagged BKI Company casing as CRIT-6. **Refuted** by system-arch + code-verifier with production evidence (`tmp/pi_probe.json`, `s206_seed_intercompany_accounts.py:82`, `STORE_COMPANY_CANONICAL.md:172`). Actual `tabCompany.name` IS uppercase `"BEBANG KITCHEN INC."`. Plan's `if doc.company != "BEBANG KITCHEN INC."` filter is correct. **No v2 change needed.**

### Phase budget impact

| Phase | v1 | v2 |
|---|---:|---:|
| Phase 0 — Boot + state probe | 4 | 6 (+2: full 49-store CoA survey, naming series check) |
| Phase 1 — Account seeder | 5 | 7 (+2: dynamic parent-group lookup, account_number prefix) |
| Phase 2 — Supplier + Custom Field + Toggle | 5 | 5 (unchanged: drop auto_submit toggle = 1u saved; add validate hook for posting_date = 1u added) |
| Phase 3 — PI generator implementation | 10 | 14 (+4: on_cancel cascade fn + hook, posting_time mirror, cost_center mirror, has_field guard, IC ref dual-set, tax row spec, savepoint API fix) |
| Phase 4 — ARANETA trial (local-frappe only) | 8 | 8 (unchanged) |
| Phase 5 — 5-store regression + S206 sanity | 5 | 5 (unchanged) |
| Phase 6 — Closeout | 3 | 5 (+2: post-merge smoke, deploy mode, 839-SI follow-up note) |
| **Total** | **40** | **50** |

50 units — well under 80 ceiling, single-session executable.

---

## Design Rationale (For Cold-Start Agents)

### Why this exists

Audit 2026-05-05 + 2026-05-07 found a clear implementation gap:

- ICT-003 (CFO Butch Formoso, 2026-02-20, still binding): "BKI issues Sales Invoice (SI) and BEI receives Purchase Invoice (PI) for each hub transfer. Both documents required since separate legal entities."
- Built today: **BKI's SI side works** (839 SIs, ICT-001/002/007 all wired via `commissary.py:build_bki_store_sale_invoice`).
- Missing today: **the store-side PI was never built.** Stores have 0 PI from BKI in the entire production database. Each per-store BIR Form 2550Q is missing the Input VAT claim from BKI purchases; each store's books of accounts is missing AP-BKI + Inventory-from-Commissary entries.

This sprint closes the gap: when an SI on BKI's books submits, a **separate Draft Purchase Invoice** is auto-generated on the receiving store's books, ready for review + submission by Denise's team.

### Why this is NOT S236 v2 (the wrong path)

S236 v2 tried to use ERPNext's atomic auto-mirror feature (`Make Inter Company Invoice` button) which would have flipped 49 billing Customers to `is_internal_customer=1`. Audit found:
- **Violates ICT-001** — the Customer flag stays at 0 because stores ARE separate legal entities (per `commissary.py:1137` + `billing.py:595` hardcoded `si.is_internal_customer = 0` with comment "EXTERNAL sale per ICT-001").
- **Violates ICT-003** — the auto-mirror creates an *atomic two-company transaction* which conflates legal independence; Butch said "both documents required" precisely because they should be SEPARATE.
- **Would silently break S206** — `labor_allocation.py:324-339` looks up Internal Customers by `{represents_company, is_internal=1}` with no name-suffix filter; flipping billing Customers makes that lookup ambiguous.

S236 v2's framing of "consolidated group vs arm's-length" was a false dichotomy. BEI is BOTH:
- Legally arm's-length (49 + 1 separate BIR-registered corporations) → each entity needs its own complete books per ICT-003
- Operationally one accounting team (Denise's team manages all 50 sets in-house) → centralized review + submission workflow

The right architecture is **separate documents** on separate Companies, with **operational pairing** via a backend hook, NOT atomic auto-mirroring.

### Architecture summary

When `Sales Invoice on_submit` fires AND `company == BEBANG KITCHEN INC.` AND `customer` matches a per-store billing Customer:

1. Identify the buyer Company (the per-store Company) from the SI's customer name (canonical model: `Customer.name == per-store Company.name`).
2. Look up the per-store CoA: `Inventory-from-Commissary` (Asset), `Input VAT - BKI Inter-Co` (Asset), `AP-Trade-BKI` (Liability) — all numbered per existing BEI CoA convention (`1xxxx`/`2xxxx` series, parent=Stock-in-Hand / Current Liabilities).
3. Construct a **Draft Purchase Invoice** on the buyer Company with:
   - `supplier` = `BEBANG KITCHEN INC. - Trade` (a NEW non-internal Supplier record, `is_internal_supplier=0`, `Allowed To Transact With` = all 49 per-store Companies)
   - `posting_date` = SI's posting_date (per ICT-007 — Incoterm Destination: SI date is the delivery acceptance date)
   - `bill_no` = SI's name (the BKI-side SI)
   - `bill_date` = SI's posting_date
   - Line items mirror SI items (item code, qty, rate including the 2.75%/8% markup already in the SI)
   - Taxes mirror SI's tax breakdown (12% Input VAT lands on store's books per ICT-001)
   - `update_stock=1` so Inventory-from-Commissary increases on the per-store warehouse
   - Custom field `bki_si_reference` linking back to the SI for traceability
4. Insert as Draft (do NOT submit) — Denise's team reviews + submits via Frappe Desk.
5. `is_internal_customer/_supplier` flags ALL stay at 0 (no canonical model rewrite).

### Why use a NEW Supplier record (not the existing `BEBANG KITCHEN INC. (Internal)`)

Audit 2026-05-05 found a Supplier already exists named "Bebang Kitchen Inc." with `is_internal_supplier=1, represents_company=BEBANG KITCHEN INC.`. **That record is for S206 labor cost-sharing JEs, NOT for trade.** Re-using it would conflict with S206 lookup logic. New record:

- `name` (docname): `BEBANG KITCHEN INC. - Trade`
- `supplier_name`: `BEBANG KITCHEN INC.` (display name shown on PI print format — BIR-compliant)
- `is_internal_supplier`: 0
- `represents_company`: NULL (not internal)
- `tax_id`: BKI's TIN (preserved on SI's print format — same TIN as BKI's billing entity)
- `Allowed To Transact With`: 49 per-store Companies + holdco

### Source references

- `data/_CONSOLIDATED/01_FINANCE/DECISIONS.md:193-200` — ICT-001 through ICT-008 (CFO-locked, still binding per 2026-05-07 banner)
- `data/_CONSOLIDATED/01_FINANCE/questionnaires/CFO_INTERCOMPANY_Butch_Formoso_2026-02-20.md:35-42` — Q3 verbatim "we need to maintain the SI and PI for each hub transfer"
- `hrms/api/commissary.py:864-988, 973-1248` — existing `build_bki_store_sale_invoice` (the SI side; UNCHANGED)
- `hrms/api/commissary.py:1137`, `hrms/api/billing.py:595` — `si.is_internal_customer = 0` hardcoded; UNCHANGED
- `hrms/utils/labor_allocation.py:324-339` — S206 Internal Customer lookup; UNCHANGED
- Audit findings: `output/plan-audit/s236-intercompany-auto-trade/AUDIT_SUMMARY.md`, `tmp/CANONICAL_COVERAGE_AUDIT_SUMMARY.md`, `tmp/pi_probe.json`
- S168 SI implementation history: `docs/plans/2026-04-07-sprint-168-bki-store-sale-billing-on-delivery.md`

---

## Canonical Model Preflight (Mandatory)

Executing agent MUST run before the first code change:

```bash
python scripts/verify_canonical_structure.py 2>&1 | tee tmp/s238/canonical_preflight.log
```

If the verifier prints `VIOLATIONS FOUND`, STOP and ask Sam. Post-implementation verifier (Phase 6) MUST also pass.

**Canonical law (this sprint preserves it intact):**
- 49 per-store Companies + Warehouses + billing Customers + S206 Internal Customers — UNCHANGED.
- `is_internal_customer/_supplier` flags — ALL UNCHANGED (no flips).
- `resolve_store_buyer_entity` — UNCHANGED (no resolver changes).
- Existing `BEBANG KITCHEN INC. (Internal)` Supplier (S206) — UNCHANGED.
- `commissary.py:1137`, `billing.py:595` — UNCHANGED.

**Forbidden in this plan:**
- Flipping `is_internal_customer` on any Customer.
- Modifying any existing Supplier record's `is_internal_supplier` flag.
- Modifying `resolve_store_buyer_entity` or any code under `hrms/utils/supply_chain_contracts.py`.
- Modifying `hrms/utils/labor_allocation.py`.
- Modifying canonical Rules in `docs/STORE_COMPANY_CANONICAL.md`.
- Touching the existing 839 historical BKI SIs.
- Modifying `build_bki_store_sale_invoice` in commissary.py.

**Scope claim — what this plan creates / mutates:**
- INSERT 1 Supplier: `BEBANG KITCHEN INC. - Trade` (`is_internal_supplier=0`).
- INSERT 49 entries to `BEBANG KITCHEN INC. - Trade.companies` child table (Allowed To Transact With per-store Companies).
- INSERT 3 GL accounts × 49 stores = 147 accounts under existing per-store parent groups (`Stock Assets - <ABBR>`, `Accounts Payable - <ABBR>` or `Current Liabilities - <ABBR>`, `Current Assets - <ABBR>`) — discovered dynamically per Phase 0-T4 survey (v2-B5 / v2.1-CRIT-4).
- INSERT 1 Custom Field on `Purchase Invoice`: `bki_si_reference` (Link → Sales Invoice, read-only).
- INSERT 1 row in `BEI Settings` (or extend existing settings doc): `enable_bki_store_pi_generator` (toggle, default 1).
- ADD 1 hook in `hrms/hooks.py`: `Sales Invoice on_submit → hrms.api.bki_store_pi_generator.maybe_generate_store_pi`.
- ADD new module `hrms/api/bki_store_pi_generator.py` with the generator logic.

## Canonical Model Binding

This feature binds to the canonical model as follows:

- Reads `Customer.name == warehouse.company == per-store Company.name` to map SI customer → buyer Company.
- Reads `Sales Invoice` doc submitted on BKI's books for the line items + tax breakdown to clone.
- Reads per-store Company's CoA to find the right `Inventory-from-Commissary` / `Input VAT - BKI Inter-Co` / `AP-Trade-BKI` accounts.
- Reads new `BEBANG KITCHEN INC. - Trade` Supplier on each per-store Company's books.
- Writes a Draft Purchase Invoice (docstatus=0) on the per-store Company's books.
- Does NOT touch any Customer, Company, or Warehouse records.
- Does NOT touch the existing S206 Internal Customer or its Supplier counterpart.
- Does NOT call `resolve_store_buyer_entity` or any S206-binding utility.

## Worktree Isolation & Evidence Split

Worktree path: `F:/Dropbox/Projects/BEI-ERP-s238-ict003-pi-generator`

```yaml
evidence_committed:
  - output/s238/SUMMARY.md
  - output/s238/verification/before_state.json
  - output/s238/verification/after_state.json
  - output/s238/verification/aranetatrial_pi.json
  - output/s238/verification/historical_si_regression.json
  - output/s238/verification/canonical_post_check.log
evidence_transient:
  - tmp/s238/probe_*.py
  - tmp/s238/probe_*.json
  - tmp/s238/seed_dry_run_*.log
```

---

## Test Data Seeding Contract (Mandatory per S229)

**Records the scenarios depend on:**
- 49 per-store Companies + Warehouses + billing Customers + S206 Internal Customers — must exist (verified via canonical preflight).
- Existing `BEI Settings.bki_sales_income_account` set per ICT-008 — must exist.
- Per-store CoA must include parent groups dynamically discovered via Phase 0-T4 survey: `Stock Assets - <ABBR>` (for Inventory-from-Commissary leaf), `Accounts Payable - <ABBR>` or `Current Liabilities - <ABBR>` (for AP-Trade-BKI leaf), `Current Assets - <ABBR>` (for Input VAT - BKI Inter-Co leaf). Per-store `<ABBR>` is the CoA suffix per BEI canonical convention. Reference pattern: `_find_parent_group()` in `hrms/on_demand/s206_seed_intercompany_accounts.py:82`. (v2.1-CRIT-4: corrected — v1/v2 incorrectly referenced `Stock in Hand` which does NOT exist in production CoA.)
- 3 NEW GL accounts × 49 stores = 147 accounts (seeded by this sprint).
- 1 NEW `BEBANG KITCHEN INC. - Trade` Supplier with 49 Allowed To Transact With entries (seeded by this sprint).
- 1 NEW Custom Field `bki_si_reference` on `Purchase Invoice` (seeded by this sprint).
- Test SI: created in Phase 4 trial (1 small ARANETA SI, ~PHP 1.00) via existing BKI flow; tracked in teardown ledger.

**Pre-test seeding plan (all idempotent, all use `frappe.db.savepoint`):**
- `scripts/s238/seed_pi_generator_accounts.py --dry-run|--apply` — 147 accounts.
- `scripts/s238/seed_bki_trade_supplier.py --dry-run|--apply` — 1 Supplier + 49 Allowed entries.
- `scripts/s238/install_bki_si_reference_field.py --dry-run|--apply` — 1 Custom Field.

**Teardown plan:**
- Test SI + auto-generated Draft PI: cancel both via Frappe Desk; teardown removes ledger entries.
- Seeded accounts: keep (idempotent, harmless).
- New Supplier: keep (this is the production change).
- New Custom Field: keep (this is the production change).
- Hook in hooks.py: keep (this is the production change).

If sprint is **rolled back**: revert the PR; cancel + delete the new Supplier; remove the Custom Field via `bench remove-from-installed-apps` pattern OR drop the field manually via SQL with savepoint.

**Teardown ledger:** `output/l3/s238/teardown_ledger.json` (per-record before/after).
**Teardown verification:** `output/l3/s238/teardown_complete.json` (closeout).

---

## L3 Workflow Scenarios

| User | Action | Expected Outcome | Failure Means |
|---|---|---|---|
| Administrator | Run `scripts/s238/seed_pi_generator_accounts.py --apply` | 147 accounts created (or already exist), zero errors | Account seed broken |
| Administrator | Run `scripts/s238/seed_bki_trade_supplier.py --apply` | 1 Supplier `BEBANG KITCHEN INC. - Trade` created with `is_internal_supplier=0` and 49 Allowed To Transact With entries | Supplier seed broken |
| Administrator | Run `scripts/s238/install_bki_si_reference_field.py --apply` | 1 Custom Field on Purchase Invoice (`bki_si_reference`, Link → Sales Invoice, read-only) | Custom field install broken |
| Administrator | Submit a real BKI→ARANETA SI via existing `complete_receiving` flow (small amount, ~PHP 1.00) | SI submits successfully on BKI's books. ALSO: 1 Draft PI created on ARANETA's books with `supplier=BEBANG KITCHEN INC. - Trade`, `bill_no=<SI name>`, `bki_si_reference=<SI name>`, `update_stock=1`, posting_date=SI posting_date | Hook didn't fire OR PI generator broken |
| Administrator | Open the auto-generated Draft PI; verify line items match SI; verify tax breakdown shows 12% Input VAT | Items 1:1 match. Tax row shows Input VAT amount that mirrors SI's Output VAT. | Tax/item mirroring broken |
| Denise (or test.finance) | Submit the Draft PI from Frappe Desk | PI submits. SLE created on per-store warehouse with `actual_qty>0`, `valuation_rate=<from PI>`. GL Entry rows: DR Inventory-from-Commissary, DR Input VAT - BKI Inter-Co, CR AP-Trade-BKI (with `party_type=Supplier, party=BEBANG KITCHEN INC. - Trade` per DM-1) | Stock or GL recognition broken |
| test.area@bebang.ph | Open per-store P&L for ARANETA via `Profit and Loss Statement` report | COGS-from-Commissary line shows non-zero value (after the inventory is consumed via POS / Stock Entry — note: PI alone increases Inventory, not COGS; COGS recognition happens at POS/consumption time) | P&L wiring broken |
| Administrator | Sample 5 random PRE-S238 historical SIs (ACC-SINV-2026-00100, 00300, 00500, 00700, 00900) | All 5 readable, customer field unchanged, `bki_si_reference` does NOT appear (Custom Field is forward-only on the PI side; SI is unchanged) | Path B regression on historical |
| Administrator | Submit a NEW BKI SI to a DIFFERENT store (e.g. SM TANZA, 5 random stores) | All 5 produce a Draft PI on each respective store's books with correct supplier + accounts | Cross-store regression |
| test.scm@bebang.ph | Run S206 labor JE creation for one store (existing flow) | S206 labor JE creates against the existing `(Internal)` Customer (UNTOUCHED). `BEBANG KITCHEN INC. - Trade` Supplier is NOT involved. | Resolver / S206 broke |
| Administrator | Cancel the test SI from earlier | SI cancels. The matching Draft PI: option 1 — auto-cancels via cascade hook; option 2 — flagged as `cancellation_pending` for manual cancel by Denise. (Decision: auto-cancel if Draft, flag if Submitted.) | Cancel cascade broken |
| Administrator | Run `python scripts/verify_canonical_structure.py` post-implementation | `ALL CANONICAL` (zero new violations) | Canonical drift introduced |
| Administrator | Disable the toggle: `BEI Settings.enable_bki_store_pi_generator=0`; submit another BKI SI | NO PI auto-generated. SI submits cleanly. | Toggle broken (kill switch) |

**Evidence files contract:**
```
output/l3/s238/form_submissions.json
output/l3/s238/api_mutations.json
output/l3/s238/state_verification.json
output/l3/s238/teardown_ledger.json
output/l3/s238/teardown_complete.json
output/l3/s238/historical_si_regression.json
```

**Failure Response (mandatory):**
- **Mode A (app/Frappe bug):** hook fires but PI not created / GL Entry missing party fields. File `[BUG] s238 — <symptom>`. Halt sprint.
- **Mode B (test/data bug):** account names mismatched, Custom Field SQL malformed, supplier collision. Fix the migration script.
- **Mode C (brittleness):** intermittent timing on hook firing. Fix LIBRARY wait helpers. No `waitForTimeout` masking.

---

## Phases

### Phase 0 — Boot, Worktree Spawn, Pre-State Probe (7 units — v2.1)

**0-T0 (v2.1 NEW — Sam-action prerequisite, BEFORE execute kickoff)** **HARD BLOCKER:** verify `BEI Settings.bki_sales_naming_series` has a non-empty BIR-registered value via SSM probe:
```bash
docker exec $BACKEND psql ... -c "SELECT bki_sales_naming_series FROM \`tabBEI Settings\`;"
```
If NULL/empty, **STOP and ask Sam** — Sam confirms with Finance the BIR-authorized prefix and sets the value via Frappe Desk OR `/frappe-bulk-edits` BEFORE proceeding. (The v2 audit found this NULL in production; if not pre-set, Phase 0-T4 HARD STOP triggers anyway.)

**0-T1** Read this plan fully (v2.1 amendment section MUST be read; CRIT-1 + CRIT-2 fixes are non-obvious from v2 alone).

**0-T2** Spawn HRMS worktree (already done at plan creation; confirm):
```bash
cd F:/Dropbox/Projects/BEI-ERP-s238-ict003-pi-generator
git status --short    # must be clean other than this plan + registry
mkdir -p tmp/s238 output/s238/verification output/l3/s238
git rev-parse origin/production > tmp/s238/remote_truth_baseline_hrms.sha
```

**0-T3** Run canonical preflight + capture baseline:
```bash
python scripts/verify_canonical_structure.py 2>&1 | tee tmp/s238/canonical_preflight.log
```
If violations, STOP.

**0-T4 (v2)** Probe production state via SSM — write `output/s238/verification/before_state.json` with:
- BKI SI total count + sample of latest 5 SI naming_series values
- PI count where company in (49 per-store Cos) AND supplier matches BKI pattern (expected: 0)
- Existing Suppliers matching `BEBANG KITCHEN%` pattern (verify ONLY the S206 internal one exists, no Trade variant yet)
- Existence of `bki_si_reference` Custom Field on Purchase Invoice (expected: false)
- Existence of `enable_bki_store_pi_generator` setting (expected: false)
- `BEI Settings.bki_sales_income_account` value (HARD STOP if unset — ICT-008 prerequisite per audit B6)
- **v2-B7**: `BEI Settings.bki_sales_naming_series` value (HARD STOP if unset — BIR-authorized series prerequisite per audit B7)
- **v2-B5**: per-store CoA structure for ALL 49 per-store Companies — list each Company's parent groups for `Stock Assets - <ABBR>`, the appropriate Liability parent (`Current Liabilities - <ABBR>` or equivalent), and `Current Assets - <ABBR>` (for Input VAT). Discover each store's `<ABBR>` via existing leaf account suffix pattern (reuse `s206_seed_intercompany_accounts._find_parent_group()` pattern).
- **v2-B6**: read actual `bki_sales_income_account` value and confirm it matches production (currently `4000210 - DELIVERIES - BKI`, NOT the `4000003` referenced in stale DECISIONS.md ICT-008 row — that doc fix is OUT OF SCOPE for this sprint).

**MUST_MODIFY:** `output/s238/verification/before_state.json`
**MUST_CONTAIN:** `"bki_si_total"`, `"existing_bki_supplier_count"`, `"bki_trade_supplier_exists"`, `"custom_field_exists"`, `"bki_sales_income_account"`, `"bki_sales_naming_series"`, `"per_store_coa_parent_groups"` (dict of 49 stores × 3 parent group names), `"bki_sales_income_account_value"`

**Phase 0 verify (v2):**
```python
import os, json, sys
errs = []
for f in ["tmp/s238/canonical_preflight.log", "output/s238/verification/before_state.json"]:
    if not os.path.exists(f): errs.append(f"MISSING: {f}")
log = open("tmp/s238/canonical_preflight.log", encoding="utf-8", errors="replace").read()
if "VIOLATIONS FOUND" in log: errs.append("Canonical preflight violations")
if os.path.exists("output/s238/verification/before_state.json"):
    s = json.load(open("output/s238/verification/before_state.json"))
    if s.get("bki_trade_supplier_exists") is True:
        errs.append("BKI Trade Supplier already exists — investigate before seeding")
    if not s.get("bki_sales_income_account"):
        errs.append("BEI Settings.bki_sales_income_account not set — ICT-008 prerequisite missing, STOP")
    # v2-B7: BIR-authorized naming series prerequisite
    if not s.get("bki_sales_naming_series"):
        errs.append("BEI Settings.bki_sales_naming_series not set — BIR series prerequisite missing, STOP")
    # v2-B5: every store must have all 3 parent groups identified
    cga = s.get("per_store_coa_parent_groups") or {}
    if len(cga) != 49:
        errs.append(f"Expected 49 per-store CoA surveys, got {len(cga)}")
    for store, groups in cga.items():
        for need in ("stock_assets_parent", "ap_parent", "current_assets_parent"):
            if not groups.get(need):
                errs.append(f"{store}: missing parent group key '{need}'")
print("PASS" if not errs else "\n".join(errs))
sys.exit(0 if not errs else 1)
```

---

### Phase 1 — GL Account Seeder (5 units)

**1-T1 (v2)** Write `scripts/s238/seed_pi_generator_accounts.py` (NEW):
- For each per-store Company (49), seed 3 accounts with **deterministic account_number prefixes** (v2-B4 — exact-match resolver depends on these numbers):
  - **`1104210 Inventory-from-Commissary`** — under `Stock Assets - <ABBR>` parent (v2-B5 — actual production parent group, NOT `Stock in Hand`), account_type=`Stock`, root_type=Asset, report_type=Balance Sheet
  - **`1106210 Input VAT - BKI Inter-Co`** — under `Current Assets - <ABBR>` (or VAT-input parent if exists), account_type=`Tax`, root_type=Asset, report_type=Balance Sheet
  - **`2103210 AP-Trade-BKI`** — under `Accounts Payable - <ABBR>` (preferred) or `Current Liabilities - <ABBR>`, account_type=`Payable`, root_type=Liability, report_type=Balance Sheet
- v2-B5: Per-store `<ABBR>` discovered from `before_state.json` `per_store_coa_parent_groups` survey (Phase 0-T4). Reuse `_find_parent_group()` pattern from `hrms/on_demand/s206_seed_intercompany_accounts.py:82` so the seed script handles per-store CoA divergence dynamically.
- v2-B1 (savepoint API): use `frappe.db.savepoint("s238_seed_<co_safe>")` for entry, and on exception use raw SQL `frappe.db.sql("ROLLBACK TO SAVEPOINT s238_seed_<co_safe>")` (NOT `rollback_to_savepoint` — does not exist).
- `--dry-run` (default) and `--apply` modes.
- Idempotent: skip if account_number already exists for the Company.
- All accounts logged to `output/l3/s238/teardown_ledger.json`.

**MUST_MODIFY:** `scripts/s238/seed_pi_generator_accounts.py` (NEW)
**MUST_CONTAIN:** `frappe.db.savepoint`, `ROLLBACK TO SAVEPOINT`, `1104210`, `1106210`, `2103210`, `Stock Assets`, `_find_parent_group`, `--dry-run`, `--apply`

**1-T2 (v2)** Dry-run on production via SSM, capture log to `tmp/s238/seed_dry_run_accounts.log`. Verify parent_account assignments are correct for each per-store CoA per the Phase 0-T4 survey. If any store has missing parent groups (some stores may not have all 3 of `Stock Assets`, `Accounts Payable`, `Current Assets`), STOP — Phase 0-T4 should have caught this; if it slipped through, ask Sam.

**1-T3** Apply on production. Re-probe. Verify 147 accounts exist (49 × 3) with the right account_numbers (`1104210`, `1106210`, `2103210` per Company).

---

### Phase 2 — Supplier + Custom Field + Toggle (5 units)

**2-T1** Write `scripts/s238/seed_bki_trade_supplier.py` (NEW):
- Create Supplier:
  - `name`: `BEBANG KITCHEN INC. - Trade`
  - `supplier_name`: `BEBANG KITCHEN INC.` (display name on PI print)
  - `is_internal_supplier`: 0
  - `represents_company`: NULL
  - `tax_id`: BKI's TIN (read from existing BKI Customer record's tax_id or BKI Company's tax_id)
  - `supplier_group`: existing default
- Add 49 entries to `companies` child table (`Allowed To Transact With`) — one per per-store Company.
- Idempotent + savepoint + ledger.

**MUST_MODIFY:** `scripts/s238/seed_bki_trade_supplier.py` (NEW)
**MUST_CONTAIN:** `is_internal_supplier`, `represents_company`, `BEBANG KITCHEN INC. - Trade`, `tax_id`, `companies`

**2-T2** Write `scripts/s238/install_bki_si_reference_field.py` (NEW):
- Install Custom Field on `Purchase Invoice`:
  - `fieldname`: `bki_si_reference`
  - `label`: `BKI Sales Invoice Reference`
  - `fieldtype`: Link
  - `options`: Sales Invoice
  - `read_only`: 1
  - `insert_after`: `bill_no`
- Idempotent.

**MUST_MODIFY:** `scripts/s238/install_bki_si_reference_field.py` (NEW)
**MUST_CONTAIN:** `bki_si_reference`, `Link`, `Sales Invoice`, `read_only`

**2-T3 (v2)** Add toggle to BEI Settings (existing single doctype):
- `enable_bki_store_pi_generator` (Check, default 1) — kill switch for the hook.
- ~~`auto_submit_store_pi`~~ — **REMOVED in v2 (audit B11).** Always Draft. Auto-submit deferred to a future queued-job sprint (out of scope here).

Add via `scripts/s238/install_bei_settings_toggles.py` (NEW) OR extend existing settings install script.

**MUST_MODIFY:** `scripts/s238/install_bei_settings_toggles.py` (or amend existing)
**MUST_CONTAIN:** `enable_bki_store_pi_generator`
**MUST_NOT_CONTAIN:** `auto_submit_store_pi` (v2-B11 — explicitly excluded)

**2-T3a (v2-B8)** NEW: install validate hook on Purchase Invoice that locks `posting_date` from edit when `bki_si_reference` is set:

```python
# in hrms/api/bki_store_pi_generator.py — additional validate fn
def lock_posting_date_on_bki_paired_pi(doc, method=None):
    """v2-B8: prevent Denise from editing posting_date on auto-generated PIs.
    The posting_date must equal the SI's posting_date (per ICT-007 + PFRS 15
    period match). Only Administrator may override.
    """
    if not doc.get("bki_si_reference"): return
    if doc.is_new(): return  # initial insert by hook is fine
    if frappe.session.user == "Administrator": return
    db_pd = frappe.db.get_value("Purchase Invoice", doc.name, "posting_date")
    if db_pd and str(doc.posting_date) != str(db_pd):
        frappe.throw(_(
            "S238: posting_date is locked on BKI-paired PIs (must match the "
            "BKI SI's posting_date per ICT-007). Contact Administrator to override."
        ))
```

Register in hooks.py: `Purchase Invoice` → `validate` → list-style append `bki_store_pi_generator.lock_posting_date_on_bki_paired_pi`.

**MUST_CONTAIN (in 2-T3a):** `lock_posting_date_on_bki_paired_pi`, `Purchase Invoice` validate registration in hooks.py

**2-T4** Apply all seeds on production. Verify post-seed state in `output/s238/verification/after_state.json`.

---

### Phase 3 — PI Generator Implementation (10 units)

**3-T1 (v2)** Create `hrms/api/bki_store_pi_generator.py` (NEW):

```python
"""S238 — Generate store-side Draft Purchase Invoice when a BKI Sales Invoice submits.

Implements ICT-003: each BKI→store SI must have a paired PI on the receiving
store's books for BIR per-entity bookkeeping. NOT an atomic auto-mirror — the
PI is a SEPARATE document on a SEPARATE Company, awaiting Denise's team review.

v2: audit fixes B1 (savepoint API), B2 (set_warehouse), B3 (on_cancel),
B4 (account_number resolution), B7 (naming series guard), B8 (posting_time),
B9 (tax mirror), B10 (cost_center mirror), B11 (no auto_submit), W (IC ref
dual-set, has_field guard, S192/S203 fields).
"""
import frappe
from frappe import _
from frappe.utils import flt
from hrms.utils.sentry import set_backend_observability_context

BKI_COMPANY = "BEBANG KITCHEN INC."
BKI_TRADE_SUPPLIER = "BEBANG KITCHEN INC. - Trade"

# Account number prefixes seeded by scripts/s238/seed_pi_generator_accounts.py.
# v2-B4: exact match by account_number, not LIKE %name%.
ACCT_INVENTORY_FROM_COMMISSARY = "1104210"   # Asset, leaf under Stock Assets - <ABBR>
ACCT_INPUT_VAT_BKI_INTERCO    = "1106210"   # Asset (Tax)
ACCT_AP_TRADE_BKI             = "2103210"   # Liability (Payable)

def maybe_generate_store_pi(doc, method=None):
    """S238: Sales Invoice on_submit hook — generates store-side PI."""
    set_backend_observability_context(
        module="billing",
        action="maybe_generate_store_pi",
        mutation_type="create",
        extras={"si_name": doc.name, "company": doc.company, "customer": doc.customer},
    )
    # Filter 1: only BKI -> store SIs trigger the generator
    if doc.company != BKI_COMPANY: return
    # Filter 2 (v2-W has_field guard): skip if Custom Field not installed yet
    if not frappe.get_meta("Purchase Invoice").has_field("bki_si_reference"):
        frappe.log_error(
            "S238: bki_si_reference Custom Field not installed; skipping PI generation",
            "S238 Custom Field Missing",
        )
        return
    settings = frappe.get_single("BEI Settings")
    if not getattr(settings, "enable_bki_store_pi_generator", 1): return
    # Filter 3 (v2-B7): only fire when SI used BIR-authorized series
    bir_series = (getattr(settings, "bki_sales_naming_series", "") or "").strip()
    if bir_series and doc.naming_series and not doc.naming_series.startswith(bir_series.split(".")[0]):
        return
    # Identify buyer Company (per canonical: Customer.name == per-store Company.name)
    buyer_company = doc.customer if frappe.db.exists("Company", doc.customer) else None
    if not buyer_company:
        # v2.1-W3: log silent skip via Sentry breadcrumb so non-matching customers
        # are visible (251/839 historical SIs hit this path; helps diagnose
        # walk-in / holdco / other non-store customers).
        try:
            sentry_sdk.add_breadcrumb(
                category="s238.pi_generator",
                message=f"Skipped SI {doc.name}: customer '{doc.customer}' is not a per-store Company",
                level="info",
            )
        except Exception:
            pass
        return  # Customer is not a per-store Company; ignore
    # Idempotency: skip if a PI already exists referencing this SI
    if frappe.db.exists("Purchase Invoice", {"bki_si_reference": doc.name}): return
    sp_name = "s238_pi_gen"
    try:
        frappe.db.savepoint(sp_name)
        pi = build_store_pi(doc, buyer_company)
        pi.insert(ignore_permissions=True)
        # v2-B11: auto_submit_store_pi is REMOVED from this version. Always Draft.
        # Future auto-submit will be a separate queued-job sprint.
        # v2-B1: this Frappe build does NOT have rollback_to_savepoint() method.
        # Use raw SQL pattern matching commissary.py:879, billing.py:1472.
        # Add a comment on the SI for audit trail
        si_comment = frappe.get_doc({
            "doctype": "Comment", "comment_type": "Comment",
            "reference_doctype": "Sales Invoice", "reference_name": doc.name,
            "content": f"S238: Store-side PI auto-generated → {pi.name} (Draft). "
                       f"Awaiting review by Finance team.",
        })
        si_comment.insert(ignore_permissions=True)
    except Exception:
        # v2-B1: raw SQL ROLLBACK TO SAVEPOINT (rollback_to_savepoint API doesn't exist)
        try:
            frappe.db.sql(f"ROLLBACK TO SAVEPOINT {sp_name}")
        except Exception:
            pass
        frappe.log_error(
            f"S238: PI generation failed for SI {doc.name}: {frappe.get_traceback()}",
            "S238 Store PI Generator Error",
        )
        # Do NOT block the SI submit — log and surface via Sentry only.

def build_store_pi(si, buyer_company):
    """Construct the Draft PI mirroring the SI's items + taxes."""
    # v2-B4: exact-match by account_number (deterministic, no LIKE pattern fragility)
    inv_account = resolve_account_by_number(buyer_company, ACCT_INVENTORY_FROM_COMMISSARY)
    vat_account = resolve_account_by_number(buyer_company, ACCT_INPUT_VAT_BKI_INTERCO)
    ap_account  = resolve_account_by_number(buyer_company, ACCT_AP_TRADE_BKI)

    # v2-B2: per-store warehouse — canonical model: Warehouse.docname == Company.name
    buyer_warehouse = buyer_company  # exact same string per docs/STORE_COMPANY_CANONICAL.md

    # v2.1-CRIT-2: resolve per-store cost_center BEFORE building items.
    # SI's cost_center is BKI's (e.g., 'Stores - BKI') and would fail the per-store
    # PI's `Cost Center.company == doc.company` validation. Use Warehouse.custom_cost_center
    # as primary source per pattern at store.py:5276-5281; fall back to Company.cost_center.
    buyer_cost_center = _resolve_per_store_cost_center(buyer_company, buyer_warehouse)

    pi = frappe.new_doc("Purchase Invoice")
    pi.company = buyer_company
    pi.supplier = BKI_TRADE_SUPPLIER
    pi.posting_date = si.posting_date
    # v2-B8: mirror posting_time so SLE lands at SI's exact timestamp
    pi.set_posting_time = 1
    pi.posting_time = si.posting_time
    pi.bill_no = si.name
    pi.bill_date = si.posting_date
    pi.bki_si_reference = si.name
    # v2-W (G-046 dashboard): also set the standard ERPNext IC ref so existing
    # procurement dashboards at procurement.py:4707/4731/4765 continue to report
    pi.inter_company_invoice_reference = si.name
    pi.update_stock = 1
    pi.set_warehouse = buyer_warehouse                    # v2-B2
    pi.credit_to = ap_account
    # v2.1-CRIT-1: bei_legal_entity is the BUYER's legal entity (per-store Co), NOT the seller's.
    # P10-D04 server script (p10_d04_legal_entity_issuance_guard.py:25-32) throws on mismatch;
    # same failure mode as S203 incident hrms#610 (2026-04-17). Existing PI flows at
    # erp_sync.py:2045, 2112 use buyer's company — match that pattern.
    # v2.1-W7: has_field guards prevent crashes if S192/S203 Custom Fields not yet installed.
    pi_meta = frappe.get_meta("Purchase Invoice")
    if pi_meta.has_field("bei_legal_entity"):
        pi.bei_legal_entity = buyer_company   # NOT si.bei_legal_entity (was bug in v2)
    if pi_meta.has_field("bei_store_label") and getattr(si, "bei_store_label", None):
        pi.bei_store_label = si.bei_store_label   # store label IS same on both sides
    # v2-B9: explicit item + tax mirroring (see _mirror_items, _mirror_taxes below)
    _mirror_items(pi, si, inv_account, buyer_warehouse, buyer_cost_center)
    _mirror_taxes(pi, si, vat_account, buyer_cost_center)
    return pi

def _resolve_per_store_cost_center(buyer_company, buyer_warehouse):
    """v2.1-CRIT-2: resolve a Cost Center that BELONGS TO the per-store Company.

    SI's cost_center belongs to BKI (e.g., 'Stores - BKI' from
    commissary.py:_resolve_store_cost_center which hardcodes bki_company filter).
    Mirroring it onto a per-store PI would fail Frappe's
    `Cost Center.company == doc.company` validation, and the savepoint try/except
    would silently swallow the error — 0 PIs ever created.

    Resolution order:
    1. `Warehouse.custom_cost_center` (per-store warehouse → store's CC) —
       pattern from `store.py:5276-5281`.
    2. `Company.cost_center` default — fallback for stores without warehouse-level CC.
    3. Throw if neither is set — fail loud, not silent.
    """
    cc = frappe.db.get_value("Warehouse", buyer_warehouse, "custom_cost_center")
    if not cc:
        cc = frappe.db.get_value("Company", buyer_company, "cost_center")
    if not cc:
        frappe.throw(_(
            f"S238: per-store Cost Center not found for {buyer_company}. "
            f"Set either Warehouse({buyer_warehouse}).custom_cost_center OR "
            f"Company({buyer_company}).cost_center."
        ))
    return cc

def _mirror_items(pi, si, inv_account, warehouse, cost_center):
    """v2-B9 + B10 + v2.1-CRIT-2: mirror SI line items with per-store inventory account + per-store cost_center."""
    for si_item in si.items:
        pi.append("items", {
            "item_code":   si_item.item_code,
            "item_name":   si_item.item_name,
            "description": si_item.description,
            "qty":         flt(si_item.qty),
            "uom":         si_item.uom,
            "rate":        flt(si_item.rate),
            "amount":      flt(si_item.amount),
            "warehouse":   warehouse,                     # v2-B2
            "expense_account": inv_account,
            "cost_center": cost_center,                   # v2.1-CRIT-2 (was si_item.cost_center — wrong Company)
        })

def _mirror_taxes(pi, si, vat_account, cost_center):
    """v2-B9 + v2.1-CRIT-2: mirror only Output VAT rows from SI; skip EWT-deduct rows.

    Note: `add_deduct_tax` does NOT exist on Sales Taxes and Charges (only on
    Purchase Taxes side per audit code-verifier W). The check below is defensive —
    if Frappe ever adds the column, EWT-deduct rows will be filtered out; until then
    BKI's tax structure has no EWT-deduct rows per ICT-004 anyway.
    """
    for si_tax in si.taxes:
        ah = (si_tax.account_head or "").lower()
        # Only mirror VAT (Output VAT on SI side -> Input VAT on PI side).
        if "vat" not in ah:
            continue
        # Defensive filter for future-proofing
        if getattr(si_tax, "add_deduct_tax", "") and si_tax.add_deduct_tax.lower() == "deduct":
            continue
        pi.append("taxes", {
            "charge_type":      "Actual",
            "account_head":     vat_account,
            "description":      f"Input VAT — BKI Inter-Co (mirrors SI {si.name})",
            "tax_amount":       flt(si_tax.tax_amount),
            "category":         "Total",
            "add_deduct_tax":   "Add",
            "cost_center":      cost_center,   # v2.1-CRIT-2: per-store CC, NOT si_tax.cost_center
        })

def resolve_account_by_number(company, account_number):
    """v2-B4: exact match by account_number (deterministic).

    Replaces v1's LIKE %name% lookup which silently picked random matches on dupes.
    """
    rows = frappe.db.sql(
        "SELECT name FROM `tabAccount` "
        "WHERE company=%s AND account_number=%s AND disabled=0 LIMIT 1",
        (company, account_number), as_dict=True,
    )
    if not rows:
        frappe.throw(_(
            f"S238: account number '{account_number}' not found on {company}. "
            f"Run scripts/s238/seed_pi_generator_accounts.py --apply first."
        ))
    return rows[0]["name"]


# v2-B3: on_cancel cascade hook handler (Sales Invoice on_cancel)
def cascade_cancel_store_pi(doc, method=None):
    """When a BKI SI is cancelled, cascade to the paired store-side PI.

    - If paired PI is Draft (docstatus=0): delete it (no GL impact).
    - If paired PI is Submitted (docstatus=1): file a Comment alert and DO NOT
      auto-cancel — that requires Denise's review (cancel cascade on a
      Submitted PI reverses inventory + Input VAT in the per-store books and
      should be a deliberate accounting action, not an automatic one).

    Reference pattern: commissary.py:1317-1353 (S168's
    _delete_orphan_draft_si_on_se_cancel handles the analogous
    Stock Entry → Sales Invoice cascade).
    """
    set_backend_observability_context(
        module="billing",
        action="cascade_cancel_store_pi",
        mutation_type="delete",
        extras={"si_name": doc.name},
    )
    if doc.company != BKI_COMPANY: return
    if not frappe.get_meta("Purchase Invoice").has_field("bki_si_reference"): return
    # v2.1-W2: try/except wrap so a PI cleanup failure does NOT block the SI cancel.
    # Pattern matches commissary.py:1317-1353 (S168 _delete_orphan_draft_si_on_se_cancel).
    try:
        pi_name = frappe.db.get_value(
            "Purchase Invoice", {"bki_si_reference": doc.name}, "name"
        )
        if not pi_name: return
        pi_status = frappe.db.get_value("Purchase Invoice", pi_name, "docstatus")
        if pi_status == 0:
            # Draft — safe to delete (no GL impact)
            frappe.delete_doc("Purchase Invoice", pi_name, ignore_permissions=True, force=True)
            si_comment = frappe.get_doc({
                "doctype": "Comment", "comment_type": "Comment",
                "reference_doctype": "Sales Invoice", "reference_name": doc.name,
                "content": f"S238: Paired Draft PI {pi_name} deleted (SI cancelled).",
            })
            si_comment.insert(ignore_permissions=True)
        elif pi_status == 1:
            # Submitted — flag for manual review; DO NOT auto-cancel
            pi_comment = frappe.get_doc({
                "doctype": "Comment", "comment_type": "Comment",
                "reference_doctype": "Purchase Invoice", "reference_name": pi_name,
                "content": (
                    f"S238: Paired BKI SI {doc.name} was CANCELLED. This PI was "
                    f"already submitted; Finance review required to decide whether "
                    f"to cancel this PI (will reverse inventory + Input VAT)."
                ),
            })
            pi_comment.insert(ignore_permissions=True)
            frappe.log_error(
                f"S238: BKI SI {doc.name} cancelled but paired PI {pi_name} is submitted — manual review required",
                "S238 PI Cascade Manual Review",
            )
    except Exception:
        # Fail-soft: don't block SI cancel just because PI cleanup raised.
        # Sentry captures via frappe.log_error monkey-patch.
        frappe.log_error(
            f"S238: cascade_cancel_store_pi failed for SI {doc.name}: {frappe.get_traceback()}",
            "S238 PI Cascade Error",
        )
```

**MUST_MODIFY:** `hrms/api/bki_store_pi_generator.py` (NEW)
**MUST_CONTAIN:** `maybe_generate_store_pi`, `cascade_cancel_store_pi`, `_resolve_per_store_cost_center`, `set_backend_observability_context`, `frappe.db.savepoint`, `ROLLBACK TO SAVEPOINT`, `BEBANG KITCHEN INC. - Trade`, `bki_si_reference`, `inter_company_invoice_reference`, `update_stock = 1`, `set_warehouse`, `set_posting_time`, `posting_time = si.posting_time`, `enable_bki_store_pi_generator`, `bki_sales_naming_series`, `has_field("bki_si_reference")`, `has_field("bei_legal_entity")`, `_mirror_items`, `_mirror_taxes`, `resolve_account_by_number`, `pi.bei_legal_entity = buyer_company`, `bei_store_label`, `custom_cost_center`, `1104210`, `1106210`, `2103210`
**MUST_NOT_CONTAIN:** `pi.bei_legal_entity = si.bei_legal_entity` (v2.1-CRIT-1 fix), `cost_center: si_item.cost_center` (v2.1-CRIT-2 fix), `auto_submit_store_pi` (v2-B11 verified)

**3-T2 (v2)** Add hooks to `hrms/hooks.py`:
```python
"Sales Invoice": {
    "on_submit": "hrms.api.bki_store_pi_generator.maybe_generate_store_pi",
    "on_cancel": "hrms.api.bki_store_pi_generator.cascade_cancel_store_pi",   # v2-B3
},
```

**MUST_MODIFY:** `hrms/hooks.py`
**MUST_CONTAIN:** `bki_store_pi_generator.maybe_generate_store_pi`, `bki_store_pi_generator.cascade_cancel_store_pi`

**3-T3 (v2)** Implement item + tax mirroring logic in `build_store_pi` (already inline in 3-T1 code skeleton above):
- `_mirror_items`: each `si.items` row → `pi.items` with `item_code`, `qty`, `rate`, `uom`, `warehouse=buyer_warehouse` (v2-B2), `expense_account=inv_account`, **`cost_center=si_item.cost_center`** (v2-B10).
- `_mirror_taxes`: filter `si.taxes` to only `account_head LIKE '%vat%'` AND `add_deduct_tax != 'Deduct'` (v2-B9 — skip EWT-deduct rows). Set `charge_type='Actual'`, mirror `tax_amount`, point `account_head` to per-store `Input VAT - BKI Inter-Co` account (resolved by number).
- Preserve `total`, `grand_total`, `outstanding_amount` calculations via Frappe's standard validate (auto on `pi.insert()`).

**3-T4 (v2)** Write unit tests in `hrms/tests/test_s238_pi_generator.py` (NEW) — expanded to 8 tests:
- **Test 1**: SI on BKI to ARANETA Customer → 1 Draft PI created on ARANETA Co with right supplier + accounts (resolved by account_number) + `set_warehouse=ARANETA-warehouse` + `posting_time` mirrored.
- **Test 2**: SI on BKI to a non-Company Customer (e.g., Walk-in, holdco) → NO PI created (filter works).
- **Test 3**: SI on BKI with `enable_bki_store_pi_generator=0` → NO PI created.
- **Test 4**: Resubmit SI scenario → PI not duplicated (idempotency via `bki_si_reference` check).
- **Test 5**: SI on a non-BKI Company → NO PI created (filter works).
- **Test 6 (v2-B3)**: BKI SI cancelled while paired PI is Draft → cascade deletes the PI; cancelled while paired PI is Submitted → manual-review Comment posted, PI NOT auto-cancelled.
- **Test 7 (v2-B9)**: SI with both Output VAT and EWT-deduct rows → PI mirrors only the VAT row; EWT row is excluded from PI taxes.
- **Test 8 (v2-W has_field)**: Custom Field `bki_si_reference` removed mid-test → hook returns early without inserting PI; logs the missing-field error.

**MUST_MODIFY:** `hrms/tests/test_s238_pi_generator.py` (NEW)
**MUST_CONTAIN:** all 8 test docstrings, `cascade_cancel_store_pi` reference, `_mirror_taxes`, `account_number`

**3-T5 (v2.1-CRIT-3)** Run unit tests via `/local-frappe`:
```bash
bench --site hq.bebang.ph run-tests --module hrms.tests.test_s238_pi_generator
```
**All 8 tests must pass** (was incorrectly stated as 5 in v2 — expanded to 8 in v2 to add Test 6 cancel cascade, Test 7 EWT filter, Test 8 has_field guard).

**Phase 3 verify (v2.1):**
```python
import sys, os
errs = []
src = open("hrms/api/bki_store_pi_generator.py", encoding="utf-8").read()
# v2.1: full MUST_CONTAIN list including v2.1-CRIT-1, v2.1-CRIT-2 fix markers
for m in ["maybe_generate_store_pi", "cascade_cancel_store_pi",
          "_resolve_per_store_cost_center",
          "set_backend_observability_context",
          "frappe.db.savepoint", "ROLLBACK TO SAVEPOINT",
          "BEBANG KITCHEN INC. - Trade", "bki_si_reference",
          "inter_company_invoice_reference",
          "update_stock = 1", "set_warehouse",
          "set_posting_time", "posting_time = si.posting_time",
          "enable_bki_store_pi_generator", "bki_sales_naming_series",
          'has_field("bki_si_reference")', 'has_field("bei_legal_entity")',
          "_mirror_items", "_mirror_taxes", "resolve_account_by_number",
          "pi.bei_legal_entity = buyer_company",  # v2.1-CRIT-1
          "custom_cost_center",                    # v2.1-CRIT-2 (Warehouse field used by helper)
          "1104210", "1106210", "2103210"]:
    if m not in src: errs.append(f"generator MUST_CONTAIN: {m}")
# v2.1-W4: MUST_NOT_CONTAIN — verify B11 toggle removed AND v2.1 CRITs not regressed
for m in ["pi.bei_legal_entity = si.bei_legal_entity",  # v2.1-CRIT-1 — must NOT mirror seller
          "cost_center: si_item.cost_center"]:           # v2.1-CRIT-2 — must NOT mirror seller's CC
    if m in src: errs.append(f"generator MUST_NOT_CONTAIN: {m}")
# auto_submit may appear in comments noting it's removed; check it doesn't appear as actual code
if "pi.submit()" in src:
    errs.append("generator must NOT call pi.submit() (v2-B11 removed auto-submit)")
hooks = open("hrms/hooks.py", encoding="utf-8").read()
if "bki_store_pi_generator.maybe_generate_store_pi" not in hooks:
    errs.append("hooks.py missing on_submit hook")
if "bki_store_pi_generator.cascade_cancel_store_pi" not in hooks:
    errs.append("hooks.py missing on_cancel hook (v2-B3)")
if not os.path.exists("hrms/tests/test_s238_pi_generator.py"):
    errs.append("Unit tests file missing")
print("PASS" if not errs else "\n".join(errs))
sys.exit(0 if not errs else 1)
```

---

### Phase 4 — Single-Store Trial (ARANETA) (8 units)

**4-T1** Deploy code to local-frappe via `/local-frappe` first. Run unit tests (8 tests, all must pass).

**4-T2 (v2)** Submit BKI→ARANETA SI via the existing `complete_receiving` flow **on local-frappe ONLY** (v2 audit blocker — PRODUCTION trial is forbidden because it consumes BIR-authorized ATP serials per Phase 4 v2 amendment):
- Small amount (~PHP 1.00, 1 line item from existing catalog)
- Verify SI submits successfully
- Verify Draft PI auto-created on per-store-replica's books in local-frappe
- All 8 unit tests + browser-validated trial run on local-frappe before any production touch

**4-T3** Open the auto-created Draft PI in Frappe Desk:
- `supplier=BEBANG KITCHEN INC. - Trade` ✓
- `bill_no=<SI name>` ✓
- `bki_si_reference=<SI name>` ✓
- `update_stock=1` ✓
- `posting_date=<SI posting_date>` ✓
- Line items match SI 1:1
- Tax row shows 12% Input VAT with `account_head=Input VAT - BKI Inter-Co`

**4-T4** Submit the Draft PI manually (test.finance@bebang.ph). Verify:
- SLE created on ARANETA's per-store warehouse with `actual_qty>0`, `voucher_type=Purchase Invoice, voucher_no=<PI name>`
- GL Entries: DR Inventory-from-Commissary, DR Input VAT - BKI Inter-Co, CR AP-Trade-BKI (with `party_type=Supplier, party=BEBANG KITCHEN INC. - Trade`)

**4-T5** Run per-store P&L for ARANETA — verify Inventory-from-Commissary line is on Balance Sheet (not COGS yet — COGS happens at consumption).

Write to `output/s238/verification/aranetatrial_pi.json`:
```json
{
  "test_si": "<SI name>",
  "test_pi": "<PI name>",
  "pi_supplier": "BEBANG KITCHEN INC. - Trade",
  "pi_update_stock": true,
  "pi_bki_si_reference": "<SI name>",
  "sle_count": 1,
  "sle_actual_qty": <value>,
  "gl_entries": [<rows>],
  "input_vat_account": "<account>",
  "ap_account": "<account>",
  "trial_pass": true
}
```

**4-T6** Cancel the test PI then test SI; verify clean state.

**Phase 4 verify:**
```python
import json, sys
state = json.load(open("output/s238/verification/aranetatrial_pi.json"))
errs = []
required = ["test_si", "test_pi", "pi_supplier", "pi_update_stock", "pi_bki_si_reference",
            "sle_count", "gl_entries", "trial_pass"]
for k in required:
    if k not in state: errs.append(f"missing {k}")
if state.get("pi_supplier") != "BEBANG KITCHEN INC. - Trade":
    errs.append(f"wrong supplier: {state.get('pi_supplier')}")
if state.get("sle_count", 0) != 1: errs.append(f"expected 1 SLE, got {state.get('sle_count')}")
if not state.get("trial_pass"): errs.append("trial_pass=false")
print("PASS" if not errs else "\n".join(errs))
sys.exit(0 if not errs else 1)
```

---

### Phase 5 — 5-Store Regression + Historical SI Verification + S206 Sanity (5 units)

**5-T1** Pick 5 stores spanning diverse legal entities: ARANETA (TUNGSTEN), AYALA EVO CITY (BEBANG MEGA), CTTM TOMAS MORATO (B CUBED VENTURES), ORTIGAS GREENHILLS (BEIFRANCHISE), SM TANZA (BEBANG MEGA).

**5-T2** Sample 5 random PRE-S238 historical SIs. Verify:
- Still readable; customer field unchanged.
- `bki_si_reference` does not appear on the historical SI (it's a Custom Field on PI only).
- The historical SIs have NO matching PI (existing 0-PI state preserved for historicals — backfill is out of scope).
- Standard SI print format renders correctly with TIN intact.

Write `output/s238/verification/historical_si_regression.json` with the results.

**5-T3 (v2)** For each of the 5 trial stores, submit a NEW BKI SI **on local-frappe** (small amount, immediately cancel — never on production per v2-B-trial-on-prod fix). Verify each generates a Draft PI on each respective store's books with the right supplier + accounts. Cancel each Draft PI; verify on_cancel cascade deletes the Draft PI (v2-B3 test).

**5-T4** S206 sanity check: trigger labor JE creation for one of the 5 trial stores via existing S206 path:
- Labor JE creates against the existing `(Internal)` Customer (UNTOUCHED).
- The new `BEBANG KITCHEN INC. - Trade` Supplier is NOT involved.
- JE submits correctly.

**5-T5** Run full canonical verifier post-trial:
```bash
python scripts/verify_canonical_structure.py 2>&1 | tee output/s238/verification/canonical_post_check.log
```
Must show `ALL CANONICAL`. No new violations vs Phase 0 baseline.

---

### Phase 6 — Closeout (3 units)

**6-T1 (v2)** Push branch + open PR with all changes (single PR):
```bash
git push -u origin s238-ict003-store-pi-generator
GH_TOKEN="" gh pr create --repo Bebang-Enterprise-Inc/hrms --base production \
  --head s238-ict003-store-pi-generator \
  --title "feat(S238 v2): ICT-003 store-side Purchase Invoice generator" \
  --body-file output/s238/PR_BODY.md
```

PR description calls out:
- ICT-003 implementation gap closed (per Butch's 2026-02-20 directive, still binding per 2026-05-07 banner).
- 147 GL accounts seeded (account_numbers `1104210`/`1106210`/`2103210` × 49 stores) + 1 new BKI Trade Supplier + 1 Custom Field + 1 BEI Settings toggle + 1 generator module + 2 hooks (on_submit + on_cancel).
- Trial + 5-store regression + S206 sanity all green on **local-frappe only** (v2 audit fix — no production trial).
- `is_internal_customer/_supplier` flags ALL untouched. Canonical Rules 1-8 UNCHANGED.
- Backfill of 839 historical SI deferred (separate sprint if BIR Q1 2026 amended 2550Q recovery is approved — likely 6-7 figures of Input VAT across 49 entities per audit ph-finance W).
- Deploy mode: `skip_build=false, no_cache=true` (v2 audit B-deploy — full build required for new module).

**6-T1a (v2 NEW — declares deploy mode)** When PR merges and Sam triggers `/deploy-frappe`, MUST use:
```bash
skip_build=false
no_cache=true
```
The new module `hrms/api/bki_store_pi_generator.py` is NOT in the cached Docker image. `skip_build=true` would silently break the feature (MEMORY lesson #2).

**6-T2** Update plan YAML → `status: COMPLETED`, `completed_date`, `pr`, `execution_summary`. Mark S236 v2 as SUPERSEDED in its YAML (`status: SUPERSEDED_BY_S238`).

**6-T3** Update `docs/plans/SPRINT_REGISTRY.md`:
- S238 row → COMPLETED with PR # + verification proof
- S236 row → already PLANNED v2; amend to SUPERSEDED_BY_S238 with explanation

**6-T4** Write `output/s238/SUMMARY.md` — closeout artifact.

**6-T5** Worktree closeout:
```bash
cd F:/Dropbox/Projects/BEI-ERP-s238-ict003-pi-generator && git status --short
cd F:/Dropbox/Projects/BEI-ERP
git worktree remove F:/Dropbox/Projects/BEI-ERP-s238-ict003-pi-generator
```

**6-T6 (v2 NEW — post-merge smoke check)** After Sam merges the PR and `/deploy-frappe` runs successfully, perform a 1-store production smoke:
- Wait for the next BKI→ARANETA SI to submit through the normal `complete_receiving` flow (or manually trigger one if needed).
- Within 30 seconds, query: `SELECT name, supplier, bki_si_reference, inter_company_invoice_reference FROM \`tabPurchase Invoice\` WHERE bki_si_reference = '<that SI>'`
- If 1 row returned with `supplier="BEBANG KITCHEN INC. - Trade"` AND `bki_si_reference` populated AND `inter_company_invoice_reference` populated → SMOKE PASS.
- If 0 rows after 60 seconds → check Sentry for `S238 Store PI Generator Error`; the hook may have failed silently. Triage immediately.
- Write result to `output/s238/verification/post_merge_smoke.json`.

**6-T7 (v2 + v2.1-W9 — drift-detection script registered as scheduled job)** Ship `scripts/s238/check_si_pi_pairing.py` as a weekly reconciliation tool:
- Query: BKI SIs submitted in the last 7 days WITHOUT a matching PI on `bki_si_reference`.
- Output: `output/s238/reconciliation/<date>_si_without_pi.csv` listing SI name + customer + grand_total + age.
- **v2.1-W9 NEW**: register as a Frappe `scheduler_event.weekly` job in `hrms/hooks.py` so it runs autonomously (not manual). Pattern:
```python
# in hrms/hooks.py
scheduler_events = {
    "weekly": [
        # ... existing entries ...
        "hrms.api.bki_store_pi_generator.run_si_pi_pairing_check",  # v2.1-W9
    ],
}
```
- Add a thin entry-point function in the generator module that imports and runs the check, emits Sentry alert if drift > 5 SIs.
- Add closeout SUMMARY hint: "Auto-runs weekly; investigate any rows surfaced via Sentry alert."

**6-T8 (v2 + v2.1-W11 — refined Input VAT recovery estimate)** Add to `output/s238/SUMMARY.md` a clearly-labeled "Follow-Up Sprint Candidate" section noting:
- Pre-S238 BKI SI breakdown (per code-verifier production probe): **560 Submitted + 49 Draft + 230 Cancelled = 839 total**.
- Only the **560 Submitted** are eligible for Input VAT recovery (Drafts not in books; Cancelled have docstatus=2 reversals).
- Each store's Q1 2026 BIR Form 2550Q has incomplete Input VAT claim from BKI commissary purchases.
- **Refined estimate**: ≈ PHP 1.58M aggregate Input VAT recoverable (low end of 7 figures), distributed across the per-store buyers per their share of the 560 Submitted SIs. 251 of the 839 SIs have non-matching customers (walk-in / holdco / other) — those are NOT eligible for per-store Input VAT recovery.
- Mechanism: same generator function reusable as one-off backfill script (idempotent via `bki_si_reference` check); BIR amended 2550Q filing required per per-store entity. Note: amended filings require Q1 2026 to still be amendable (BIR usually allows 3-year amendment window).
- DECISION: defer to Sam (CEO) — not auto-actioned by S238.

---

## Phase Budget Contract (v2.1 — re-audit-amended)

| Phase | v1 | v2 | v2.1 | v2.1 Δ rationale |
|---|---:|---:|---:|---|
| Phase 0 — Boot + state probe | 4 | 6 | 7 | v2.1: +1 — NEW Phase 0-T0 pre-flight `bki_sales_naming_series` SAM-action check |
| Phase 1 — Account seeder | 5 | 7 | 7 | unchanged |
| Phase 2 — Supplier + Custom Field + Toggle | 5 | 5 | 5 | unchanged |
| Phase 3 — PI generator implementation | 10 | 14 | 16 | v2.1: +2 — `_resolve_per_store_cost_center` helper (CRIT-2), correct `bei_legal_entity` (CRIT-1), `has_field` guards on S192/S203 fields (W7), try/except on cascade (W2), silent-skip Sentry breadcrumb (W3), verify-script MUST_NOT_CONTAIN flip (W4) |
| Phase 4 — local-frappe trial | 8 | 8 | 8 | unchanged |
| Phase 5 — 5-store regression + S206 sanity | 5 | 5 | 5 | unchanged |
| Phase 6 — Closeout | 3 | 5 | 6 | v2.1: +1 — register drift script as `scheduler_event.weekly` (W9) |
| **Total** | **40** | **50** | **57** | v2.1: +7 units (4 CRIT fixes + 5 W fixes) |

**v2.1 total: 57 units** — well under 80-unit ceiling. No phase exceeds 16 units. Single-session executable.

---

## Surface Ownership Matrix (S087, v2.1)

| Surface | Owner | Allowed mutations |
|---|---|---|
| `hrms/api/bki_store_pi_generator.py` | S238 | NEW file (v2.1: + cascade_cancel_store_pi w/try-except + lock_posting_date_on_bki_paired_pi + _mirror_items + _mirror_taxes + resolve_account_by_number + **_resolve_per_store_cost_center** [v2.1-CRIT-2] + run_si_pi_pairing_check entry point [v2.1-W9]; bei_legal_entity uses buyer_company [v2.1-CRIT-1]) |
| `hrms/hooks.py` | S238 | ADD `Sales Invoice on_submit` + `Sales Invoice on_cancel` (v2-B3) + `Purchase Invoice validate` (v2-B8) + `scheduler_events.weekly` for drift script (v2.1-W9) entries |
| `hrms/tests/test_s238_pi_generator.py` | S238 | NEW file (v2: 8 tests, was 5) |
| `scripts/s238/seed_pi_generator_accounts.py` | S238 | NEW (v2: account_number prefixes, dynamic `_find_parent_group`) |
| `scripts/s238/seed_bki_trade_supplier.py` | S238 | NEW |
| `scripts/s238/install_bki_si_reference_field.py` | S238 | NEW |
| `scripts/s238/install_bei_settings_toggles.py` | S238 | NEW — installs only `enable_bki_store_pi_generator` (v2-B11: NOT `auto_submit_store_pi`) |
| `scripts/s238/check_si_pi_pairing.py` | S238 | NEW (v2-W: drift-detection reconciliation) |
| `tabAccount` | S238 | INSERT 147 accounts (3 × 49 stores) with deterministic account_numbers `1104210`/`1106210`/`2103210` (v2-B4) |
| `tabSupplier` | S238 | INSERT 1 record (`BEBANG KITCHEN INC. - Trade`) + 49 `companies` child entries (lowercase fieldname per v2 standardization) |
| `Custom Field` on `Purchase Invoice` | S238 | INSERT 1 field (`bki_si_reference`) |
| `BEI Settings` | S238 | INSERT 1 toggle field (`enable_bki_store_pi_generator`); v2 dropped `auto_submit_store_pi` |
| `hrms/api/commissary.py` | NOT S238 | UNCHANGED — including line 1137 hardcode |
| `hrms/api/billing.py` | NOT S238 | UNCHANGED — including line 674/867 hardcodes (corrected from v1's incorrect line 595 per code-verifier) |
| `hrms/utils/supply_chain_contracts.py` | NOT S238 | UNCHANGED |
| `hrms/utils/labor_allocation.py` | NOT S238 | UNCHANGED |
| `docs/STORE_COMPANY_CANONICAL.md` | NOT S238 | UNCHANGED |
| `data/_CONSOLIDATED/01_FINANCE/DECISIONS.md` ICT-008 row | NOT S238 | OUT OF SCOPE — separate doc fix to update `4000003` → `4000210` (flagged in closeout SUMMARY) |
| `tabCustomer` | NOT S238 | UNCHANGED — no flag flips |
| Existing `BEBANG KITCHEN INC. (Internal)` Supplier | NOT S238 | UNCHANGED |
| Existing 839 historical BKI SIs | NOT S238 | UNCHANGED — no backfill |
| `tabCompany` / `tabWarehouse` | NOT S238 | UNCHANGED |

---

## Anti-Rewind / Concurrent-Run Protection

- **protected_surfaces:**
  - 49 per-store billing Customers — UNCHANGED
  - 49 S206 Internal Customers — UNCHANGED
  - 839 historical BKI SI records — UNCHANGED
  - Canonical Rules 1-8 — UNCHANGED
  - `commissary.py:1137`, `billing.py:595` (`is_internal_customer = 0` hardcodes) — UNCHANGED
  - `labor_allocation.py:324-339` (S206 lookup) — UNCHANGED
  - `resolve_store_buyer_entity` — UNCHANGED
- **remote_truth_baseline:** `tmp/s238/remote_truth_baseline_hrms.sha`
- **pretouch_backup:** none required (no master-data mutations on existing records)
- **supersession_map:** S236 v2 → S238 (S236 v2 was wrong architecture; S238 follows ICT-003 correctly)

---

## Requirements Regression Checklist (v2.1)

### NEW v2.1 audit-fix checks (must all pass)

- [ ] **CRIT-1 (bei_legal_entity)**: code skeleton has `pi.bei_legal_entity = buyer_company` (NOT `si.bei_legal_entity`). Verify via grep: `grep -c "pi.bei_legal_entity = buyer_company"` returns ≥1, AND `grep -c "pi.bei_legal_entity = si.bei_legal_entity"` returns 0.
- [ ] **CRIT-1 (P10-D04 trial)**: ARANETA trial PI submits without "Legal Entity must match Company for issuance" error.
- [ ] **CRIT-2 (cost_center)**: `_resolve_per_store_cost_center` helper exists in generator module with Warehouse.custom_cost_center → Company.cost_center fallback. `_mirror_items` and `_mirror_taxes` BOTH use the buyer-company-resolved cost_center, NOT `si_item.cost_center`.
- [ ] **CRIT-2 (validation pass)**: ARANETA trial PI passes `Cost Center.company == doc.company` validation (does not crash with "Cost Center X does not belong to Company Y").
- [ ] **CRIT-3 (test count)**: Phase 3-T5 says "All 8 tests must pass" (NOT 5). All 8 tests run.
- [ ] **CRIT-4 (parent group naming)**: NO occurrence of `Stock in Hand` parent group reference in plan body outside of explanatory amendment notes. Test Data Seeding Contract uses `Stock Assets - <ABBR>` (or dynamic per-store reference).
- [ ] **W1 (BIR series Sam-action)**: Phase 0-T0 verifies `BEI Settings.bki_sales_naming_series` is set BEFORE Phase 0-T1 begins. If NULL, agent STOPS and asks Sam.
- [ ] **W2 (cascade try/except)**: `cascade_cancel_store_pi` wraps body in try/except; SI cancel never blocks on PI cleanup failure.
- [ ] **W3 (silent skip log)**: generator's "customer is not a per-store Company" exit path emits Sentry breadcrumb. Verify by grep for `add_breadcrumb` in generator module.
- [ ] **W4 (verify-script flip)**: Phase 3 verify script uses MUST_NOT_CONTAIN for `pi.bei_legal_entity = si.bei_legal_entity` and `cost_center: si_item.cost_center`. `auto_submit_store_pi` may appear in code comments but NOT as actual `pi.submit()` call.
- [ ] **W7 (has_field guards)**: `pi.bei_legal_entity` and `pi.bei_store_label` assignments wrapped in `frappe.get_meta("Purchase Invoice").has_field(...)` guards.
- [ ] **W9 (scheduler registration)**: `hrms/hooks.py` has `scheduler_events.weekly` entry registering `run_si_pi_pairing_check`. Drift script auto-runs without manual trigger.
- [ ] **3-way refutation preserved**: Plan does NOT include any "BKI Title Case" guard logic. The hook filter uses uppercase string match (`if doc.company != "BEBANG KITCHEN INC."`).

---

## Requirements Regression Checklist (v2)

Executing agent MUST verify before each PR:

**v1 baseline checks**
- [ ] Canonical preflight ran clean BEFORE any code change (Phase 0)
- [ ] `BEI Settings.bki_sales_income_account` exists (ICT-008 prerequisite verified at Phase 0)
- [ ] 147 accounts seeded across 49 per-store Companies (3 × 49) with proper `account_type` / `root_type` / `report_type` / `parent_account` per per-store CoA
- [ ] 1 NEW Supplier `BEBANG KITCHEN INC. - Trade` created with `is_internal_supplier=0` and `tax_id` populated
- [ ] 49 `companies` child entries on the new Supplier (v2: lowercase fieldname per code standardization)
- [ ] 1 Custom Field `bki_si_reference` on Purchase Invoice (Link → Sales Invoice, read-only)
- [ ] `hrms/api/bki_store_pi_generator.py` implements `maybe_generate_store_pi` with all MUST_CONTAIN strings
- [ ] `hrms/hooks.py` has `Sales Invoice on_submit → maybe_generate_store_pi` entry
- [ ] Sentry observability — `set_backend_observability_context` called with `module=billing`, `action=maybe_generate_store_pi`
- [ ] PI submit creates SLE on per-store warehouse + GL Entries with `party_type=Supplier, party=BEBANG KITCHEN INC. - Trade` (DM-1)
- [ ] PI carries 12% Input VAT mirroring SI's Output VAT
- [ ] S206 labor JE flow STILL works (no resolver/Customer/Supplier collision)
- [ ] Toggle off → no PI generated (kill switch works)
- [ ] Idempotency: re-running generator on same SI → no duplicate PI
- [ ] Canonical post-check `ALL CANONICAL` (zero new violations)
- [ ] DM-1 / DM-2 / DM-3 / DM-4 / DM-5 / DM-6 — verified per checklist
- [ ] No flips to `is_internal_customer/_supplier` anywhere
- [ ] No modifications to `commissary.py:1137`, `billing.py:674,867` (v2-corrected from v1's 595), `labor_allocation.py`, `supply_chain_contracts.py`, `STORE_COMPANY_CANONICAL.md`
- [ ] Worktree closeout clean
- [ ] Test SI + Draft PI cancelled; teardown ledger complete

**v2 audit-fix checks (NEW — must all pass)**
- [ ] **B1**: NO occurrence of `frappe.db.rollback_to_savepoint(` anywhere in `bki_store_pi_generator.py`. Use `frappe.db.sql("ROLLBACK TO SAVEPOINT ...")` exclusively (verify via `grep -c "rollback_to_savepoint" hrms/api/bki_store_pi_generator.py` → must be 0).
- [ ] **B2**: `pi.set_warehouse` is set in `build_store_pi`. Verify via grep + ARANETA trial PI doc shows `set_warehouse` populated.
- [ ] **B3**: `cascade_cancel_store_pi` exists; `Sales Invoice on_cancel → cascade_cancel_store_pi` registered in hooks.py; Test 6 passes (cancel cascade Draft delete + Submitted manual-review path).
- [ ] **B4**: `resolve_account_by_number` uses exact-match on `account_number`; no `LIKE` patterns in account resolution.
- [ ] **B5**: `before_state.json` has `per_store_coa_parent_groups` for all 49 stores; seed script uses dynamic `_find_parent_group()`; new accounts land under `Stock Assets - <ABBR>` (NOT `Stock in Hand`).
- [ ] **B6**: Plan body references `4000210 - DELIVERIES - BKI` (production reality), not `4000003`. Closeout SUMMARY flags DECISIONS.md ICT-008 row as a follow-up data fix.
- [ ] **B7**: `BEI Settings.bki_sales_naming_series` verified set in Phase 0 (HARD STOP if missing). Generator additionally guards on `naming_series` prefix match.
- [ ] **B8**: PI has `set_posting_time=1, posting_time=si.posting_time`. `lock_posting_date_on_bki_paired_pi` validate hook prevents non-Administrator edits.
- [ ] **B9**: `_mirror_taxes` filters to VAT only, skips EWT-deduct rows; `charge_type='Actual'`; tax_amount mirrored. Test 7 passes.
- [ ] **B10**: PI items have `cost_center` mirrored from SI per line.
- [ ] **B11**: `auto_submit_store_pi` toggle is NOT installed. `MUST_NOT_CONTAIN` check passes on `install_bei_settings_toggles.py`. Generator code has NO `pi.submit()` call.
- [ ] W (G-046): PI also has `inter_company_invoice_reference = si.name`. G-046 dashboard at `procurement.py:4707` reflects S238 PIs.
- [ ] W (has_field guard): generator returns early if `Purchase Invoice.bki_si_reference` Custom Field not installed.
- [ ] W (S192/S203): PI has `bei_legal_entity` and `bei_store_label` mirrored from SI.
- [ ] W (companies fieldname): code uses lowercase `companies`; "Allowed To Transact With" only in prose/labels.
- [ ] W (deploy mode): PR description AND closeout note `skip_build=false, no_cache=true`.
- [ ] W (post-merge smoke): 6-T6 executed; `output/s238/verification/post_merge_smoke.json` PASS.
- [ ] W (drift-detection): `scripts/s238/check_si_pi_pairing.py` shipped.
- [ ] W (839-SI follow-up): closeout SUMMARY surfaces ~6-7 figures Q1 Input VAT recovery as Sam-decision item.
- [ ] W (trial on local-frappe only): Phase 4-T2 + 5-T3 do NOT touch production; "(or production)" stripped.
- [ ] **8 unit tests** (was 5 in v1) all pass: includes Test 6 (on_cancel cascade), Test 7 (EWT filter), Test 8 (has_field guard).

---

## Autonomous Execution Contract

- **completion_condition:**
  - All 6 phases complete with verify scripts PASS
  - 147 accounts + 1 Supplier + 1 Custom Field + 2 toggles + 1 hook + 1 module shipped
  - ARANETA trial PASS
  - 5-store regression PASS
  - S206 sanity PASS
  - Canonical post-check `ALL CANONICAL`
  - PR opened, plan YAML status: COMPLETED, registry updated, S236 v2 marked SUPERSEDED_BY_S238
- **stop_only_for:**
  - Canonical preflight returns violations (pre or post)
  - `BEI Settings.bki_sales_income_account` not set (ICT-008 prerequisite missing)
  - Per-store CoA structure inconsistent (some stores missing parent groups for the 3 new accounts)
  - 5-store regression reveals existing SI flow regression
  - S206 labor JE flow broken
  - Three failed attempts at the same migration step
  - Sam explicitly requests halt
- **continue_without_pause_through:**
  - Plan write → audit → execute Phases 0→6 → PR creation → closeout
- **blocker_policy:**
  - Hook not firing → debug Frappe hook registration; bench restart; retry
  - PI insert blocked by validation → check accounts + supplier + party fields; retry
  - 3 consecutive trial failures → STOP and reassess
- **signoff_authority:** `single-owner` (Sam)
- **canonical_closeout_artifacts:**
  - `output/s238/SUMMARY.md`
  - `output/s238/verification/before_state.json`
  - `output/s238/verification/after_state.json`
  - `output/s238/verification/aranetatrial_pi.json`
  - `output/s238/verification/historical_si_regression.json`
  - `output/s238/verification/canonical_post_check.log`
  - `docs/plans/2026-05-07-sprint-238-ict003-store-pi-generator.md` (status COMPLETED)
  - `docs/plans/SPRINT_REGISTRY.md` (S238 row → COMPLETED, S236 row → SUPERSEDED_BY_S238)

---

## Status Reconciliation Contract

Whenever counts, blockers, stage, or status changes, update in the same work unit:
1. `output/s238/SUMMARY.md`
2. plan YAML status line + `execution_summary`
3. `SPRINT_REGISTRY.md` S238 row + S236 supersession note
4. `output/s238/verification/*.json` files
5. teardown ledger
6. canonical post-check log

---

## Signoff Model

- **mode:** `single-owner`
- **approver_of_record:** Sam Karazi (CEO) — CFO seat vacant indefinitely per 2026-05-07 update to DECISIONS.md
- **signoff_artifact:** `output/s238/SUMMARY.md`
- **note:** Sam approved the architecture in conversation 2026-05-07. No further sign-off required during execution unless one of the `stop_only_for` conditions trips.

---

## Ground-Truth Lock

- **evidence_sources:**
  - `data/_CONSOLIDATED/01_FINANCE/DECISIONS.md:193-200` (ICT-001..008 verbatim)
  - `data/_CONSOLIDATED/01_FINANCE/questionnaires/CFO_INTERCOMPANY_Butch_Formoso_2026-02-20.md:35-42` (Q3 verbatim)
  - `hrms/api/commissary.py:864-988, 973-1248` (existing SI builder)
  - `tmp/CANONICAL_COVERAGE_AUDIT_SUMMARY.md` (audit findings)
  - `tmp/pi_probe.json` (839 SI / 0 PI on store side)
  - `output/plan-audit/s236-intercompany-auto-trade/AUDIT_SUMMARY.md` (S236 v2 audit, the basis for v1→S238 reframe)
- **count_method:**
  - SI count: `SELECT COUNT(*) FROM tabSales Invoice WHERE company='BEBANG KITCHEN INC.'`
  - PI count: `SELECT COUNT(*) FROM tabPurchase Invoice WHERE supplier LIKE 'BEBANG KITCHEN%'`
  - Account count: `SELECT COUNT(*) FROM tabAccount WHERE account_name LIKE '%Inventory-from-Commissary%' OR ...`
  - basis: live SQL via SSM-Frappe
- **authoritative_sections:** Sections "Design Rationale" + "Phases 0-6" + "Surface Ownership" + "Requirements Regression Checklist" are authoritative for execution
- **normalization_required:** any amendment changing seed counts, hook surface, or canonical impact must update authoritative sections in the same edit
- **unresolved_value_policy:** operator-facing unknowns → `[UNVERIFIED — requires resolution]`
- **normalization_artifacts:** `output/s238/verification/before_state.json`, `output/s238/verification/after_state.json`

---

## Execution Skills Reference

- Test Python changes: `/local-frappe`
- Deploy changes: `/deploy-frappe`
- Full workflow: `/agent-kickoff`
- E2E testing: `/e2e-test`
- Bulk data ops: `/frappe-bulk-edits` (use for the 3 idempotent seed scripts)

---

## Sprint Registry Row (Evidence of Lock)

```
| `S238` | Sprint 238 | `s238-ict003-store-pi-generator` | TBD | PLANNED 2026-05-07 — ICT-003 Store-Side Purchase Invoice Generator | `docs/plans/2026-05-07-sprint-238-ict003-store-pi-generator.md` |
```

Cross-checked: `git branch -a | grep s238` returned no matches before reservation; `ls docs/plans/ | grep sprint-238` empty.

---

## Execution Authority

Single agent, single session. Phase 0 through Phase 6, end to end. 40 units. Stop only for items in `stop_only_for`. Sam has pre-approved the architecture; no Phase-0 decision gate needed.
