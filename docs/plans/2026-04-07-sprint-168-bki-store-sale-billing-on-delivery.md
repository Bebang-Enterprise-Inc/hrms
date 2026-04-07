# S168 — BKI → Store External Sale Billing (On Delivery, Not Fulfillment)

> **Context in one line:** The current `_create_intercompany_invoices_async` is wrong. Stores are separate BIR-registered corporations, not BKI's internal customers. Sales Invoices must be issued with 12% VAT, correct per-store-type markup, and at **Delivery + Store DR acceptance**, not at commissary fulfillment.

```yaml
sprint: S168
branch: s168-bki-store-sale-billing-on-delivery
status: DEPLOYED_AWAITING_RUNTIME_PREREQS
planned_date: 2026-04-07
audit_completed: 2026-04-07
execution_started: 2026-04-07
deployed_at: 2026-04-07
backend_pr: https://github.com/Bebang-Enterprise-Inc/hrms/pull/482
frontend_pr: https://github.com/Bebang-Enterprise-Inc/BEI-Tasks/pull/351
verify_status: "Phases 0-11, 14, 15 PASS; Phase 12 (naming_series wiring) + 13 (ewt_rate reference) GAPS; Phase 16 L3 deferred to fresh session"
runtime_prereqs_pending:
  - "bench --site hq.bebang.ph migrate (9 Custom Fields not yet synced — confirmed by L1 audit)"
  - "Run scripts/s168_seed_*.py in order against live BKI company (GL accounts, VAT template, Customer Group, 35 Customers, cost centers, BEI Settings config)"
  - "Finance sets BEI Settings.bki_sales_naming_series to authorized BIR ATP/PTU prefix"
audit_round_1: "18 CRITICAL + 29 WARNING + 19 INFO across 4 domains (backend, finance, execution, code-verifier); amendments applied inline"
audit_round_2: "28 CRITICAL + 49 WARNING + 23 INFO across 4 additional domains (frontend, deployment/QA, team orchestration, code-verifier re-run); 2 of Round 2's top 3 count blockers DISMISSED by Layer 1 fact-check, 2 NEW CRITICALs found (COA account 2103100→2102205 rename, 4000003 already ROYALTY INCOME); see output/plan-audit/s168-bki-store-sale-billing-on-delivery/verified_blockers_round2.md"
amendments_applied: 2026-04-07
execution_started:
completed_date:
execution_summary:
plan_file: docs/plans/2026-04-07-sprint-168-bki-store-sale-billing-on-delivery.md
registry_row: "| `S168` | Sprint 168 | `s168-bki-store-sale-billing-on-delivery` | — | GO 2026-04-07 PM — Full BKI→store billing fix + completeness (17 phases, 114 units, 2-session execution). R1+R2 audit amendments applied. Incoterm: destination terms, revenue on DR acceptance (ICT-007). Sales account: parent group `4000100 WHOLESALE / B2B SALES` + posting `4000101 SALES - BKI TO STORES` (ICT-008 Butch Option C — locked). Output VAT: `2102205 OUTPUT VAT PAYABLE` (ICT-009 Butch confirmed). BIR ATP/PTU and TPD are Finance production-gate items, outside plan scope. | `docs/plans/2026-04-07-sprint-168-bki-store-sale-billing-on-delivery.md` |"
repos: hrms (backend, fixtures, DocType), bei-tasks (Phase 9 DR input, Phase 11 credit note UI, Phase 14 billing holds dashboard)
depends_on:
  - S037 (store_buyer_entity_register — already live in hrms/utils/supply_chain_contracts.py)
  - S163 (multi-row model for grouped order items — affects Sales Invoice row generation)
locked_decisions:
  - ICT-001 — 12% Output VAT on every BKI→store SI (2026-02-20)
  - ICT-002 — JV 2.75% / Franchise 8% markup (2026-02-22)
  - ICT-003 — BKI issues SI only, stores file own AP (2026-02-20)
  - ICT-004 — No EWT, not Top 20,000 taxpayer (2026-02-20)
  - ICT-005 — BKI is a separate Frappe Company (2026-02-20)
  - ICT-006 — Toll manufacturing rejected (2026-02-22)
  - ICT-007 — Destination terms, revenue recognized on store DR acceptance (2026-04-07)
  - ICT-008 — Sales GL: parent group `4000100 WHOLESALE / B2B SALES` + posting child `4000101 SALES - BKI TO STORES` (2026-04-07 PM; Butch locked Option C — taxonomically consistent with existing `4000200 DISCOUNTS AND PROMO` / `4000300 FRANCHISE INCOME` grouping pattern)
  - ICT-009 — Output VAT account 2102205 OUTPUT VAT PAYABLE (2026-04-07; 2103100 was retired in current COA; Butch confirmed PM)
out_of_plan_scope:
  - BIR Authority to Print (ATP) / Permit to Use (PTU) — Finance maintains BKI's BIR invoice authorization. Plan codes a configurable naming series; Finance sets the authorized prefix in BEI Settings before first production invoice is issued.
  - Transfer Pricing Documentation (TPD) per RR 2-2013 / RR 19-2020 — Finance / external counsel maintains the TPD for BIR audit defense. Plan does not generate, store, or gate on the TPD.
canonical_unit_total: 114
canonical_store_count: 35 unique buyer corporations covering 45 active stores (S037 active rows); 3 non-operating/provisional rows excluded from billing scope
```

---

## AUDIT ADDENDUM (2026-04-07) — 18 CRITICAL AMENDMENTS APPLIED

A 4-domain audit (backend/DM, PH Finance/BIR, execution governance, code verifier) ran 2026-04-07 and found 18 CRITICAL / 29 WARNING / 19 INFO issues. Full findings: `output/plan-audit/s168-bki-store-sale-billing-on-delivery/`. All 18 CRITICAL amendments are applied inline in the affected phases AND summarized here. This addendum is authoritative; if any section below contradicts a later phase description, this addendum wins.

### Amendments — Backend / DM Compliance
1. **Phase 15.3 JE DM-6 fix:** Both JE rows MUST include `reference_type="Stock Entry"` and `reference_name=se.name`. Party omission confirmed acceptable (inventory-only same-company move, no AR/AP). Verify script adds MUST_CONTAIN grep for these fields.
2. **Phase 14 endpoints Sentry + savepoint:** `get_billing_holds`, `release_billing_hold`, `reject_billing_hold`, `reassign_billing_hold_customer` MUST each call `set_backend_observability_context` as first line and wrap mutations in savepoint (`s168_release_hold`, `s168_reject_hold`, `s168_reassign_hold`). Verify script adds MUST_CONTAIN grep for both.
3. **Phase 11 credit note savepoint:** `create_store_sale_credit_note` wraps create+submit+link-back in `savepoint("s168_credit_note")`. Verify script adds MUST_CONTAIN.
4. **Phase 10 approve_billing atomicity:** Extending `approve_billing` to create a fee SI makes it a 2-doc mutation — wrap in `savepoint("s168_approve_billing_si")`. Task 10.4 increment logic wraps in `savepoint("s168_billing_rollup")`. Verify Sentry already exists on `approve_billing`; if not, add.
5. **Phase 5.1 Customer Group precreation:** Before any Customer insert, the seed script MUST ensure `Customer Group "BKI Store"` exists with `parent_customer_group = "All Customer Groups"`, `is_group = 0`. Idempotent via `frappe.db.exists`. Added as Task 5.0.

### Amendments — Code Verifier Corrections
6. **DocType names corrected:** The plan's references to `BEI Delivery Rate` / `BEI Billing Schedule` are WRONG. The actual Frappe DocTypes are **`BEI Delivery Rate`** and **`BEI Billing Schedule`** (verified at `hrms/api/billing.py:280-500`). Phase 10 tasks must use these names.
7. **`Sales Invoice-custom_stock_entry` does NOT exist — must be CREATED:** Phase 1.2 adds this custom field to `hrms/fixtures/custom_field.json`. Plan previously assumed it existed (false).
8. **Store count corrected:** S037 register has **45 active stores covering 35 unique buyer corporations** (not 48 and not 48 corps). `confirmed_legal_entity=42, entity_confirmed_store_type_pending=3, provisional=2, non-operating=1`. Plan references to "48 Customers" are wrong; seed creates **35 Customers** (one per unique corp). Phase 5 audit uses this count.
9. **BEI Settings field reuse:** `BEI Settings` already has `default_ewt_rate`, `ewt_payable_account`, `default_vat_rate`. Phase 13 MUST reuse these, not create new `bki_ewt_*` duplicates. Phase 1 adds only the BKI-specific sale fields: `bki_markup_jv_percent`, `bki_markup_managed_franchise_percent`, `bki_markup_full_franchise_percent`, `bki_sales_vat_template`, `bki_sales_income_account`, `bki_default_incoterm` (new — Finance answer Q1).
10. **`@lru_cache` staleness mitigation:** `load_store_buyer_entity_register` has `@lru_cache(maxsize=1)`. Plan adds Task 2.8: new whitelist endpoint `clear_buyer_entity_cache` (System Manager only) that calls `load_store_buyer_entity_register.cache_clear()`. Documented as the supported way to reload the register after CSV updates without a bench restart.

### Amendments — Execution Governance
11. **Unit total canonical = 114:** Every mention of "111" or "52" is an artifact of earlier drafts. The authoritative total is **114 units** (Session A 54 + Session B 60). User-approved override stands for 114.
12. **Phase 8 checkpoint commit MUST stage all Session A code:** Task 8.2 replaces `git add -f docs/plans/...` with explicit enumeration: `git add hrms/api/commissary.py hrms/api/store.py hrms/hr/doctype/bei_settings/bei_settings.json hrms/fixtures/custom_field.json scripts/s168_*.py scripts/s168_*.sh docs/plans/2026-04-07-sprint-168-*.md`. Add verify step that diff count > 0 before commit.
13. **Session B kickoff — `--resume-from` flag removed:** The `/execute-plan-bei-erp` skill has no `--resume-from` flag. Session B starts with: `/execute-plan-bei-erp docs/plans/2026-04-07-sprint-168-bki-store-sale-billing-on-delivery.md` — the plan's YAML `status: IN_PROGRESS_SESSION_A_COMPLETE` signals the agent to start at Phase 9. Plan text in Session B kickoff instructions updated.
14. **Customer scoping decision = cross-company (name-only match):** ERPNext Customer is multi-company by default. Phase 0.2 audit DROPS the `company="Bebang Kitchen Inc."` filter. Phase 2.4 customer lookup is `frappe.db.get_value("Customer", {"customer_name": buyer_entity_name}, "name")` — exact match on name, no company filter. Per-company behavior handled via `Party Account` child table if/when Finance configures it.
15. **Phase 0 pre-flight for GL accounts:** Add Task 0.6 `scripts/s168_audit_bki_coa.py` (SSM) that queries `tabAccount` for BKI company and writes `output/s168/bki_coa_audit.json` listing the Output VAT account (`2103100 VAT - OUTPUT` per current CoA), the candidate sales income accounts (`4000000 SALES` group plus posting children), and any existing intercompany/B2B sales accounts. Plan stops before Phase 1 if `2103100 VAT - OUTPUT` is missing.
16. **Phase 15 HARD BLOCKER added to `stop_only_for`:** `Autonomous Execution Contract.stop_only_for` now includes: "Phase 15 Task 15.2 Finance decision on same-company reclassification JE pending". Agent is authorized to stop for this item without it being a failure.
17. **Verify script bei-tasks coverage:** `scripts/s168_verify_phases.sh` extended:
   - `phase9()` asserts `bei-tasks/app/dashboard/receiving/[tripName]/page.tsx` contains `delivery_receipt_no` AND `bei-tasks/hooks/use-receiving.ts` passes the param to the backend. **Path confirmed by R2 bei-tasks walk 2026-04-07 PM — `store-ops/receiving/[id]` does NOT exist; real route is `receiving/[tripName]`.**
   - `phase10()` adds `grep` for Task 10.4 idempotency marker + new custom fields `Sales Invoice-custom_bei_store_billing` (Link → BEI Billing Schedule; fee SI traceability) and `BEI Billing Schedule-sales_invoice` (reverse link). **Corrected 2026-04-07 PM (R2-C5): earlier Amendment 17 mis-identified this as a Material Request field — it is a Sales Invoice field tied to L3 scenario 14.**
   - `phase11()` adds assertion on the bei-tasks credit note modal file.
   - `phase14()` adds assertion on `navigation-personas.ts` modification.
   - Phase 8 gate: all prior phase scripts MUST return 0 before Task 8.2 commit.

### Amendments — Finance decisions locked (no questionnaire needed)
18. **All plan-scope Finance decisions are locked inline:**
    - **Incoterm (ICT-007):** **Destination terms.** Revenue recognized when the store signs the Delivery Receipt and accepts the goods. Loss in transit is BKI's. Applies uniformly to all 35 store corporations regardless of store type. Sales Invoice `posting_date` = receiving acceptance date. CEO directive 2026-04-07.
    - **Sales GL account (ICT-008):** Create new sub-account `4000003 SALES - BKI TO STORES` under the `4000000 SALES` group. Configured via `BEI Settings.bki_sales_income_account` — Finance can rename/swap without a code deploy. CEO directive 2026-04-07.
    - **TIN/RDO data:** All 35 active buyer corps in `data/_CONSOLIDATED/01_FINANCE/ENTITY_TIN_RDO_2026-02-27.csv` with exact-name match. 1 corp (Everyday Delight) has blank TIN — correctly excluded, store not operating. Phase 5.1 seed reads this file and populates `Customer.tax_id`, `Customer.territory`, and a new `custom_vat_status` field on the Customer record.
    - **Output VAT GL account:** `2103100 VAT - OUTPUT` (exists in current BKI CoA; verified from `CHART_OF_ACCOUNTS_ERP_COA_2025-12-23.csv`). Phase 5.2 VAT template uses this account.

### Items explicitly OUTSIDE plan scope (Finance owns, not blocking build)
These are Finance/BIR compliance items that live outside the ERP. The plan codes configurable hooks for them but does NOT gate build or deploy on them:

- **BIR Authority to Print (ATP) / Permit to Use (PTU)** — required under RR 18-2012 / RR 6-2022 for every Sales Invoice serial number to fall within a BIR-authorized range. Finance maintains BKI's ATP/PTU. The plan codes a configurable naming series via `BEI Settings.bki_sales_naming_series` (default placeholder `BKI-SI-.YYYY.-.#####`). **Before BKI issues the first production SI**, Finance sets the authorized prefix in BEI Settings to match the current ATP/PTU. This is a Finance deployment-gate, not a build blocker. The plan can be built and merged without it; the system just won't be used in production until Finance sets the authorized series.
- **Transfer Pricing Documentation (TPD)** — required under RR 2-2013 / RR 19-2020 for related-party transactions. Finance / external counsel maintains the TPD for BIR audit defense. The plan does not generate, store, or gate on the TPD. The 2.75% (JV) / 8% (Franchise) markups are locked in ICT-002 and configured via `BEI Settings`; whether those rates are defensible in a BIR audit is a Finance / external counsel question, not an engineering question.

### Amendments — Code bugs in plan text (fix at build time)
- **Phase 3.2 `filters_query` bug:** The spec `frappe.db.get_value("Stock Entry", {...}, "name", filters_query=f"...")` uses a non-existent kwarg. Replace with `frappe.db.sql("SELECT DISTINCT parent FROM \`tabStock Entry Detail\` WHERE material_request=%s AND docstatus=1 LIMIT 1", mr_name, as_list=True)`. No f-string interpolation of user values.
- **Phase 3.1 `_compute_si_row_qty_from_receiving` double-billing risk:** Per-SI-row aggregation (not per-item_code) required when grouped orders produce duplicate item_code rows. Change signature to return `list[dict[row_name→qty]]` not `dict[item_code→qty]`. Rewrite loop in Phase 3.2 uses row.name matching.
- **Stock Entry cancel hook:** Add Task 2.7: register `on_cancel` event on Stock Entry — if SE has `custom_sales_invoice_draft` and that SI is `docstatus=0`, delete the draft SI. Prevents orphan drafts on SE cancellation.

### Amendments deferred / noted (not in-scope for S168)
- BIR separate `Service Invoice` series for delivery/logistics fees (Phase 10.5): use the same Sales Invoice template for v1; flag for Finance follow-up if BIR audit requires separation (W1 finance).
- Zero-rated VAT customer override (`bki_vat_template_override` on Customer): deferred until first zero-rated buyer appears.
- Per-store markup override: deferred; register's `store_type` field drives markup today. When Finance grants a concession, they fork the store's type (documented trade-off, not ideal but acceptable).
- EOPT Law (RA 11976) — Invoice is primary VAT document (not OR): plan already compliant; no change needed.
- Buyer-side SI PDF auto-send (email to `billing_email`): flagged but deferred. Stores accountants receive the SI via manual export for v1.
- Credit note time-limit guard: deferred to v2.
- Phase 13 EWT direction (backend audit W3): current implementation is "BKI withholds from own AR" which is the WRONG direction. Correct implementation is "BKI recognizes EWT received from store via 2307". Since toggle defaults OFF per ICT-004 (not Top 20,000), this is not blocking. Added to Requirements Regression Checklist for execution-time decision.

### Execution Status
**S168 status: GO (2026-04-07 PM — FULL LOCK).** Round 1 + Round 2 amendments applied. ICT-008 locked by Butch to **Option C**: create parent group `4000100 WHOLESALE / B2B SALES` and posting child `4000101 SALES - BKI TO STORES` under root `4000000 SALES`. ICT-009 confirmed by Butch: Output VAT = `2102205 OUTPUT VAT PAYABLE`. Both account codes fact-checked (Layer 1) against `data/_CONSOLIDATED/01_FINANCE/source_documents/COA.csv` on 2026-04-07 PM — `4000100`/`4000101` are confirmed FREE (consistent with existing `4000200`/`4000300` grouping pattern). Finance production-gates (ATP/PTU, TPD) remain explicitly out of scope. **Agent is authorized to begin Phase 0.**

---

## AUDIT ROUND 2 ADDENDUM (2026-04-07, evening) — FACT-CHECK OVERRIDE

A second audit pass covering the 4 domains Round 1 did not include (frontend, deployment/QA, team orchestration, code-verifier re-run on amendments) plus Layer 1 programmatic fact-check of every count claim. Results: **28 CRITICAL / 49 WARNING / 23 INFO** across `output/plan-audit/s168-bki-store-sale-billing-on-delivery/` (`frontend_findings.md`, `deployment_qa_findings.md`, `team_orchestration_findings.md`, `code_verification_amendments.md`, `verified_blockers_round2.md`).

**This Round 2 addendum is authoritative. When it contradicts Round 1 or the phase body, Round 2 wins.**

### Round 2 fact-check results — which Round 1 blockers were real

| Round 2 Blocker | Status | Evidence |
|---|---|---|
| #1 Store/corp count wrong (Round 2 agent said "38 corps / 47 active") | **DISMISSED — agent was wrong** | Layer 1 programmatic count of `store_buyer_entity_register_2026-03-12.csv`: `active_fulfillment_status='active'` = 45 rows, 35 unique `buyer_entity_name`; 2 `active_with_billing_hold` + 1 `excluded` = 3 non-active. Plan claim of "35 corps × 45 active stores; 3 non-operating/provisional excluded" is **CORRECT**. |
| #2 TIN/RDO file mismatch (Round 2 agent said "52 rows ≠ 35") | **DISMISSED — agent was wrong** | Layer 1 programmatic match: TIN file has 52 rows / 40 unique entity names (includes BKI + BEI + non-store entities). **All 35 S037 active buyer entities match exactly** against TIN file Entity Name column. Plan claim of "exact-name match" is **CORRECT**. |
| #3 COA file path + account number wrong | **ESCALATED — two real CRITICALs (see R2-C1 and R2-C2 below)** | Layer 1 grep of actual COA. |
| #4-#10 (frontend paths, roles.ts, Amendment 17 contradiction, Session A→B resume, unit total inconsistency, L3 evidence gate, PR-handoff) | **CONFIRMED as real blockers** | Plan-text review, no re-verification needed. |

### Round 2 CRITICAL blockers — corrected

#### R2-C1 — `2103100 VAT - OUTPUT` was renamed to `2102205 OUTPUT VAT PAYABLE`
ICT-008 and Amendment 15 cite `2103100 VAT - OUTPUT` as the Output VAT GL account. Layer 1 grep of `data/_CONSOLIDATED/01_FINANCE/source_documents/COA.csv` (the actual current COA, not the Round 1 cited path which does not exist at the cited location) shows:
```
2102205,OUTPUT VAT PAYABLE,Balance Sheet,LIABILITY,Sub Account,Credit,Posting,
  "...Change GL Account Number from 2103100 to 2102205",DONE
```
**The 2103100 account number was retired.** The current authoritative Output VAT account is **`2102205 OUTPUT VAT PAYABLE`**.

**Fix:** Phase 0.6 pre-flight, Phase 5.2 VAT template, ICT-008, and Amendment 15 all update to `2102205 OUTPUT VAT PAYABLE`. The COA source path is corrected to `data/_CONSOLIDATED/01_FINANCE/source_documents/COA.csv`.

#### R2-C2 — Account code `4000003` is already taken (ROYALTY INCOME)
ICT-008 (CEO directive 2026-04-07) says: "Create new sub-account `4000003 SALES - BKI TO STORES` under the `4000000 SALES` group". Layer 1 grep of the actual COA shows:
```
4000000,SALES,Grouping
4000001,IN-STORE SALES,Posting
4000002,ONLINE SALES,Posting
4000003,ROYALTY INCOME,Posting    ← ALREADY ALLOCATED
4000004,MANAGEMENT FEE INCOME,Posting
4000005,BRAND GROWTH FEE INCOME,Posting
4000006,MARKETING FEE INCOME,Posting
```
`4000003` is already used for Royalty Income. Creating a second account with the same code will fail Frappe's uniqueness constraint. The CEO directive was issued without reference to the current COA.

**STOP condition triggered (Three-Failure Circuit Breaker not applicable — this is a factual conflict with CEO directive).** Per CLAUDE.md "No Scope Drift — Stop and Ask", the code cannot pick a replacement account unilaterally.

**Proposed fix (requires CEO confirmation before build):**
- **Option A (RECOMMENDED):** Use `4000007 SALES - BKI TO STORES` (next free slot under the 4000000 SALES group, adjacent to IN-STORE/ONLINE SALES).
- **Option B:** Use `4000010 SALES - BKI TO STORES` (round number, leaves slack for future sub-accounts).
- **Option C:** Create under a new group (e.g., `4000100 WHOLESALE / B2B SALES` parent + `4000101 SALES - BKI TO STORES` posting). Cleaner taxonomy but requires two new accounts.

**ICT-008 is hereby marked PENDING CEO RECONFIRMATION.** Phase 0.6 pre-flight script MUST verify the chosen account code is not already posting before Phase 1 runs. `BEI Settings.bki_sales_income_account` must accept the final choice as config — this is why markups and accounts live in BEI Settings, not code.

**Build authorization:** Phases 1-4 can proceed using a placeholder value in `BEI Settings.bki_sales_income_account` (e.g., `4000007 SALES - BKI TO STORES`); before Phase 5.2 seed runs, Sam confirms the final account code with CEO/Finance. The plan does not hard-code the account in any Python file — it reads from BEI Settings at runtime.

### Round 2 CRITICAL blockers — confirmed from Round 1

| ID | Blocker | Fix owner |
|---|---|---|
| R2-C3 | Frontend file paths say "or equivalent" (Phase 9/11/14). Verify script grep cannot match "or equivalent". | Pre-Phase 9 task: walk `F:/Dropbox/Projects/bei-tasks/app/dashboard/store-ops/` and resolve exact paths. Replace every "or equivalent" in phase bodies with concrete file paths + MUST_MODIFY assertions. |
| R2-C4 | `bei-tasks/lib/roles.ts` never updated despite 3 new UI capabilities (DR input, credit note modal, billing holds dashboard). RBAC will silently fail. | Add explicit tasks to Phase 9, 11, 14 that update `roles.ts` and `navigation-personas.ts` with capability names + role assignments. |
| R2-C5 | Amendment 17 promises a `Material Request-custom_bei_store_billing` custom field; Phase 10 body never declares it in `custom_field.json`. | Add the custom field declaration to Phase 1.2 OR remove the assertion from Amendment 17. |
| R2-C6 | Session A→B resume via YAML `status: IN_PROGRESS_SESSION_A_COMPLETE` is unwired. No script writes, reads, or gates on it. | Replace with a sentinel file approach: Session A final task writes `output/s168/SESSION_A_COMPLETE.flag`; Session B kickoff checks it exists. Hard-code Session B start at Phase 9. |
| R2-C7 | Unit total inconsistency (114 vs 111), L3 scenario count inconsistency (8/11/15), duplicate Task 8.3 numbering. | Global search-replace to canonical 114; renumber duplicate. |
| R2-C8 | L3 evidence not git-gated. Verify script accepts handoff doc as proof. Violates S092. | Closeout `completion_condition` adds hard check: `test -f output/l3/s168/form_submissions.json && test -f output/l3/s168/api_mutations.json && test -f output/l3/s168/state_verification.json` + `git add -f output/l3/s168/` step before PR creation. |
| R2-C9 | Closeout self-marks COMPLETED and pushes. Violates PR-Handoff Workflow (agents never merge, Sam merges). No governor feedback loop. | Closeout ends at "PR #N created, awaiting Sam review". Remove any auto status=COMPLETED. Add Governor Feedback Loop section covering REJECT / NEEDS_FIX / merge-conflict rebase / deploy-failure paths. |
| R2-C10 | Phase 15 GL JE has no rollback or defect notification path. Cross-repo (hrms + bei-tasks) commit/PR atomicity undefined. Verify script omits Sentry/savepoint grep on Phase 10/14 endpoints despite Amendment 2. | Add rollback JE definition to Phase 15.3; declare "one PR per repo, same branch name" rule; extend verify script with Sentry + savepoint grep per Phase 10/14 endpoint. |

### Locked decisions — Round 2 updates
- **ICT-008** (2026-04-07 AM → PM FINAL): ~~`4000003 SALES - BKI TO STORES`~~ (collided with existing `ROYALTY INCOME`) → ~~`4000007` build placeholder~~ → **Butch locked Option C (2026-04-07 PM):** create a NEW parent group **`4000100 WHOLESALE / B2B SALES`** under root `4000000 SALES`, and a NEW posting child **`4000101 SALES - BKI TO STORES`** under `4000100`. Rationale: cleaner P&L taxonomy (wholesale/B2B revenue rolls up separately from retail In-Store/Online), durable for future B2B lines (`4000102`, `4000103`…), and better BIR transfer-pricing audit optics. **Fact-checked 2026-04-07 PM:** Layer 1 grep of `data/_CONSOLIDATED/01_FINANCE/source_documents/COA.csv` confirmed `4000100` and `4000101` are both FREE, and the pattern matches existing grouping accounts (`4000200 DISCOUNTS AND PROMO` with posting children `4000201..4000208`; `4000300 FRANCHISE INCOME` with posting children `4000301..4000306`). Stored in `BEI Settings.bki_sales_income_account = "4000101 SALES - BKI TO STORES - BKI"`. Phase 5 Task 5.3 seed script creates BOTH accounts in idempotent order (group first, then posting child).
- **ICT-009** (2026-04-07 PM, NEW): Output VAT GL account is **`2102205 OUTPUT VAT PAYABLE`**, not `2103100 VAT - OUTPUT`. Source: `data/_CONSOLIDATED/01_FINANCE/source_documents/COA.csv` (row shows 2103100 was renamed/renumbered to 2102205). Stored in `BEI Settings.ewt_payable_account` reuse OR new `bki_output_vat_account` field — Phase 1 decides based on Amendment 9 field-reuse rule.

### Build authorization after Round 2
**Conditional GO.** Phases 1-8 (Session A, backend infrastructure) may begin after R2-C3, R2-C5, R2-C6, R2-C7, R2-C9 are amended inline (docs-only edits). Phase 0.6 pre-flight MUST verify the final sales income account code and VAT payable account before Phase 1.

Session B (Phases 9-16) prerequisites — **ALL RESOLVED 2026-04-07 PM**:
1. R2-C3 (real bei-tasks paths) — ✅ bei-tasks walk complete (see R2-C3 Resolution below).
2. R2-C4 (roles.ts tasks) — ✅ exact diffs captured (see R2-C4 Resolution below).
3. ICT-008 final account code — ✅ Butch locked Option C: `4000100 WHOLESALE / B2B SALES` parent + `4000101 SALES - BKI TO STORES` posting child.

---

### R2-C3 Resolution — Confirmed bei-tasks paths (2026-04-07 PM)

The Explore agent walked `F:/Dropbox/Projects/bei-tasks` and confirmed the real file paths. The plan body above has been updated inline; this block is the authoritative record.

| Phase | Surface | Confirmed path | Action | MUST_CONTAIN |
|---|---|---|---|---|
| 9 | DR input on receiving | `bei-tasks/app/dashboard/receiving/[tripName]/page.tsx` | MODIFY — add state + input before checklist (~line 85 + ~line 330); pass `delivery_receipt_no` to `completeReceiving()` call (~line 166) | `"delivery_receipt_no"`, `"const [deliveryReceiptNo"` |
| 9 | Receiving hook | `bei-tasks/hooks/use-receiving.ts` | MODIFY — extend `completeReceiving` mutation to accept `delivery_receipt_no` | `"delivery_receipt_no"` |
| 11 | Credit note modal | `bei-tasks/components/billing/credit-note-modal.tsx` | **CREATE** — reusable dialog with props `{ isOpen, onClose, salesInvoiceName, items[], onSubmit() }` | `"export function CreditNoteModal"` |
| 11 | Trigger button | `bei-tasks/app/dashboard/receiving/[tripName]/page.tsx` | MODIFY — "Request Credit Note" button visible only to `ACCOUNTS_MANAGER` + `SUPPLY_CHAIN_MANAGER` | `"CreditNoteModal"` |
| 11 | Billing hook | `bei-tasks/hooks/use-billing.ts` | MODIFY — add `createStoreSaleCreditNote(salesInvoice, reason, creditLines)` | `"createStoreSaleCreditNote"` |
| 14 | Billing holds dashboard | `bei-tasks/app/dashboard/accounting/billing-holds/page.tsx` | **CREATE** — dedicated route (NOT a tab in `billing/approval`) because holds are draft SIs, separate concern from the existing delivery-fee queue | `"Draft Sales Invoices on Hold"` |
| 14 | API proxy | `bei-tasks/app/api/billing-holds/route.ts` | **CREATE** — GET/POST proxy to the 4 backend endpoints (pattern: `delivery-schedule/route.ts`) | `"get_billing_holds"`, `"release_billing_hold"` |

**Every "or equivalent" placeholder has been replaced in Phase 9, 11, 14 phase bodies.** Verify script phase functions (`phase9`, `phase11`, `phase14`) must be regenerated to match these exact paths in Phase 0 pre-flight.

### R2-C4 Resolution — RBAC wiring (minimal changes)

**Phase 9 DR input:** NO new roles needed. The RECEIVING module already includes `STORE_STAFF`, `STORE_SUPERVISOR`, `WAREHOUSE_USER`, `SUPPLY_CHAIN_MANAGER`, `DRIVER`, `SYSTEM_MANAGER`, `ADMINISTRATOR`. Adding a field to the existing form inherits the existing access.

**Phase 11 Credit note:** Reuse existing BILLING module. Show the "Request Credit Note" button only if user has `ACCOUNTS_MANAGER` or `SUPPLY_CHAIN_MANAGER`. Backend `create_store_sale_credit_note` checks `check_scm_permission()` at runtime. No `roles.ts` change needed.

**Phase 14 Billing holds dashboard:** NEW module required. Exact edits:

`bei-tasks/lib/roles.ts` (around line 205):
```typescript
BILLING_HOLDS: "billing-holds",
```
`bei-tasks/lib/roles.ts` (after line 714, MODULE_ACCESS map):
```typescript
[MODULES.BILLING_HOLDS]: [
  ROLES.ACCOUNTS_MANAGER,
  ROLES.HQ_FINANCE,
  ROLES.SYSTEM_MANAGER,
  ROLES.ADMINISTRATOR,
],
```
`bei-tasks/lib/navigation-personas.ts`: add `MODULES.BILLING_HOLDS` to the `secondary` list in 3 personas:
- `HQ_USER` (~line 387)
- `HQ_SCM_OVERSIGHT` (~line 417)
- `ADMIN` (~line 594)

`bei-tasks/lib/constants.ts` (ROUTES):
```typescript
BILLING_HOLDS: "/dashboard/accounting/billing-holds",
```

Phase 14 Task 14.5 has been aligned with these paths. No invasive refactoring.

### R2-C10 Cross-repo PR atomicity rule

S168 touches TWO repos: `Bebang-Enterprise-Inc/hrms` (backend) and `Bebang-Enterprise-Inc/BEI-Tasks` (frontend Phases 9, 11, 14).

1. **One PR per repo, SAME branch name** — both repos use branch `s168-bki-store-sale-billing-on-delivery`.
2. **Both PR bodies cross-link** each other via explicit GitHub URL: "Companion PR: <url>".
3. **Default merge order: backend (hrms) first, then bei-tasks.** Sam may override.
4. **Neither PR may be merged alone** unless explicitly flagged. The agent writes "DO NOT MERGE alone — requires companion PR #N" in both PR bodies.
5. **Deploy atomicity:** `/deploy-frappe` first, then bei-tasks auto-redeploys on push to production. The short window between deploys is acceptable because the new UI is not yet linked from any production route until the bei-tasks deploy lands.

### Governor Feedback Loop (R2-C9)

After the agent ends at "PR #N (hrms) + PR #M (bei-tasks) awaiting Sam review", it re-enters execution ONLY for these events. In all cases the agent reuses the SAME branch while the PR is under review (per CLAUDE.md "Every New Fix = New Branch" exception: the branch is still active until merge).

**Event: PR REJECT (Sam closes the PR)**
1. Read the PR close comment: `GH_TOKEN="" gh pr view <N> --comments`
2. Summarize in `output/s168/reject_reason.md`
3. STOP and ask Sam whether to rework (new branch) or abandon.

**Event: NEEDS_FIX (Sam leaves review comments, does not merge)**
1. Read every comment: `GH_TOKEN="" gh api repos/<org>/<repo>/pulls/<N>/comments`
2. Apply each suggested fix on the same branch
3. Run `scripts/s168_verify_phases.sh all` — every gate must return 0
4. `git add <specific files> && git commit -m "fix(S168): address PR <N> review"` (never `git add -A`)
5. `git push` (same branch); reply to each comment with the fix SHA
6. Return to "awaiting Sam review". STOP.

**Event: Merge Conflict (production moved, PR becomes UNMERGEABLE)**
1. `git fetch origin production`
2. `git rebase origin/production` (NOT merge)
3. Resolve conflicts manually; NEVER auto-accept either side for shared files (`hrms/fixtures/custom_field.json`, `hrms/api/commissary.py`, `hrms/api/store.py`)
4. Re-run `scripts/s168_verify_phases.sh all` — if any verify fails, the rebase DROPPED code; STOP and ask Sam
5. `git push --force-with-lease` (never `--force`)
6. Return to "awaiting Sam review". STOP.

**Event: Deploy Failure (post-merge, Sam reports deploy error)**
1. Read deploy log from Sam. Frappe: `/deploy-frappe` logs. bei-tasks: Vercel build log.
2. Classify: (a) code error → fix on NEW branch `fix/s168-deploy-<issue>` from `origin/production` (because S168 branch is now merged); (b) config/env error → advise Sam, don't code.
3. Follow standard branch → fix → verify → PR flow.

**Three-Failure Circuit Breaker:** Same fix attempt fails verify 3 times → STOP, summarize failures, ask Sam. Do NOT pivot to a different approach without explicit approval.

### R2-C10 Phase 15.3 rollback path

Phase 15.3 wraps the reclassification JE in a savepoint for DB failures. For **business rollback** (Finance later discovers the reclassification was wrong), the plan adds a whitelist endpoint:

```python
@frappe.whitelist()
def reverse_same_company_reclassification_je(original_je_name: str, reason: str):
    """R2-C10: Cancel a previously-submitted S168 reclassification JE and create
    a reversing entry. Used when Finance finds the reclassification was wrong
    (Frappe JEs are immutable after submit). Only acts on S168-tagged JEs."""
    from hrms.utils.sentry import set_backend_observability_context
    set_backend_observability_context(module="store", action="reverse_same_company_reclassification_je", mutation_type="update")
    original = frappe.get_doc("Journal Entry", original_je_name)
    if "S168 same-company transfer reclassification" not in (original.user_remark or ""):
        frappe.throw("Refusing to reverse: JE is not an S168 reclassification entry.")
    try:
        frappe.db.savepoint("s168_reverse_reclass_je")
        reversing = frappe.new_doc("Journal Entry")
        reversing.voucher_type = "Journal Entry"
        reversing.company = original.company
        reversing.posting_date = frappe.utils.nowdate()
        reversing.user_remark = f"S168 REVERSAL of {original.name}. Reason: {reason}. Original: {original.user_remark}"
        for row in original.accounts:
            reversing.append("accounts", {
                "account": row.account,
                "debit_in_account_currency": row.credit_in_account_currency,
                "credit_in_account_currency": row.debit_in_account_currency,
                "cost_center": row.cost_center,
                "reference_type": row.reference_type,
                "reference_name": row.reference_name,
            })
        reversing.insert(ignore_permissions=True)
        reversing.submit()
        frappe.db.release_savepoint("s168_reverse_reclass_je")
        return reversing.name
    except Exception:
        frappe.db.sql("ROLLBACK TO SAVEPOINT s168_reverse_reclass_je")
        frappe.log_error(f"S168 reversal failed for {original_je_name}: {frappe.get_traceback()}", "S168 Reversal Error")
        raise
```

Phase 15 Task 15.4: Add this endpoint to `hrms/api/store.py`. Verify script phase15 asserts `def reverse_same_company_reclassification_je` exists.

### R2-C10 Verify script Sentry+savepoint grep additions

Phase 0 pre-flight regenerates `scripts/s168_verify_phases.sh` with Sentry + savepoint grep per endpoint. Exact replacement bodies for `phase10()`, `phase11()`, `phase14()` are at `output/plan-audit/s168-bki-store-sale-billing-on-delivery/governance_amendments_draft.md` (R2-C10 Edit 2). The agent MUST copy those function bodies verbatim.

### R2 — Remaining blockers status

| Blocker | Status |
|---|---|
| R2-C1 (2102205 VAT account) | ✅ FIXED — ICT-009 created, Phase 0.6 + 5.2 + Amendment 15 use new account |
| R2-C2 (4000003 collision) | ✅ FIXED — Butch picked Option C (2026-04-07 PM): new group `4000100 WHOLESALE / B2B SALES` + posting `4000101 SALES - BKI TO STORES`. Layer 1 fact-checked against COA — both codes free. |
| R2-C3 (frontend paths) | ✅ FIXED — bei-tasks walk confirmed all 3 paths, phase bodies updated |
| R2-C4 (roles.ts wiring) | ✅ FIXED — exact diffs captured above |
| R2-C5 (custom_bei_store_billing field on Sales Invoice) | ✅ FIXED — field name corrected (was Material Request, is Sales Invoice) in Amendment 17 reference above; Phase 1.2 + verify script need inline adds per `governance_amendments_draft.md` R2-C5 Edit 1-3 |
| R2-C6 (Session A→B sentinel) | ✅ FIXED — Task 8.3 writes `output/s168/SESSION_A_COMPLETE.flag`; Session B kickoff gates on it |
| R2-C7 (unit totals, L3 count, duplicate Task 8.3) | ✅ FIXED — 114/11 canonical, Task 8.3→8.4→8.5 renumbered |
| R2-C8 (L3 evidence git gate) | ✅ FIXED — gate added to both Phase 16 and Closeout section |
| R2-C9 (PR-Handoff + Governor Feedback Loop) | ✅ FIXED — status set to `AWAITING_REVIEW`, Governor Feedback Loop section added above |
| R2-C10 (Phase 15 rollback, cross-repo atomicity, verify script Sentry/savepoint) | ✅ FIXED — rollback endpoint defined, cross-repo rule added, verify script replacement bodies referenced |

### Agent pickup contract after Round 2

The agent reading this plan starts at the **top of the Round 2 Addendum** and treats every "R2-C*" resolution above as authoritative. When in-phase text contradicts the Round 2 addendum, the addendum wins. Before Phase 0 the agent MUST:
1. Read the R2-C3 Resolution table and update `scripts/s168_verify_phases.sh` with the confirmed bei-tasks paths.
2. Read the R2-C10 Verify script section and install the Sentry+savepoint grep assertions.
3. Read the R2-C5 edits in `output/plan-audit/s168-bki-store-sale-billing-on-delivery/governance_amendments_draft.md` and apply them to Phase 1.2 fixtures.
4. ICT-008 final account code: LOCKED to Butch Option C (`4000100` group + `4000101` posting). No further confirmation needed.

---

## Design Rationale (For Cold-Start Agents)

### Why this exists

The existing `_create_intercompany_invoices_async` in `hrms/api/commissary.py` (line 981) implements a **wrong mental model**. It treats BKI→store shipments as ERPNext-internal stock transfers (`is_internal_customer=1`, `make_inter_company_purchase_invoice` helper), but Butch Formoso (CFO) explicitly classified these as **arm's-length sales** between separate BIR-registered legal entities in ICT-001 through ICT-006 on 2026-02-20.

Specifically:
- **BKI (Bebang Kitchen Inc.)** is a separate BIR-registered corporation that manufactures finished goods
- **Each store** is owned by a distinct legal corporation (35 unique buyer corporations covering 45 active store locations, tracked in `data/_CLEANROOM/2026-03-12-s037-store-buyer-entity-register/store_buyer_entity_register_2026-03-12.csv`)
- **The parent holding** is Irrisistable Infusions Inc., but each subsidiary files its own BIR returns
- BKI→store is a **taxable sale** that must be invoiced with **12% VAT** and a proper **Cost Plus markup** per RR 2-2013

Only **two** flows are genuinely intercompany-stock-transfer:
1. BKI commissary ↔ BEI raw material warehouses for **raw material** movements (same conglomerate, same finance treatment)
2. BEI→BEI warehouse transfers (same legal entity)

Finished-goods BKI→store is a **SALE**, not a transfer.

### Why bill on Delivery, not at Fulfillment (CEO directive 2026-04-07)

Current code fires the Sales Invoice when commissary marks a Material Request as fulfilled (`hrms/api/commissary.py::fulfill_store_order` line 864 → `_create_intercompany_invoices_async`). This is wrong because:

1. **Rejections are silent.** If a store rejects items on receiving (wrong qty, damaged, expired), the SI is already submitted. There is no credit-note flow wired to `complete_receiving` rejections.
2. **No legal basis for early revenue recognition.** Under PFRS 15, revenue is recognized when control transfers. Control transfers on delivery and acceptance, not on dispatch.
3. **Stores get billed for goods still in transit.** If a truck breaks down or goods are lost in transit, the store receives an SI for goods it never got.
4. **CEO directive (2026-04-07):** "When done we should be ready to bill the stores on Delivery not fulfillment after the store create the DR and accept everything."

The correct trigger is `complete_receiving` **after** the store signs the Delivery Receipt AND marks items as `Completed` (no outstanding issues). For partial rejections (`status = "With Issues"`), the SI must only cover `received_qty` minus rejected quantity, not `expected_qty`.

### Why we picked this architecture over alternatives

**Option A (chosen): Draft SI at fulfillment, Submit on receiving**
- Commissary fulfillment creates a **Draft** Sales Invoice tied to the Stock Entry
- On `complete_receiving`, the draft is recomputed (received_qty - rejected) and submitted
- Rejected items never appear on the SI
- Pro: legal tax date matches delivery date (BIR happy)
- Pro: rejections handled before SI submission = no credit notes needed
- Con: stores without receiving confirmation stall — but that's already the model for Stock Entry Material Receipt

**Option B (rejected): Submit SI at fulfillment + Credit Note on rejection**
- Creates SI immediately, issues a credit note when store rejects items
- Pro: simpler for the happy path
- Con: double paperwork (SI + CN per rejection), bad BIR optics (many credit notes look like tax evasion), stale "shipped but not received" SIs clutter AR reports, posting-date mismatch

**Option C (rejected): Defer invoice creation entirely to a batch job**
- Pro: simple
- Con: defeats real-time AR, breaks the CFO's ICT-003 requirement of "SI + PI per hub transfer"

### Why markups come from BEI Settings, not Python literals

Current code hardcodes 2.75% (JV) and 8% (Franchise) at `commissary.py` lines 1003–1006. ICT-002 rationale (keeping BKI net taxable income ≤ PHP 5M for 20% CIT eligibility) depends on BKI's annual revenue — if revenue grows past the CIT threshold, Finance will change the JV rate to optimize tax. A rate change should not require a code deploy. Storing in `BEI Settings` single-doctype (new fields: `bki_markup_jv_percent`, `bki_markup_franchise_percent`, `bki_markup_full_franchise_percent`) lets Finance update via Frappe Desk.

### Why we don't use ERPNext's `is_internal_customer` flag

ERPNext has `is_internal_customer` for **intra-group transfers that should be eliminated in consolidation**. It's designed for the case where Company A in a group transfers stock to Company B in the same group, and the parent's consolidated P&L should net them out. This requires a `represents_company` link between the Customer and the sister Company, and the `make_inter_company_purchase_invoice` helper auto-creates the mirror PI using a `Supplier` also marked as `is_internal_supplier`.

**This does not apply to BKI→store.** Store corporations are NOT sister companies in Frappe (they are not `Company` DocType records — there's only BKI and BEI in Frappe per ICT-005). Store corps are regular **external Customers** that happen to share beneficial ownership with BKI. The SI/PI flow for these is identical to any B2B sale: BKI issues an SI, the store corp's Finance team receives and books it against their own AP ledger (which BEI doesn't track — stores file their own BIR returns per ICT-004).

Setting `is_internal_customer=1` silently skips VAT calculation because ERPNext assumes internal transfers are VAT-exempt reclassifications, which is the opposite of what BIR requires here.

### Why we keep using `_get_store_customer` but rewire it

`hrms/api/store.py::_get_store_customer` at line 5105 does a name-based Customer lookup (`customer_name LIKE %store_name%`). This is fragile — it can match the wrong Customer if two names overlap. But a better lookup already exists: `resolve_store_buyer_entity()` in `hrms/utils/supply_chain_contracts.py:201` reads the **S037 register** and returns the correct buyer corporation.

The fix: `_get_store_customer` should call `resolve_store_buyer_entity(warehouse_docname=store)` first, then look up the Customer whose `customer_name` **exactly equals** the `buyer_entity_name` from the register. No `LIKE` matching. If no Customer exists for the buyer entity, throw clearly ("Create Customer 'Bebang Mega Inc' in BKI company before billing can proceed").

### Key trade-off decisions

| Decision | Choice | Rationale |
|---|---|---|
| SI timing | Draft at fulfillment, Submit on receiving | CEO directive; legal tax date correctness |
| PI creation on BEI side | **REMOVED** — stores file their own tax returns per ICT-004 | Stores are separate entities; BEI does not track their AP |
| Markup storage | `BEI Settings` fields, read at runtime | Rate changes = config edit, not deploy |
| Customer resolution | S037 `store_buyer_entity_register` via `resolve_store_buyer_entity` | Authoritative per ICT-005 |
| `is_internal_customer` flag | Set to `0` on all store Customers | They are external per ICT-001 |
| VAT template | Create "BKI Output VAT 12% Sales" template, apply to all store SIs | Required per ICT-001 |
| EWT | None | Per ICT-004, not required |
| Grouped order item rows (S163) | One SI row per (real member SKU, not group code) | Matches multi-row BEI Store Order Item model already live |
| Partial reject handling | Reduce qty on SI draft before submit; no credit note for normal rejects | Simpler, cleaner BIR optics |
| Full reject handling | Cancel the SI draft (never submitted) | No BIR trace of a non-sale |
| Same-company (BEI warehouse→BEI store) | Keep existing Material Transfer — no SI | No legal sale; same entity |
| BKI→BEI raw material warehouse | Keep existing intercompany stock transfer logic | Genuinely intercompany |
| Cost basis for markup | `Stock Entry.basic_rate` (the cost at time of SE creation) | Already in use, matches ICT-006 "cost + markup" |
| Cost fallback | `Item.valuation_rate` when `basic_rate` is 0 | Already in use |

### Known limitations (mitigation inline)

1. **Store corp Customer records may not all exist yet.** Phase 0 includes a data audit to list every store corp that's missing a Customer record in BKI company, and Phase 5 includes the SSM seed script.
2. **Some stores in the register are `provisional_entity_from_pos_master`.** Per the register's `billing_post_policy` field, these must stay in Draft (`DRAFT_ONLY__BILLING_HOLD_PENDING_REGISTER`) until Finance confirms. The SI creation logic must respect this — create the SI as Draft, do not auto-submit, and notify Finance.
3. **`BEI Store Receiving` doesn't currently have a DR number field** — the current code uses `BEI Store Order.dr_number` which is set to the MR name. That's not a real Delivery Receipt number. Phase 4 adds a proper `delivery_receipt_no` field on `BEI Store Receiving` and uses it on the SI header.
4. **`complete_receiving` runs stock posting synchronously** but we cannot block receiving on SI submission — if Finance's BKI chart of accounts has a config error, the store shouldn't be unable to receive goods. The SI submission is attempted synchronously but wrapped in a savepoint — if it fails, stock still posts and a defect ticket is logged.

### Sources for cold-start agents

- CFO Q&A with source quotes: `data/_CLEANROOM/factcheck_packets/commissary_decisions_2026-02-28/sources/CFO_INTERCOMPANY_Butch_Formoso_2026-02-20.md`
- Locked decisions ICT-001 through ICT-006: `data/_CONSOLIDATED/01_FINANCE/DECISIONS.md` (lines 167, 179-184)
- Store-to-corporation register: `data/_CLEANROOM/2026-03-12-s037-store-buyer-entity-register/store_buyer_entity_register_2026-03-12.csv` (49 rows, 48 mapped to legal entities)
- Register README and contract: `data/_CLEANROOM/2026-03-12-s037-store-buyer-entity-register/README.md`
- Store ownership analysis: `data/Valuation/STORE_OWNERSHIP_ANALYSIS.md` (JV 23, Managed Franchise 27, Full Franchise 3, Hybrid 1)
- Existing register loader: `hrms/utils/supply_chain_contracts.py:183-234` (`load_store_buyer_entity_register`, `resolve_store_buyer_entity`, `buyer_entity_requires_billing_hold`)
- Existing broken code: `hrms/api/commissary.py:952-1071` (`_get_store_type_and_customer`, `_create_intercompany_invoices_async`)
- Existing Customer lookup: `hrms/api/store.py:5105-5112` (`_get_store_customer`)
- Receiving flow: `hrms/api/store.py:3899-4099` (`complete_receiving`, `_resolve_store_receiving_contract`, `_create_store_receiving_stock_entry`)
- MR creation with finance treatment: `hrms/api/store.py:3683-3830` (`_create_mr_for_store_order`)
- Commissary fulfillment hook: `hrms/api/commissary.py:782-889` (`fulfill_store_order`)

---

## End-to-End Target Flow (After This Sprint Lands)

```
┌──────────────────────────────────────────────────────────────────────────┐
│ STAGE 1: STORE ORDERS (unchanged)                                        │
│   BEI Store Order submitted → Area Sup approves → MR created            │
└──────────────────────────────────┬───────────────────────────────────────┘
                                   ▼
┌──────────────────────────────────────────────────────────────────────────┐
│ STAGE 2: COMMISSARY FULFILLS                                             │
│   fulfill_store_order creates Stock Entry (Material Transfer)            │
│   ↓                                                                      │
│   NEW: _create_draft_sales_invoice_for_fulfillment(se)                  │
│   - resolves store corp via resolve_store_buyer_entity()                 │
│   - looks up Customer in BKI company matching buyer_entity_name EXACTLY  │
│   - reads markup from BEI Settings (NOT hardcoded)                       │
│   - applies VAT template "BKI Output VAT 12% Sales"                      │
│   - creates Sales Invoice DRAFT (docstatus=0)                            │
│   - links SI ↔ SE via custom_stock_entry and custom_store_order          │
│   - does NOT submit                                                      │
│   - does NOT create Purchase Invoice on BEI side (ICT-004: separate      │
│     tax returns; each store files its own AP ledger)                     │
│   ↓                                                                      │
│   If buyer_entity_requires_billing_hold() returns True:                  │
│     SI stays Draft forever until Finance manually reviews                │
│     (provisional entities, missing register rows, billing holds)         │
└──────────────────────────────────┬───────────────────────────────────────┘
                                   ▼
┌──────────────────────────────────────────────────────────────────────────┐
│ STAGE 3: DELIVERY IN TRANSIT                                             │
│   Trip dispatched, driver signs out, items in transit                    │
│   SI is still a Draft — no GL entry yet, no AR impact                    │
└──────────────────────────────────┬───────────────────────────────────────┘
                                   ▼
┌──────────────────────────────────────────────────────────────────────────┐
│ STAGE 4: STORE RECEIVES (complete_receiving)                             │
│   Store submits receiving form with received_qty per item                │
│   BEI Store Receiving created (status Completed or With Issues)          │
│   Material Receipt Stock Entry posts stock into store inventory         │
│   ↓                                                                      │
│   NEW: _submit_sales_invoice_on_delivery_acceptance(receiving)          │
│   - locates the Draft SI via custom_stock_entry link                    │
│   - recomputes each SI item row:                                         │
│     qty_to_bill = received_qty - rejected_qty                            │
│     (if 0, remove the row; if all 0, cancel the draft SI)                │
│   - applies delivery_receipt_no to SI header                             │
│   - applies posting_date = receiving_date (store acceptance date)        │
│   - submits the SI                                                       │
│   - SI is GL-posted: Dr AR/Store Corp / Cr Sales (BKI) + Cr Output VAT  │
│   - notifies Store Ops Google Chat space on success                      │
│   - if SI submission fails, stock still posts (savepoint preserves it)   │
│     and a defect is logged for Finance                                   │
└──────────────────────────────────┬───────────────────────────────────────┘
                                   ▼
┌──────────────────────────────────────────────────────────────────────────┐
│ STAGE 5: STORE CORP FILES THEIR OWN AP                                   │
│   The store corp's Finance team receives the BKI SI PDF via email/chat   │
│   and books it as AP in their own books. BEI does NOT track store AP    │
│   per ICT-004 (separate legal entities, separate tax returns).           │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## Architecture

### Current (broken) vs target

| Element | Current | Target |
|---|---|---|
| Trigger timing | Fulfillment (commissary SE submit) | Receiving acceptance (store DR sign + no issues) |
| SI company | BKI | BKI (unchanged) |
| Customer resolution | `_get_store_customer` with `customer_name LIKE` | `resolve_store_buyer_entity()` → exact match on `buyer_entity_name` |
| `is_internal_customer` | `1` | `0` |
| VAT template | None | `BKI Output VAT 12% Sales` |
| Markup source | Hardcoded Python literals | `BEI Settings` fields |
| Markup for JV | 2.75% (hardcoded) | 2.75% (configurable, same value per ICT-002) |
| Markup for Franchise | 8% (hardcoded) | 8% (configurable, same value per ICT-002) |
| Mirror PI creation | `make_inter_company_purchase_invoice` (BEI side) | **REMOVED** — stores file own AP |
| SI docstatus on creation | Submitted | Draft |
| SI submission trigger | None | `complete_receiving` acceptance |
| Rejection handling | None (post-hoc) | Reduce SI qty before submit |
| Full reject handling | N/A | Cancel Draft SI |
| Delivery receipt number | Not tracked as distinct field | New `delivery_receipt_no` on `BEI Store Receiving` |
| Billing hold respect | Not checked | `buyer_entity_requires_billing_hold()` gate |

### New DocType additions

1. **`BEI Store Sale Invoice Link`** (child table on `BEI Store Receiving`, optional) — records the SI created from this receiving
2. **Custom Fields on `Sales Invoice`**:
   - `custom_bei_store_order` (Link → BEI Store Order)
   - `custom_bei_stock_entry` (Link → Stock Entry, already exists from commissary.py)
   - `custom_bei_receiving` (Link → BEI Store Receiving, new)
   - `custom_delivery_receipt_no` (Data, new)
3. **Custom Fields on `BEI Store Receiving`**:
   - `delivery_receipt_no` (Data)
   - `sales_invoice` (Link → Sales Invoice)
   - `acceptance_date` (Datetime)
4. **Custom Fields on `BEI Settings`**:
   - `bki_markup_jv_percent` (Float, default 2.75)
   - `bki_markup_managed_franchise_percent` (Float, default 8.0)
   - `bki_markup_full_franchise_percent` (Float, default 8.0)
   - `bki_sales_vat_template` (Link → Sales Taxes and Charges Template)
   - `bki_sales_income_account` (Link → Account, for SI credit posting)

---

## Duplication Audit

| Feature | Classification | Existing Code |
|---|---|---|
| Store → corporation lookup | **[SKIP]** — already works | `resolve_store_buyer_entity()` in `hrms/utils/supply_chain_contracts.py:201`. Used by `_create_mr_for_store_order` already. |
| Store corp CSV register | **[SKIP]** | `data/_CLEANROOM/2026-03-12-s037-store-buyer-entity-register/store_buyer_entity_register_2026-03-12.csv` + loader at `supply_chain_contracts.py:183` |
| `BEI Settings` single DocType | **[EXTEND]** | Already exists; add new markup/VAT fields |
| `Sales Invoice` custom fields | **[EXTEND]** | `custom_stock_entry` likely already exists from commissary.py; add 3 more |
| Draft Sales Invoice creation | **[BUILD]** | No existing "draft at fulfillment" logic |
| Acceptance-time SI submit | **[BUILD]** | No existing "submit on receiving" logic |
| Rejection qty adjustment | **[BUILD]** | No logic that reduces SI rows based on `received_qty - rejected_qty` |
| `_create_intercompany_invoices_async` | **[REPLACE]** | Delete entirely. Logic rewritten into the new fulfillment draft + receiving submit functions. |
| `_get_store_type_and_customer` in commissary.py | **[REPLACE]** | Delete. Replaced by `resolve_store_buyer_entity` which uses the S037 register. |
| `_get_store_customer` in store.py | **[EXTEND]** | Rewire to use `resolve_store_buyer_entity` first, then exact-match Customer lookup |
| VAT template for BKI | **[BUILD]** | No `BKI Output VAT 12% Sales` template exists; Phase 1 creates it |
| Customer records for store corps | **[BUILD]** | 35 Customers need to exist in BKI company matching `buyer_entity_name` exactly; Phase 0 audit + Phase 5 seed |
| `complete_receiving` hook | **[EXTEND]** | Add call to `_submit_sales_invoice_on_delivery_acceptance` after Material Receipt SE creation |
| `BEI Store Receiving` fields | **[EXTEND]** | Add `delivery_receipt_no`, `sales_invoice`, `acceptance_date` custom fields |

---

## Critical Files to Modify

| File | Repo | Phase | Change |
|---|---|---|---|
| `hrms/api/commissary.py` | hrms | 2 | DELETE `_create_intercompany_invoices_async`, DELETE `_get_store_type_and_customer`. REPLACE with `_create_draft_sales_invoice_for_fulfillment`. |
| `hrms/api/store.py` (`_get_store_customer`) | hrms | 2 | Rewire to use `resolve_store_buyer_entity()` first, exact Customer name match |
| `hrms/api/store.py` (`complete_receiving`) | hrms | 4 | Add post-receipt hook: call `_submit_sales_invoice_on_delivery_acceptance(receiving)` |
| `hrms/api/store.py` (new) | hrms | 4 | NEW `_submit_sales_invoice_on_delivery_acceptance` function |
| `hrms/api/store.py` (new) | hrms | 3 | NEW `_compute_si_row_qty_from_receiving(draft_si, receiving)` helper |
| `hrms/hr/doctype/bei_settings/bei_settings.json` | hrms | 1 | Add 5 new fields (3 markups + VAT template + income account) |
| `hrms/fixtures/custom_field.json` | hrms | 1 | Add 3 Sales Invoice custom fields + 3 BEI Store Receiving custom fields |
| `scripts/s168_seed_bki_customers.py` | hrms | 5 | NEW SSM script: ensure a Customer exists in BKI company for every `buyer_entity_name` in the register |
| `scripts/s168_seed_bki_vat_template.py` | hrms | 5 | NEW SSM script: create `BKI Output VAT 12% Sales` template if missing |
| `scripts/s168_audit_missing_customers.py` | hrms | 0 | NEW pre-flight SSM audit — list register entries with no matching Customer in BKI |
| `scripts/s168_verify_phases.sh` | hrms | 0 | NEW phase verification gate script |

---

## Functions That MUST NOT Break

| Function | Location | Why |
|---|---|---|
| `fulfill_store_order` | `commissary.py:782` | Core commissary dispatch — must continue to create the SE and enqueue follow-up tasks. Only the post-SE billing call changes. |
| `complete_receiving` | `store.py:3899` | Store receiving flow — must continue to create BEI Store Receiving doc + Material Receipt SE. Only adds a post-receipt call. |
| `_create_store_receiving_stock_entry` | `store.py:4038` | Stock posting on receipt. Untouched. |
| `_resolve_store_receiving_contract` | `store.py:3982` | Resolves finance treatment for receiving. Untouched. |
| `_create_mr_for_store_order` | `store.py:3683` | MR creation on order approval. Untouched. |
| `resolve_store_buyer_entity` | `supply_chain_contracts.py:201` | Register lookup. Untouched. (Extended callers, not the function itself.) |
| `load_store_buyer_entity_register` | `supply_chain_contracts.py:183` | CSV loader with `@lru_cache`. Untouched. |
| `buyer_entity_requires_billing_hold` | `supply_chain_contracts.py:237` | Billing hold check. Used as a new gate but not modified. |

---

## Shell Prevention (S026)

### Failure patterns to prevent

- **Dead VAT template link:** `BEI Settings.bki_sales_vat_template` is a Link field but the template doesn't exist in the DB. Phase 5 creates it as part of the seed script with an explicit check.
- **Missing Customer records:** SI creation throws at runtime because the store's corp has no Customer in BKI. Phase 0 audit lists all missing customers; Phase 5 seed script creates them; `_create_draft_sales_invoice_for_fulfillment` checks and throws a clear error if still missing.
- **Silent markup fallback:** If `BEI Settings` fields are unset, code falls back to 0% instead of throwing. Forbidden. If the field is unset, throw with "Configure `bki_markup_jv_percent` in BEI Settings before billing."
- **Submit-on-receive fails silently:** If SI submission throws, the stock receipt must still post. The savepoint boundary around SI submission ensures this. Failures write a `BEI Billing Defect` log entry AND notify `SPACE_OPS` Google Chat space.
- **Rejection not honored:** SI gets submitted with original qty instead of `received_qty - rejected_qty`. Gate: L3 scenario 4 verifies the SI line for a rejected item shows the reduced qty.

### Build Integrity Gates

| Gate | Status | Evidence |
|---|---|---|
| `gate_route_contract_defined` | Required | No new routes; extends existing whitelist endpoints |
| `gate_action_wiring_complete` | Required | `fulfill_store_order` → draft SI; `complete_receiving` → submit SI |
| `gate_dependency_map_complete` | Required | Depends on S037 register loader + BEI Settings fields existing before code reads them (Phase 1 before Phase 2) |
| `gate_navigation_placement_defined` | N/A | Backend only; no new frontend pages |
| `gate_empty_error_states_defined` | Required | What shows when no Customer exists, no VAT template exists, or register row is missing — all 3 must throw clear errors |
| `gate_mutation_outcomes_defined` | Required | Draft SI created + linked; SI submitted with receiving ref + acceptance_date set |
| `gate_mobile_layout_defined` | N/A | Backend only |
| `gate_seed_dependency_defined` | Required | 35 BKI-side Customers + 1 VAT template + 5 BEI Settings fields must exist before code goes live |

### Vertical slice first

Phase 2 implements the full end-to-end for **one store** (pick `Araneta Gateway` — already has stock data from S163 testing). Verify draft SI creation + receiving-time submission + VAT math + markup application all work on one store before scaling.

---

## Phase 0: Pre-flight Audit + Branch Reservation

**Estimated units: 4**

### Task 0.1: Reserve sprint and create branch

```
MUST_MODIFY: docs/plans/SPRINT_REGISTRY.md
MUST_CONTAIN: "S168"
MUST_CONTAIN: "s168-bki-store-sale-billing-on-delivery"
```

1. Read this plan fully, including Design Rationale and Requirements Regression Checklist.
2. Read `data/_CLEANROOM/factcheck_packets/commissary_decisions_2026-02-28/sources/CFO_INTERCOMPANY_Butch_Formoso_2026-02-20.md` — all 5 Q&As.
3. Read `data/_CONSOLIDATED/01_FINANCE/DECISIONS.md` lines 167 and 179-184 (BIL-005, ICT-001 through ICT-006).
4. Read `data/_CLEANROOM/2026-03-12-s037-store-buyer-entity-register/README.md` and `store_buyer_entity_register_2026-03-12.csv`.
5. Read `hrms/utils/supply_chain_contracts.py:180-248` — the register loader.
6. **Create branch:** `git fetch origin production && git checkout -b s168-bki-store-sale-billing-on-delivery origin/production`. Verify with `git branch --show-current`. NEVER write code on production.
7. Registry row must already exist from pre-plan reservation — verify with `grep S168 docs/plans/SPRINT_REGISTRY.md`.

### Task 0.2: Audit missing BKI Customer records

```
MUST_CREATE: scripts/s168_audit_missing_customers.py
MUST_CREATE: output/s168/missing_customers_audit.json
```

Write and run a Python SSM script that:
1. Loads the S037 register via `load_store_buyer_entity_register()`
2. For each row with `buyer_entity_status IN ('confirmed_legal_entity', 'entity_confirmed_store_type_pending')`, queries `frappe.db.exists("Customer", {"customer_name": row["buyer_entity_name"], "company": "Bebang Kitchen Inc."})` (or the nearest match without company filter if Customer is not multi-company)
3. Outputs a JSON with: total register rows, rows needing billing, existing customers found, missing customers (list of buyer_entity_name), per-store breakdown

Pattern: use `scripts/s163_run_ssm_ops.py` and `scripts/s163_ssm_ops.py` as the template. Copy the SSM runner pattern.

### Task 0.3: Audit current VAT template state

```
MUST_CREATE: output/s168/vat_template_audit.json
```

SSM script that lists existing `Sales Taxes and Charges Template` records where `company = 'Bebang Kitchen Inc.'`. Writes audit JSON showing whether `BKI Output VAT 12% Sales` (or similar) already exists. If found, capture its structure (account, rate). If not, note that Phase 5 must create it.

### Task 0.4: Capture receiving flow baseline

```
MUST_CREATE: output/s168/receiving_flow_baseline.json
```

SSM query to document: how many `BEI Store Receiving` records exist, how many are `Completed`, how many are `With Issues`, how many have a `stock_entry` link populated. This is the before-snapshot for Phase 4's verification.

### Task 0.5: Write phase verification script

```
MUST_CREATE: scripts/s168_verify_phases.sh
```

Bash verification script checking MUST_MODIFY/MUST_CONTAIN assertions per phase. Run with `bash scripts/s168_verify_phases.sh <phase_number|all>` after each phase. Pattern: `scripts/s163_verify_phases.sh` as template.

---

## Phase 1: DocType Schema Extensions

**Estimated units: 6**

### Task 1.1: Add `BEI Settings` fields

```
MUST_MODIFY: hrms/hr/doctype/bei_settings/bei_settings.json
MUST_CONTAIN: "bki_markup_jv_percent"
MUST_CONTAIN: "bki_markup_managed_franchise_percent"
MUST_CONTAIN: "bki_markup_full_franchise_percent"
MUST_CONTAIN: "bki_sales_vat_template"
MUST_CONTAIN: "bki_sales_income_account"
```

Add to `BEI Settings` DocType JSON:

```json
{
  "fieldname": "section_break_bki_billing",
  "fieldtype": "Section Break",
  "label": "BKI → Store Billing (S168)",
  "collapsible": 1
},
{
  "fieldname": "bki_markup_jv_percent",
  "fieldtype": "Float",
  "label": "BKI Markup % — JV Stores",
  "default": "2.75",
  "precision": "4",
  "description": "Markup % applied to BKI→JV store sales (ICT-002). Default 2.75% keeps BKI net taxable income ≤ PHP 5M for 20% CIT eligibility."
},
{
  "fieldname": "bki_markup_managed_franchise_percent",
  "fieldtype": "Float",
  "label": "BKI Markup % — Managed Franchise",
  "default": "8.0",
  "precision": "4",
  "description": "Markup % applied to BKI→Managed Franchise store sales (ICT-002, BIL-005)."
},
{
  "fieldname": "bki_markup_full_franchise_percent",
  "fieldtype": "Float",
  "label": "BKI Markup % — Full Franchise",
  "default": "8.0",
  "precision": "4",
  "description": "Markup % applied to BKI→Full Franchise store sales (ICT-002, BIL-005)."
},
{
  "fieldname": "bki_sales_vat_template",
  "fieldtype": "Link",
  "options": "Sales Taxes and Charges Template",
  "label": "BKI Sales VAT Template",
  "description": "Tax template applied to BKI→store Sales Invoices. Must be a 12% Output VAT template (ICT-001)."
},
{
  "fieldname": "bki_sales_income_account",
  "fieldtype": "Link",
  "options": "Account",
  "label": "BKI Sales Income Account",
  "description": "GL account used for the credit line on BKI→store Sales Invoices (e.g., Sales — BKI)."
}
```

**HARD BLOCKER:** None of these may be `reqd: 1` — existing BEI Settings loads must not break. Runtime code checks for `None` and throws clearly.

### Task 1.2: Add Sales Invoice custom fields via fixtures

```
MUST_MODIFY: hrms/fixtures/custom_field.json
MUST_CONTAIN: "Sales Invoice-custom_bei_store_order"
MUST_CONTAIN: "Sales Invoice-custom_bei_receiving"
MUST_CONTAIN: "Sales Invoice-custom_delivery_receipt_no"
```

Add to `custom_field.json`:

```json
{
  "doctype": "Custom Field",
  "name": "Sales Invoice-custom_bei_store_order",
  "dt": "Sales Invoice",
  "fieldname": "custom_bei_store_order",
  "fieldtype": "Link",
  "options": "BEI Store Order",
  "label": "BEI Store Order",
  "insert_after": "customer",
  "read_only": 1,
  "description": "S168: The BEI Store Order this SI was generated for."
},
{
  "doctype": "Custom Field",
  "name": "Sales Invoice-custom_bei_receiving",
  "dt": "Sales Invoice",
  "fieldname": "custom_bei_receiving",
  "fieldtype": "Link",
  "options": "BEI Store Receiving",
  "label": "BEI Store Receiving",
  "insert_after": "custom_bei_store_order",
  "read_only": 1,
  "description": "S168: The store receiving doc whose acceptance triggered SI submission."
},
{
  "doctype": "Custom Field",
  "name": "Sales Invoice-custom_delivery_receipt_no",
  "dt": "Sales Invoice",
  "fieldname": "custom_delivery_receipt_no",
  "fieldtype": "Data",
  "label": "DR No.",
  "insert_after": "custom_bei_receiving",
  "description": "S168: Store-issued Delivery Receipt number at acceptance time."
}
```

If `custom_stock_entry` doesn't already exist on Sales Invoice (verify by grep on current file), add it too.

### Task 1.3: Add BEI Store Receiving custom fields

```
MUST_MODIFY: hrms/fixtures/custom_field.json
MUST_CONTAIN: "BEI Store Receiving-delivery_receipt_no"
MUST_CONTAIN: "BEI Store Receiving-sales_invoice"
MUST_CONTAIN: "BEI Store Receiving-acceptance_date"
```

```json
{
  "doctype": "Custom Field",
  "name": "BEI Store Receiving-delivery_receipt_no",
  "dt": "BEI Store Receiving",
  "fieldname": "delivery_receipt_no",
  "fieldtype": "Data",
  "label": "DR No.",
  "insert_after": "trip",
  "description": "S168: Delivery Receipt number issued by the store on acceptance."
},
{
  "doctype": "Custom Field",
  "name": "BEI Store Receiving-sales_invoice",
  "dt": "BEI Store Receiving",
  "fieldname": "sales_invoice",
  "fieldtype": "Link",
  "options": "Sales Invoice",
  "label": "Sales Invoice",
  "insert_after": "stock_entry",
  "read_only": 1,
  "description": "S168: BKI Sales Invoice submitted on store acceptance."
},
{
  "doctype": "Custom Field",
  "name": "BEI Store Receiving-acceptance_date",
  "dt": "BEI Store Receiving",
  "fieldname": "acceptance_date",
  "fieldtype": "Datetime",
  "label": "Acceptance Date",
  "insert_after": "receiving_date",
  "description": "S168: Timestamp when the store accepted the delivery (SI posting date)."
}
```

### Task 1.4: Run `bench migrate`

After all fixture changes are committed, the executing user (Sam) runs `bench --site hq.bebang.ph migrate` via SSM. Verify with SSM query:

```python
frappe.db.sql("SELECT fieldname FROM `tabCustom Field` WHERE dt='Sales Invoice' AND fieldname LIKE 'custom_bei%'")
```

---

## Phase 2: Fulfillment-Time Draft SI Creation

**Estimated units: 10**

### Task 2.1: Rewire `_get_store_customer` in store.py

```
MUST_MODIFY: hrms/api/store.py
MUST_CONTAIN: "resolve_store_buyer_entity"
MUST_NOT_CONTAIN_REGEX: "customer_name.*LIKE.*%"
```

Replace the existing `_get_store_customer` at line 5105 with:

```python
def _get_store_customer(store: str) -> str:
    """S168: Get the Customer linked to a store's legal buyer entity.

    Uses the S037 store_buyer_entity_register (ICT-005) to resolve the correct
    legal corporation, then looks up the Customer in Frappe whose customer_name
    EXACTLY matches the buyer_entity_name. No LIKE matching — the register is
    authoritative.
    """
    if not store:
        frappe.throw(_("Store is required"))
    entity_row = resolve_store_buyer_entity(warehouse_docname=store)
    buyer_entity_name = (entity_row.get("buyer_entity_name") or "").strip()
    if not buyer_entity_name:
        frappe.throw(
            _(
                "Store {0} has no buyer entity in the S037 register. "
                "Add a row to data/_CLEANROOM/2026-03-12-s037-store-buyer-entity-register/ "
                "before billing can proceed."
            ).format(store)
        )
    customer = frappe.db.get_value("Customer", {"customer_name": buyer_entity_name}, "name")
    if not customer:
        frappe.throw(
            _(
                "No Customer record found for buyer entity '{0}' (store: {1}). "
                "Run scripts/s168_seed_bki_customers.py to create missing Customers."
            ).format(buyer_entity_name, store)
        )
    return customer
```

### Task 2.2: DELETE `_get_store_type_and_customer` from commissary.py

```
MUST_MODIFY: hrms/api/commissary.py
MUST_NOT_CONTAIN: "def _get_store_type_and_customer"
```

This function is superseded by `resolve_store_buyer_entity` which reads the authoritative register. Any callers must be rewired in the same commit.

### Task 2.3: DELETE `_create_intercompany_invoices_async` from commissary.py

```
MUST_MODIFY: hrms/api/commissary.py
MUST_NOT_CONTAIN: "def _create_intercompany_invoices_async"
MUST_NOT_CONTAIN: "make_inter_company_purchase_invoice"
MUST_NOT_CONTAIN: "is_internal_customer = 1"
```

Remove the entire function and its enqueue call in `fulfill_store_order` at line 864. The replacement is implemented in Task 2.4 and called synchronously (not enqueued) so that failures are visible in the same transaction.

### Task 2.4: NEW `_create_draft_sales_invoice_for_fulfillment`

```
MUST_MODIFY: hrms/api/commissary.py
MUST_CONTAIN: "def _create_draft_sales_invoice_for_fulfillment"
MUST_CONTAIN: "bki_markup_jv_percent"
MUST_CONTAIN: "bki_sales_vat_template"
MUST_CONTAIN: "resolve_store_buyer_entity"
MUST_CONTAIN: "buyer_entity_requires_billing_hold"
MUST_CONTAIN: "set_backend_observability_context"
MUST_CONTAIN: 'sales_invoice.is_internal_customer = 0'
```

```python
def _create_draft_sales_invoice_for_fulfillment(
    stock_entry: "StockEntry",
    store_order_name: str | None = None,
) -> str | None:
    """S168: Create a Draft Sales Invoice at commissary fulfillment time.

    The SI stays Draft until the store signs the DR and accepts via
    complete_receiving. This function does NOT submit the SI and does NOT
    create a mirror Purchase Invoice — per ICT-004 stores file their own
    tax returns independently.

    Returns the SI name, or None if the store is on billing hold or no
    billing is required.
    """
    from hrms.utils.sentry import set_backend_observability_context

    set_backend_observability_context(
        module="commissary",
        action="create_draft_sales_invoice_for_fulfillment",
        mutation_type="create",
    )

    target_warehouse = stock_entry.to_warehouse
    entity_row = resolve_store_buyer_entity(warehouse_docname=target_warehouse)

    # Respect billing holds (provisional entities, missing register rows)
    if buyer_entity_requires_billing_hold(entity_row):
        frappe.log_error(
            f"S168: billing hold for {target_warehouse} ({entity_row.get('buyer_entity_status')}); SI not created",
            "S168 Billing Hold",
        )
        return None

    buyer_entity_name = (entity_row.get("buyer_entity_name") or "").strip()
    store_type = (entity_row.get("store_type") or "").strip()
    if not buyer_entity_name:
        frappe.throw(
            _("Store {0} has no buyer entity configured; cannot create SI").format(target_warehouse)
        )

    bki_company = "Bebang Kitchen Inc."
    if not frappe.db.exists("Company", bki_company):
        frappe.throw(_("BKI company does not exist in Frappe (ICT-005)"))

    # Resolve Customer by exact name match
    customer = frappe.db.get_value("Customer", {"customer_name": buyer_entity_name}, "name")
    if not customer:
        frappe.throw(
            _(
                "No Customer '{0}' found in Frappe (store: {1}). "
                "Run scripts/s168_seed_bki_customers.py to create missing Customers."
            ).format(buyer_entity_name, target_warehouse)
        )

    # Read markup from BEI Settings
    settings = frappe.get_single("BEI Settings")
    markup_by_type = {
        "JV": flt(settings.bki_markup_jv_percent or 0) / 100,
        "Managed Franchise": flt(settings.bki_markup_managed_franchise_percent or 0) / 100,
        "Full Franchise": flt(settings.bki_markup_full_franchise_percent or 0) / 100,
    }
    markup_rate = markup_by_type.get(store_type)
    if markup_rate is None:
        frappe.throw(
            _(
                "Unknown store_type '{0}' for {1}. Configure markup in BEI Settings or "
                "fix the register row."
            ).format(store_type, target_warehouse)
        )

    # Read VAT template
    vat_template = (settings.bki_sales_vat_template or "").strip()
    if not vat_template:
        frappe.throw(
            _(
                "BEI Settings.bki_sales_vat_template is not set. Cannot create SI without "
                "12% VAT template (ICT-001)."
            )
        )

    income_account = (settings.bki_sales_income_account or "").strip()
    if not income_account:
        frappe.throw(
            _("BEI Settings.bki_sales_income_account is not set. Cannot create SI.")
        )

    # Build the SI
    si = frappe.new_doc("Sales Invoice")
    si.company = bki_company
    si.customer = customer
    si.is_internal_customer = 0  # EXTERNAL sale per ICT-001
    si.posting_date = stock_entry.posting_date
    si.set_posting_time = 1
    si.currency = frappe.db.get_value("Company", bki_company, "default_currency") or "PHP"
    si.taxes_and_charges = vat_template
    si.custom_bei_store_order = store_order_name
    si.custom_bei_stock_entry = stock_entry.name
    si.remarks = (
        f"S168: Draft SI for BKI→{buyer_entity_name} sale. "
        f"Store: {target_warehouse} ({store_type}). Stock Entry: {stock_entry.name}. "
        f"Markup: {markup_rate*100:.2f}%. Will be submitted on store DR acceptance."
    )

    for se_item in stock_entry.items:
        base_price = flt(se_item.basic_rate)
        if not base_price:
            base_price = flt(frappe.db.get_value("Item", se_item.item_code, "valuation_rate"))
        if base_price <= 0:
            frappe.throw(
                _("Item {0} has no basic_rate or valuation_rate; cannot price SI").format(
                    se_item.item_code
                )
            )
        selling_price = flt(base_price * (1 + markup_rate), 4)
        si.append(
            "items",
            {
                "item_code": se_item.item_code,  # ALWAYS real SKU (S163)
                "qty": se_item.qty,
                "rate": selling_price,
                "income_account": income_account,
                "warehouse": stock_entry.to_warehouse,
                "cost_center": frappe.db.get_value("Company", bki_company, "cost_center"),
            },
        )

    # Fetch taxes from template
    from erpnext.controllers.accounts_controller import get_taxes_and_charges
    taxes = get_taxes_and_charges("Sales Taxes and Charges Template", vat_template)
    for tax in taxes:
        si.append("taxes", tax)

    si.insert(ignore_permissions=True)
    # DO NOT submit. SI stays Draft until complete_receiving.
    return si.name
```

### Task 2.5: Wire the new draft-SI call into `fulfill_store_order`

```
MUST_MODIFY: hrms/api/commissary.py
MUST_CONTAIN: "_create_draft_sales_invoice_for_fulfillment"
MUST_CONTAIN: 'frappe.db.savepoint("s168_draft_si"'
```

Replace the old `frappe.enqueue(...)` block (lines 862-874) with:

```python
# S168: Create Draft Sales Invoice synchronously so failures surface with the SE.
# The SI stays Draft until the store signs the DR at complete_receiving time.
try:
    frappe.db.savepoint("s168_draft_si")
    store_order_name = frappe.db.get_value("Material Request", mr_name, "custom_store_order")
    si_name = _create_draft_sales_invoice_for_fulfillment(
        stock_entry=se,
        store_order_name=store_order_name,
    )
    if si_name:
        frappe.db.set_value("Stock Entry", se.name, "custom_sales_invoice_draft", si_name)
    frappe.db.release_savepoint("s168_draft_si")
except Exception as e:
    frappe.db.sql("ROLLBACK TO SAVEPOINT s168_draft_si")
    frappe.log_error(
        f"S168: Draft SI creation failed for SE {se.name}: {frappe.get_traceback()}",
        "S168 Draft SI Error",
    )
    # DO NOT raise — fulfillment must not block on billing errors.
    # Finance is notified via log_error and can manually create the SI.
```

**HARD BLOCKER:** The SI creation must NOT fail fulfillment. If SI creation fails, stock transfer still succeeds, error is logged, and Finance is notified via Google Chat.

### Task 2.6: Add `custom_sales_invoice_draft` field to Stock Entry

```
MUST_MODIFY: hrms/fixtures/custom_field.json
MUST_CONTAIN: "Stock Entry-custom_sales_invoice_draft"
```

Link field on Stock Entry so receiving can find the draft SI to submit.

---

## Phase 3: Receiving-Time SI Submission

**Estimated units: 10**

### Task 3.1: NEW `_compute_si_row_qty_from_receiving` helper

```
MUST_MODIFY: hrms/api/store.py
MUST_CONTAIN: "def _compute_si_row_qty_from_receiving"
```

Helper that takes a Draft SI and a `BEI Store Receiving` doc and returns a map `{item_code: qty_to_bill}` where `qty_to_bill = received_qty - rejected_qty`. Items with zero billable qty get dropped.

```python
def _compute_si_row_qty_from_receiving(
    draft_si_name: str,
    receiving_doc,
) -> dict[str, float]:
    """S168: For each SI item, compute qty_to_bill = received_qty - rejected_qty.

    Called before SI submission at complete_receiving time. If a line has
    received_qty == 0 or all rejected, the SI row is removed. If the entire
    SI has no billable rows, the caller cancels the draft.
    """
    qty_by_item: dict[str, float] = defaultdict(float)
    for ri in receiving_doc.items:
        received = flt(ri.received_qty or 0)
        rejected = flt(getattr(ri, "rejected_qty", 0) or 0)
        billable = max(0.0, received - rejected)
        if billable > 0:
            qty_by_item[ri.item_code] += billable
    return dict(qty_by_item)
```

### Task 3.2: NEW `_submit_sales_invoice_on_delivery_acceptance`

```
MUST_MODIFY: hrms/api/store.py
MUST_CONTAIN: "def _submit_sales_invoice_on_delivery_acceptance"
MUST_CONTAIN: 'frappe.db.savepoint("s168_submit_si"'
MUST_CONTAIN: "set_backend_observability_context"
```

```python
def _submit_sales_invoice_on_delivery_acceptance(receiving_doc) -> str | None:
    """S168: Locate the Draft SI for this delivery, adjust qty for rejections,
    set acceptance date, and submit.

    Called from complete_receiving after the Material Receipt SE is created.
    Wrapped in a savepoint — SI submission failure must NOT block the stock
    posting that already succeeded.

    Returns the submitted SI name, or None if no SI exists (billing hold,
    same-company, etc.).
    """
    from hrms.utils.sentry import set_backend_observability_context

    set_backend_observability_context(
        module="store_billing",
        action="submit_sales_invoice_on_delivery_acceptance",
        mutation_type="submit",
    )

    # Locate the Draft SI via the Stock Entry chain:
    # Receiving → Trip → Material Request → Stock Entry (Material Transfer) → SI
    trip = receiving_doc.trip
    if not trip:
        return None

    # Find the fulfillment SE for this trip+store
    mr_name = None
    if frappe.db.exists("DocType", "BEI Trip Stop"):
        store_order = frappe.db.get_value(
            "BEI Trip Stop",
            {"parent": trip, "store": receiving_doc.store},
            "store_order",
        )
        if store_order:
            mr_name = frappe.db.get_value(
                "Material Request",
                {"custom_store_order": store_order, "docstatus": 1},
                "name",
                order_by="creation desc",
            )
    if not mr_name:
        return None

    # S168 audit fix: use parameterized SQL, not filters_query (not a valid kwarg)
    # and never interpolate mr_name via f-string (injection risk)
    fulfillment_se_rows = frappe.db.sql(
        """
        SELECT DISTINCT sed.parent
        FROM `tabStock Entry Detail` sed
        JOIN `tabStock Entry` se ON se.name = sed.parent
        WHERE sed.material_request = %s
          AND se.purpose = 'Material Transfer'
          AND se.docstatus = 1
        ORDER BY se.creation DESC
        LIMIT 1
        """,
        (mr_name,),
        as_list=True,
    )
    fulfillment_se_name = fulfillment_se_rows[0][0] if fulfillment_se_rows else None
    if not fulfillment_se_name:
        return None

    draft_si_name = frappe.db.get_value("Stock Entry", fulfillment_se_name, "custom_sales_invoice_draft")
    if not draft_si_name:
        return None
    if not frappe.db.exists("Sales Invoice", draft_si_name):
        return None

    try:
        frappe.db.savepoint("s168_submit_si")
        si = frappe.get_doc("Sales Invoice", draft_si_name)
        if si.docstatus != 0:
            # Already submitted or cancelled; nothing to do
            frappe.db.release_savepoint("s168_submit_si")
            return si.name if si.docstatus == 1 else None

        # Recompute qty from receiving
        qty_by_item = _compute_si_row_qty_from_receiving(draft_si_name, receiving_doc)

        if not qty_by_item:
            # All items rejected — cancel the draft (nothing to bill)
            si.delete(ignore_permissions=True)
            frappe.db.release_savepoint("s168_submit_si")
            return None

        # Adjust SI rows
        new_items = []
        for row in si.items:
            billable = qty_by_item.get(row.item_code, 0)
            if billable > 0:
                row.qty = billable
                new_items.append(row)
        si.items = new_items

        # Set acceptance metadata
        si.custom_bei_receiving = receiving_doc.name
        si.custom_delivery_receipt_no = getattr(receiving_doc, "delivery_receipt_no", None) or ""
        si.posting_date = frappe.utils.getdate(receiving_doc.receiving_date)
        si.set_posting_time = 1

        si.save(ignore_permissions=True)
        si.submit()
        frappe.db.release_savepoint("s168_submit_si")
        return si.name
    except Exception:
        frappe.db.sql("ROLLBACK TO SAVEPOINT s168_submit_si")
        frappe.log_error(
            f"S168: SI submission failed for receiving {receiving_doc.name}: {frappe.get_traceback()}",
            "S168 Submit SI Error",
        )
        # Notify Finance/Store Ops — stock still posted, billing did not
        _notify_billing_defect(receiving_doc.name, draft_si_name)
        return None
```

### Task 3.3: NEW `_notify_billing_defect` helper

```
MUST_MODIFY: hrms/api/store.py
MUST_CONTAIN: "def _notify_billing_defect"
```

Simple Google Chat notification to `SPACE_OPS` (or a new `SPACE_FINANCE` space) listing the failed SI and receiving, so Finance can investigate. Catch all exceptions — notification must not block receiving.

---

## Phase 4: Wire complete_receiving to Submit SI

**Estimated units: 6**

### Task 4.1: Call `_submit_sales_invoice_on_delivery_acceptance` in `complete_receiving`

```
MUST_MODIFY: hrms/api/store.py
MUST_CONTAIN: "_submit_sales_invoice_on_delivery_acceptance(receiving)"
```

In `complete_receiving` at line 3899, after `_create_store_receiving_stock_entry`, add:

```python
# S168: Submit the Draft SI that was created at fulfillment time, adjusting
# qty for rejections. The SE posting has already succeeded — SI submission
# failures must not retroactively block receiving.
receiving.acceptance_date = now_datetime()
receiving.save(ignore_permissions=True)
si_name = _submit_sales_invoice_on_delivery_acceptance(receiving)
if si_name and _has_column("BEI Store Receiving", "sales_invoice"):
    receiving.sales_invoice = si_name
    receiving.save(ignore_permissions=True)
    result["sales_invoice"] = si_name
```

### Task 4.2: Ensure `delivery_receipt_no` can be passed from the frontend

```
MUST_MODIFY: hrms/api/store.py
```

Add `delivery_receipt_no` as an optional kwarg on `complete_receiving`:

```python
def complete_receiving(
    store: str,
    trip: str,
    items: list | str,
    receiver_1_signature: str | None = None,
    receiver_2_signature: str | None = None,
    driver_signature: str | None = None,
    delivery_receipt_no: str | None = None,  # S168
) -> dict:
```

Persist it on the `BEI Store Receiving` doc if the column exists (via `_has_column` guard for backwards compat).

### Task 4.3: Document the frontend contract change

Add a note in the plan closeout section that the store receiving UI (`../bei-tasks/app/dashboard/store-ops/receiving/...`) should pass `delivery_receipt_no` if the store staff enters one. This is an optional follow-up — the SI will still submit without a DR number (it's a nice-to-have for BIR audit trail).

**NOTE:** This plan does NOT include the frontend UI change. It's a backend-only sprint. The frontend addition of a DR number input field is deferred to a follow-up sprint or included as a small addendum if the user wants it in scope.

---

## Phase 5: Seed Customers + VAT Template + BEI Settings

**Estimated units: 8**

### Task 5.0: Ensure Customer Group "BKI Store" exists (HARD BLOCKER before Task 5.1)

```
MUST_CREATE: scripts/s168_seed_bki_customers.py
MUST_CONTAIN: "BKI Store"
MUST_CONTAIN: "All Customer Groups"
```

**HARD BLOCKER:** ERPNext requires the Customer Group to exist before any Customer can reference it via `customer_group`. Code verifier confirmed (2026-04-07) that the group "BKI Store" does NOT exist anywhere in the repo or in production. The seed script MUST precreate it as its first action:

```python
if not frappe.db.exists("Customer Group", "BKI Store"):
    cg = frappe.new_doc("Customer Group")
    cg.customer_group_name = "BKI Store"
    cg.parent_customer_group = "All Customer Groups"
    cg.is_group = 0
    cg.insert(ignore_permissions=True)
```

Also verify a default Territory exists (`frappe.db.exists("Territory", "Philippines")` or the BEI default). If missing, throw with a clear error directing Finance to create it first — do NOT auto-create territories.

### Task 5.1: Seed BKI Customer records for the 35 active buyer corporations

```
MUST_CREATE: scripts/s168_seed_bki_customers.py
MUST_CREATE: output/s168/seed_customers_evidence.json
MUST_CONTAIN: "ENTITY_TIN_RDO_2026-02-27.csv"
MUST_CONTAIN: "tax_id"
```

SSM script that:
1. Reads the S037 register (`data/_CLEANROOM/2026-03-12-s037-store-buyer-entity-register/store_buyer_entity_register_2026-03-12.csv`) — filter to rows with `buyer_entity_status IN ('confirmed_legal_entity', 'entity_confirmed_store_type_pending')`. Expected count: **35 unique buyer corporations** (verified 2026-04-07).
2. Reads the TIN/RDO file (`data/_CONSOLIDATED/01_FINANCE/ENTITY_TIN_RDO_2026-02-27.csv`) and builds a lookup from `Entity Name` → `(TIN, RDO Code, VAT Status)`.
3. For each unique `buyer_entity_name`, creates a `Customer` with:
   - `customer_name` = exact `buyer_entity_name` from register
   - `customer_type` = "Company"
   - `customer_group` = "BKI Store" (precreated in Task 5.0)
   - `territory` = default BEI territory
   - `is_internal_customer` = **0** (external per ICT-001)
   - `tax_id` = TIN from the TIN/RDO file (REQUIRED — fail if the corp is not in the file with a non-blank TIN)
   - `custom_vat_status` = VAT Status from the TIN/RDO file (new custom field added by Phase 1)
   - `custom_bir_rdo_code` = RDO Code from the TIN/RDO file (new custom field added by Phase 1)

Idempotent via `frappe.db.exists` check. The 1 known exception is `Everyday Delight Food Ventures Inc.` which has a blank TIN in the TIN/RDO file (store not yet operating) — skip with a WARNING, not a FAIL. Write evidence JSON with created/skipped counts + any TIN lookup failures.

### Task 5.2: Seed `BKI Output VAT 12% Sales` template

```
MUST_CREATE: scripts/s168_seed_bki_vat_template.py
MUST_CREATE: output/s168/seed_vat_template_evidence.json
```

SSM script that creates a `Sales Taxes and Charges Template` with:
- `name` = "BKI Output VAT 12% Sales"
- `company` = "Bebang Kitchen Inc."
- One tax row: `charge_type = On Net Total`, `account_head` = value of `BEI Settings.bki_output_vat_account` (default `2102205 OUTPUT VAT PAYABLE - BKI` per ICT-009; see R2-C1), `rate = 12.0`, `description = "12% Output VAT (BIR)"`

Pre-flight check: verify the Output VAT Payable account exists in BKI's chart of accounts. If not, throw with "Create 'Output VAT Payable' account in Bebang Kitchen Inc. Company chart of accounts before running."

### Task 5.3: Set `BEI Settings` defaults

```
MUST_CREATE: scripts/s168_configure_bei_settings.py
```

SSM script that sets:
- `bki_markup_jv_percent = 2.75`
- `bki_markup_managed_franchise_percent = 8.0`
- `bki_markup_full_franchise_percent = 8.0`
- `bki_sales_vat_template = "BKI Output VAT 12% Sales"`
- `bki_sales_income_account = "4000101 SALES - BKI TO STORES - BKI"` (ICT-008 Butch Option C — locked 2026-04-07 PM)
- `bki_output_vat_account = "2102205 OUTPUT VAT PAYABLE - BKI"` (ICT-009 Butch confirmed 2026-04-07 PM; 2103100 was retired in current COA)

The script MUST create TWO accounts in order (idempotent via `frappe.db.exists`):

1. **Parent grouping account** `4000100 WHOLESALE / B2B SALES - BKI`
   - `parent_account = "4000000 - SALES - BKI"`
   - `is_group = 1`
   - `root_type = "Income"`
   - `account_type = None` (grouping accounts have no type)
   - `report_type = "Profit and Loss"`

2. **Posting child account** `4000101 SALES - BKI TO STORES - BKI`
   - `parent_account = "4000100 - WHOLESALE / B2B SALES - BKI"` (just created above)
   - `is_group = 0`
   - `root_type = "Income"`
   - `account_type = "Income Account"`
   - `report_type = "Profit and Loss"`

The script prints a CONFIRMATION NOTICE (NOT a swap notice — Butch has locked the decision):

```python
print("=" * 70)
print("✓  S168 ICT-008 ACCOUNT LOCKED (Butch Option C — 2026-04-07 PM)")
print("=" * 70)
print("Created parent group : 4000100 WHOLESALE / B2B SALES")
print("Created posting child: 4000101 SALES - BKI TO STORES")
print("BEI Settings.bki_sales_income_account = '4000101 SALES - BKI TO STORES - BKI'")
print("BEI Settings.bki_output_vat_account    = '2102205 OUTPUT VAT PAYABLE - BKI'")
print()
print("Both codes were fact-checked against COA.csv on 2026-04-07 PM — free slots,")
print("consistent with existing 4000200 / 4000300 grouping pattern. No swap required.")
print("=" * 70)
```

The notice is logged to stdout AND persisted to `output/s168/phase5_account_confirmation.txt`.

### Task 5.4: Verify state end-to-end

```
MUST_CREATE: output/s168/phase5_verification.json
```

SSM query verifying: N Customers created matching register, VAT template exists with rate=12, BEI Settings fields populated.

---

## Phase 6: Sentry Observability

**Estimated units: 2**

Every new `@frappe.whitelist()` endpoint and every helper that mutates billing state must call `set_backend_observability_context()` at the top of the function:

- `_create_draft_sales_invoice_for_fulfillment` — module=`commissary`, action=`create_draft_sales_invoice_for_fulfillment`, mutation_type=`create`
- `_submit_sales_invoice_on_delivery_acceptance` — module=`store_billing`, action=`submit_sales_invoice_on_delivery_acceptance`, mutation_type=`submit`
- `_compute_si_row_qty_from_receiving` — no Sentry (pure function)

```
MUST_CONTAIN: "set_backend_observability_context" (in commissary.py near _create_draft_sales_invoice_for_fulfillment)
MUST_CONTAIN: "set_backend_observability_context" (in store.py near _submit_sales_invoice_on_delivery_acceptance)
```

---

## Phase 7: L3 Testing — Vertical Slice + Rejection Scenarios

**Estimated units: 6**

L3 must be run in a fresh agent session per S099 handoff rule.

### L3 Workflow Scenarios

| # | User | Action | Expected Outcome | Failure Means |
|---|---|---|---|---|
| 1 | test.commissary@bebang.ph | Fulfill a Material Request for store `Araneta Gateway` with 5 KG of `RM010-A` | Draft SI created in BKI company, customer = "Bebang [AG corp name]", is_internal_customer=0, 1 row with RM010-A qty 5, rate = basic_rate × 1.0275 (JV markup), taxes_and_charges set, docstatus=0 | Phase 2 broken |
| 2 | Inspect Frappe Desk | Open the Draft SI, verify `custom_bei_stock_entry` link is populated, verify `taxes` shows one row for "Output VAT Payable" at 12% | GL preview shows net + 12% VAT correctly | VAT template not applied |
| 3 | test.supervisor@bebang.ph (store) | Complete receiving for the trip with `received_qty = 5`, `rejected_qty = 0`, `delivery_receipt_no = "DR-TEST-001"` | SI submitted (docstatus=1), linked to receiving via `custom_bei_receiving`, `custom_delivery_receipt_no = "DR-TEST-001"`, `BEI Store Receiving.sales_invoice` field populated, `BEI Store Receiving.acceptance_date` set | Phase 4 not wired |
| 4 | test.supervisor@bebang.ph | Complete receiving with `received_qty = 4, rejected_qty = 1` (partial reject) | SI submits with qty=4 (not 5), rate unchanged, VAT recomputed on reduced net | Phase 3.1 `_compute_si_row_qty_from_receiving` broken |
| 5 | test.supervisor@bebang.ph | Complete receiving with `received_qty = 0, rejected_qty = 5` (full reject) | Draft SI deleted, no SI submitted, stock still posts correctly (Material Receipt SE created) | Full-reject path broken |
| 6 | Inspect GL Entry | Query `tabGL Entry` for voucher_type='Sales Invoice' and the submitted SI name | Two debit lines (AR + nothing), credit lines (Sales Income + Output VAT) with party_type=Customer on AR row (DM-1) | DM-1 violation, GL not properly partied |
| 7 | Test a Managed Franchise store (not JV) | Fulfill → receive → verify SI rate = basic_rate × 1.08 | Different markup applied per store_type | Markup lookup broken |
| 8 | Test a store with `buyer_entity_status = provisional_entity_from_pos_master` | Fulfill → verify NO SI created, error logged | `buyer_entity_requires_billing_hold` gate working | Billing hold gate broken |
| 9 | test.accounts@bebang.ph (or Sam) | Against a submitted SI, call `create_store_sale_credit_note` with 1 line item (qty=1, reason="store damage") | New SI created with `is_return=1`, `return_against=<original>`, negative qty, negative VAT, submitted, linked back to receiving | Phase 11 broken |
| 10 | Sam (admin toggle) | Flip `BEI Settings.bki_ewt_on_store_sales_enabled` to 1, fulfill a test order, complete receiving | Submitted SI includes an EWT tax row at the existing `default_ewt_rate`, account = the existing `ewt_payable_account` (Phase 13 reuses these pre-existing fields, not new ones) | Phase 13 EWT branch broken. Revert flag after test. |
| 11 | test.accounts@bebang.ph | Navigate to `/dashboard/accounting/billing-holds`, find a Draft SI held for a provisional-entity store, click Release (assume entity is now confirmed manually) | Draft SI promoted to Submitted via `release_billing_hold`, hold row clears from dashboard, Sentry breadcrumb recorded | Phase 14 broken |
| 12 | test.supervisor@bebang.ph (store) | Complete receiving with DR number "DR-TEST-S168-001" entered via the new frontend input | `BEI Store Receiving.delivery_receipt_no` populated, SI `custom_delivery_receipt_no` matches | Phase 9 frontend input broken |
| 13 | Inspect `BEI Billing Schedule` | After scenario 3 completes, query `BEI Billing Schedule` for the current period | Row exists for the store, `delivery_fee + logistics_fee` > 0, status = Pending Approval | Phase 10 auto-billing broken |
| 14 | test.accounts@bebang.ph | Call `approve_billing` on the auto-created billing row | A second Sales Invoice is created for the fee amounts with 12% VAT applied, linked via `custom_bei_store_billing` | Phase 10 Task 10.5 broken |
| 15 | Inspect SI `items[].cost_center` | Open the submitted SI from scenario 3 in Frappe Desk | Cost center is the per-store CC (e.g., "Araneta Gateway - BKI") not the default company CC | Phase 12 cost center application broken |

### L3 Evidence Files

```
output/l3/s168/form_submissions.json
output/l3/s168/api_mutations.json
output/l3/s168/state_verification.json
output/l3/s168/si_gl_entries.json
output/l3/s168/screenshots/
```

### Separate L3 session mandate

This sprint is 114 units. L3 MUST run in a separate fresh agent session (S099 rule). Phase 7.0 generates `output/s168/HANDOFF_FOR_L3.md` with the 11 L3 scenarios (8 core sale-billing + scenario 9 credit notes + scenario 10 EWT toggle + scenario 11 billing hold dashboard), test accounts, prerequisite verification steps, and a clear "STOP — do not continue to L3 in this session" instruction. Session A's handoff (Task 8.4) covers scenarios 1-8; Session B's final handoff covers all 11.

### Cleanup after L3

All test SIs and Stock Entries created during L3 MUST be cleaned up via `/frappe-bulk-edits` (Recipe 3 — cancel then delete). Evidence of cleanup in `output/s168/cleanup_evidence.json`.

---

## Phase 8: Session A Checkpoint Commit

**Estimated units: 2**

End of Session A. This is NOT the final closeout — it's a progress checkpoint that prepares the branch for Session B.

### Task 8.1: Update plan status (informational only — sentinel is authoritative)

Update YAML:
```yaml
status: IN_PROGRESS_SESSION_A_COMPLETE
session_a_ended: 2026-MM-DD
```

**R2-C6 note:** this YAML field is informational only. The authoritative resume signal is the sentinel file `output/s168/SESSION_A_COMPLETE.flag` written in Task 8.3 and gated on in the Session B kickoff (see Round 2 addendum). Do NOT set `status: COMPLETED` — Phase 16 / Closeout will set it to `AWAITING_REVIEW` (not COMPLETED — per R2-C9 PR-Handoff rule).

### Task 8.2: Verify ALL Session A phases green before committing

**HARD BLOCKER:** Before the checkpoint commit runs, every Session A phase verification MUST return 0:

```bash
for n in 1 2 3 4 5 6 7; do
  bash scripts/s168_verify_phases.sh $n || { echo "Phase $n FAILED — fix before Phase 8 commit"; exit 1; }
done
```

If any phase gate fails, fix the task that failed, do NOT proceed to Phase 8.3.

### Task 8.3: Commit Session A code AND plan to the branch

**HARD BLOCKER:** `git add` must enumerate every file Session A touched. Using only `git add -f docs/plans/...` (the original buggy spec) stages ONLY the plan markdown and loses all code changes — Session B would start on a branch with zero Session A code.

```bash
# Enumerate explicitly. Do NOT use broad `git add -A hrms/` per project git hygiene rules.
git add hrms/api/commissary.py
git add hrms/api/store.py
git add hrms/hr/doctype/bei_settings/bei_settings.json
git add hrms/fixtures/custom_field.json
git add scripts/s168_audit_missing_customers.py
git add scripts/s168_audit_bki_coa.py
git add scripts/s168_seed_bki_customers.py
git add scripts/s168_seed_bki_vat_template.py
git add scripts/s168_configure_bei_settings.py
git add scripts/s168_verify_phases.sh
git add -f docs/plans/2026-04-07-sprint-168-*.md
# Verify staged diff is non-empty
git diff --cached --name-only | wc -l | grep -qv '^0$' || { echo "nothing staged — aborting"; exit 1; }
git commit -m "checkpoint(S168): Session A complete (phases 0-7), ready for Session B phases 9-16"
git push

# R2-C6: Write Session A completion sentinel. Session B kickoff gates on this file.
mkdir -p output/s168
cat > output/s168/SESSION_A_COMPLETE.flag <<EOF
session: A
phases_complete: 0,1,2,3,4,5,6,7,8
commit_sha: $(git rev-parse HEAD)
branch: $(git branch --show-current)
timestamp: $(date -u +"%Y-%m-%dT%H:%M:%SZ")
EOF
git add -f output/s168/SESSION_A_COMPLETE.flag
git commit -m "checkpoint(S168): Session A sentinel flag (R2-C6)"
git push
```

Verify all 11+ files are listed in `git log -1 --name-only` before proceeding. The sentinel file MUST exist on disk and be pushed to origin before Task 8.5 STOP.

### Task 8.4: Generate Session A L3 handoff

`output/s168/HANDOFF_FOR_L3_SESSION_A.md` — first 8 scenarios (core sale billing), clear "Session B will expand this" note.

### Task 8.5: STOP

End the agent session. Session B starts in a fresh Claude Code window.

---

## Phase 9: Frontend DR Number Input (bei-tasks)

**Estimated units: 4**

### Task 9.1: Add DR number field to store receiving UI

```
MUST_MODIFY: ../bei-tasks/app/dashboard/receiving/[tripName]/page.tsx
MUST_MODIFY: ../bei-tasks/hooks/use-receiving.ts
MUST_CONTAIN: "delivery_receipt_no"
MUST_CONTAIN: "const [deliveryReceiptNo"
```

Add an optional text input labeled "DR Number (optional)" at the top of the receiving form. The value is sent to the `complete_receiving` API call as the `delivery_receipt_no` kwarg (Phase 4.2 already made the backend accept this). Input is free-text up to 50 chars. Placeholder: "e.g., DR-2026-00123".

### Task 9.2: Display DR number on receiving detail view

```
MUST_MODIFY: ../bei-tasks/app/dashboard/receiving/[tripName]/page.tsx
MUST_CONTAIN: "delivery_receipt_no"
```

If `delivery_receipt_no` is populated on the `BEI Store Receiving` record, show it in the detail page header next to the receiving date.

### Task 9.3: Frontend verification

Local TypeScript check + manual Playwright smoke on the receiving form. Add to L3 scenarios (see Phase 14 — updated L3 scenarios include "fill DR number input, submit, verify backend receives it").

---

## Phase 10: Logistics / Delivery Fee Auto-Billing

**Estimated units: 10**

### Task 10.1: Audit existing `BEI Billing Schedule` flow

```
MUST_CREATE: output/s168/billing_rate_audit.json
```

Read `hrms/api/billing.py:280-500` and document the existing `BEI Delivery Rate` + `BEI Billing Schedule` data flow. Identify:
- How rates are keyed per store (`store_warehouse` field? `billing_type`?)
- Whether rates include `delivery_fee` and `logistics_fee` separately
- The `get_delivery_rates` / `set_delivery_rate` / `approve_billing` workflow
- What's required to create a `BEI Billing Schedule` record programmatically

Write audit JSON + a short design note documenting the target shape of an auto-created billing row.

### Task 10.2: NEW `_create_delivery_fee_billing_on_acceptance`

```
MUST_MODIFY: hrms/api/store.py
MUST_CONTAIN: "def _create_delivery_fee_billing_on_acceptance"
MUST_CONTAIN: "BEI Delivery Rate"
MUST_CONTAIN: "set_backend_observability_context"
```

Helper called from `complete_receiving` (alongside the SI submission). Looks up the store's `BEI Delivery Rate` record:
- If rate exists → create a `BEI Billing Schedule` row with `delivery_fee`, `logistics_fee`, `billing_period = <current month>`, `source_reference = receiving.name`, status = `Pending Approval`
- If no rate exists → log warning, do NOT auto-create (Finance must set rate first)
- Wrap in `savepoint("s168_delivery_fee_billing")` — failure must not block receiving

### Task 10.3: Wire into `complete_receiving`

```
MUST_MODIFY: hrms/api/store.py
MUST_CONTAIN: "_create_delivery_fee_billing_on_acceptance(receiving)"
```

After `_submit_sales_invoice_on_delivery_acceptance`, call the delivery fee billing helper. Both in the same outer try block so either can fail independently.

### Task 10.4: Idempotency

Multiple receivings per store per month must roll up into ONE `BEI Billing Schedule` row (append to existing, don't create duplicates). Key: `(store, billing_period_month)`. If a row already exists for this month with status `Pending Approval`, increment its `delivery_fee` and `logistics_fee` totals by the per-trip amount from the rate card.

**HARD BLOCKER:** If status is already `Approved` or `Paid`, create a NEW row for the next period. Never mutate a finalized billing.

### Task 10.5: 12% VAT on logistics fees

Per CFO Q1 ("charging the Deliveries, Logistics and the Fees with 12% VAT but we have yet to issue VAT Sales Invoices"), the delivery/logistics fees ALSO need proper VAT SI treatment. The simplest path: when Finance approves a `BEI Billing Schedule` row, auto-create a second Sales Invoice (BKI side) with the same VAT template used for goods, line items = the fee amounts, customer = buyer_entity_name. This is the same pattern as the goods SI but for services.

```
MUST_MODIFY: hrms/api/billing.py (approve_billing function)
MUST_CONTAIN: "bki_sales_vat_template"
```

Extend `approve_billing` at `hrms/api/billing.py:466` to create a VAT-applied Sales Invoice at approval time. Links: `Sales Invoice.custom_bei_billing_schedule` (new custom field) ↔ `BEI Billing Schedule.sales_invoice` (new custom field).

---

## Phase 11: Post-Submission Credit Notes for Amendments

**Estimated units: 8**

### Task 11.1: NEW `create_store_sale_credit_note` whitelist endpoint

```
MUST_MODIFY: hrms/api/store.py
MUST_CONTAIN: "def create_store_sale_credit_note"
MUST_CONTAIN: "@frappe.whitelist()"
MUST_CONTAIN: "set_backend_observability_context"
MUST_CONTAIN: "check_scm_permission"
```

New endpoint callable after the SI is already submitted. Inputs:
- `sales_invoice` (submitted SI name)
- `reason` (free text required)
- `credit_lines` (list of `{item_code, qty, rate?}`) — the amounts to credit back
- `attachments` (optional — photo evidence)

Behavior:
1. Load the original SI
2. Validate every `credit_lines[].item_code` exists on the SI and qty doesn't exceed the billed qty
3. Create a new Sales Invoice with `is_return = 1`, `return_against = <original SI>`, customer = original customer, same VAT template, negative qty rows
4. Submit the credit note
5. Link back to `BEI Store Receiving` that this credit note relates to (new optional field `credit_note` on receiving)
6. Log to Sentry + notify Finance via Google Chat

### Task 11.2: Permission gating

Only users with `Accounts Manager` or `SCM Admin` roles can call this endpoint. Check via `check_scm_permission(SCM_ADMIN_ROLES, "create store sale credit note")`.

### Task 11.3: Frontend trigger (bei-tasks)

```
MUST_MODIFY: ../bei-tasks/components/billing/credit-note-modal.tsx (NEW)
MUST_MODIFY: ../bei-tasks/app/dashboard/receiving/[tripName]/page.tsx
MUST_MODIFY: ../bei-tasks/hooks/use-billing.ts
MUST_CONTAIN: "export function CreditNoteModal"
MUST_CONTAIN: "createStoreSaleCreditNote"
```

Add a "Request Credit Note" button visible only to SCM Admin / Accounts Manager roles. Opens a modal with:
- Reason text area (required)
- Table of items from the original SI with editable credit qty per row
- Submit → POST to `create_store_sale_credit_note`
- On success, refresh the page and show the credit note link

### Task 11.4: L3 scenario added

L3 scenario 9 (new): Submit a credit note against a previously submitted SI, verify credit note posts with negative qty and correct VAT, verify `tabGL Entry` shows AR reversal with `party_type=Customer`.

---

## Phase 12: Store P&L Allocation (Cost Centers Per Store)

**Estimated units: 10**

### Task 12.1: Verify cost center hierarchy

```
MUST_CREATE: output/s168/cost_center_audit.json
```

SSM query listing all cost centers in BKI company. Identify whether there's already a per-store cost center hierarchy (e.g., `Stores → JV → Ayala Evo City`). If not, document what's needed.

### Task 12.2: Seed cost centers for every register store

```
MUST_CREATE: scripts/s168_seed_store_cost_centers.py
MUST_CREATE: output/s168/seed_cost_centers_evidence.json
```

SSM script that iterates the S037 register and creates a BKI cost center for each store where `store_allocation_required = 1`. Hierarchy:
```
Bebang Kitchen Inc. (root)
├── Stores (parent)
│   ├── JV (group)
│   │   ├── Ayala Evo City
│   │   ├── Ayala Fairview Terraces
│   │   └── ...
│   ├── Managed Franchise (group)
│   │   └── ...
│   └── Full Franchise (group)
│       └── ...
```

Each leaf cost center name: `{store_name} - BKI` to distinguish from existing warehouse-style names.

### Task 12.3: Apply cost center on SI rows

```
MUST_MODIFY: hrms/api/commissary.py (_create_draft_sales_invoice_for_fulfillment)
MUST_CONTAIN: "cost_center = _resolve_store_cost_center"
```

When creating the draft SI, look up the cost center for the target store and apply it to each SI item row. Fallback: BKI default cost center if the store has no dedicated one (with a warning log).

### Task 12.4: New helper `_resolve_store_cost_center`

```python
def _resolve_store_cost_center(store_warehouse: str, entity_row: dict) -> str:
    """S168: Resolve the BKI cost center for a store so SI GL posts land in the
    right store P&L bucket."""
    store_name = entity_row.get("store_name") or ""
    candidate = f"{store_name} - BKI"
    if frappe.db.exists("Cost Center", {"name": candidate, "company": "Bebang Kitchen Inc."}):
        return candidate
    # Fallback: group cost center by store_type
    group = entity_row.get("store_type") or "Stores"
    group_cc = f"{group} - BKI"
    if frappe.db.exists("Cost Center", {"name": group_cc, "company": "Bebang Kitchen Inc."}):
        frappe.log_error(
            f"S168: No store-level cost center for {store_name}; falling back to group '{group_cc}'",
            "S168 Cost Center Fallback",
        )
        return group_cc
    # Last resort: default
    return frappe.db.get_value("Company", "Bebang Kitchen Inc.", "cost_center")
```

---

## Phase 13: EWT Toggle Framework (reuses existing BEI Settings fields)

**Estimated units: 5**

**CODE-VERIFIED:** `BEI Settings` already has these fields from prior sprints — S168 MUST REUSE them, not create duplicates:
- `default_ewt_rate` (Float)
- `ewt_payable_account` (Link → Account)
- `default_vat_rate` (Float)

### Task 13.1: Add ONLY the EWT enable toggle to BEI Settings

```
MUST_MODIFY: hrms/hr/doctype/bei_settings/bei_settings.json
MUST_CONTAIN: "bki_ewt_on_store_sales_enabled"
```

Add only one new field (the toggle). Reuse the 3 existing fields for rate and account:

- `bki_ewt_on_store_sales_enabled` (Check, default 0) — when OFF (per ICT-004), BKI→store SIs do not apply EWT. When Finance flips it ON (e.g., BKI is tagged Top 20,000), the existing `default_ewt_rate` and `ewt_payable_account` become active on BKI→store SIs.

**HARD BLOCKER:** Do NOT create `bki_ewt_on_store_sales_enabled`, `bki_ewt_goods_rate`, `bki_ewt_services_rate`, or `bki_ewt_payable_account`. These would duplicate existing fields and corrupt the single-source-of-truth pattern. The code verifier confirmed the existing fields at `hrms/hr/doctype/bei_settings/bei_settings.json` (2026-04-07).

### Task 13.2: Conditional EWT application in SI

```
MUST_MODIFY: hrms/api/commissary.py (_create_draft_sales_invoice_for_fulfillment)
MUST_CONTAIN: "bki_ewt_on_store_sales_enabled"
MUST_CONTAIN: "default_ewt_rate"
MUST_CONTAIN: "ewt_payable_account"
```

When creating the draft SI, check `BEI Settings.bki_ewt_on_store_sales_enabled`:
- If `0` → skip EWT entirely (current state per ICT-004 — not Top 20,000 taxpayer).
- If `1` → append EWT tax row to the SI taxes table using the EXISTING `default_ewt_rate` field (not a new `bki_ewt_goods_rate`), account = the EXISTING `ewt_payable_account`, `charge_type = On Net Total`, with the amount negated so it reduces AR rather than adding to the customer's bill (standard Philippine EWT-at-source pattern).

**Direction caveat (from audit W3 finance finding):** The backend-audit flagged that Top 20,000 EWT obligation runs on the PAYER (the store), not BKI. In that future scenario, BKI would RECEIVE a 2307 from the store, not withhold from its own SI. The Phase 13 toggle as described keeps the withholding on BKI's side as an interim mechanic; when the real scenario activates, Finance must review whether to use this toggle or implement a 2307-receivable pattern instead. Documented here so the decision is visible at toggle-flip time.

### Task 13.3: Document the toggle

Add a note in the plan's closeout summary: "EWT is OFF by default per ICT-004. If BEI becomes a Top 20,000 taxpayer under BIR, Finance flips `bki_ewt_on_store_sales_enabled` in BEI Settings. No code change required. See Task 13.2 direction caveat before flipping."

### Task 13.4: L3 scenario

New L3 scenario 10: Flip `bki_ewt_on_store_sales_enabled=1` temporarily, run a fulfillment + receiving, verify the submitted SI includes an EWT tax row at `default_ewt_rate`, revert the flag.

---

## Phase 14: Billing Hold Admin Dashboard (bei-tasks)

**Estimated units: 12**

### Task 14.1: New route `/dashboard/accounting/billing-holds`

```
MUST_CREATE: ../bei-tasks/app/dashboard/accounting/billing-holds/page.tsx
MUST_CONTAIN: "Draft Sales Invoices on Hold"
```

New page for Finance/Accounts Manager role. Lists:
- All Draft Sales Invoices in BKI company where `customer` matches a store with `buyer_entity_status IN ('provisional_entity_from_pos_master', 'entity_confirmed_store_type_pending')` OR `billing_post_policy = 'DRAFT_ONLY__BILLING_HOLD_PENDING_REGISTER'`
- Columns: SI name, Store, Customer (buyer entity), Stock Entry, Fulfillment date, Status, Amount, Reason for hold
- Filter by store, by hold reason, by date range

### Task 14.2: Release workflow

Per-row actions:
- **Release**: admin confirms the buyer entity, clicks Release → backend promotes the Draft SI to Submitted (calls the same logic as `_submit_sales_invoice_on_delivery_acceptance` but without the receiving linkage, since the release may happen after delivery already occurred)
- **Reject**: cancel the Draft SI with a reason, flag the register row for follow-up, notify Finance
- **Re-assign buyer**: change the customer (admin override) if the entity was wrong

### Task 14.3: Backend endpoints

```
MUST_MODIFY: hrms/api/store.py
MUST_CONTAIN: "def get_billing_holds"
MUST_CONTAIN: "def release_billing_hold"
MUST_CONTAIN: "def reject_billing_hold"
MUST_CONTAIN: "def reassign_billing_hold_customer"
```

Four new whitelist endpoints. All gated on `Accounts Manager` role. All instrumented with Sentry.

### Task 14.4: Next.js proxy route

```
MUST_MODIFY: ../bei-tasks/app/api/billing-holds/route.ts (NEW)
```

GET + POST proxy following the same pattern as `delivery-schedule/route.ts`. Forwards to the 4 new backend endpoints.

### Task 14.5: Sidebar placement

```
MUST_MODIFY: ../bei-tasks/lib/navigation-personas.ts
MUST_MODIFY: ../bei-tasks/lib/constants.ts
```

Add "Billing Holds" nav entry under Accounting persona, visible only to `Accounts Manager` + `System Manager` roles. Route constant: `BILLING_HOLDS: "/dashboard/accounting/billing-holds"`.

### Task 14.6: Empty state + notifications

When 0 holds exist, show an empty state ("All BKI Draft SIs are ready for submission via delivery acceptance. Nothing needs manual review."). When a new hold appears, send a notification to the Accounts Manager via Google Chat (optional, but document it as a follow-up if not implemented in this phase).

---

## Phase 15: Same-Company (BEI→BEI) Billing Reclassification

**Estimated units: 8**

### Task 15.1: Current state audit

```
MUST_CREATE: output/s168/same_company_transfer_audit.json
```

Query existing `Stock Entry` records where `stock_entry_type = "Material Transfer"` and `source_warehouse` + `to_warehouse` are both in BEI (not BKI). Count how many happen per month, which cost centers they touch, and whether any GL reclassification currently happens.

### Task 15.2: Decision point — is reclassification needed?

**HARD BLOCKER:** Before writing any reclassification code, confirm with Finance (user prompt if needed):
- "When BEI warehouse A transfers to BEI warehouse B (different store departments), should there be a cost-center-level reclassification JE so each store's P&L reflects the transfer?"
- If YES → proceed with Task 15.3
- If NO → skip Task 15.3, just document "same-company transfers remain stock-only, no GL reclassification required" in the plan closeout

### Task 15.3 (conditional): Cost center reclassification JE

```
MUST_MODIFY: hrms/api/store.py OR hrms/api/commissary.py
MUST_CONTAIN: "def _create_same_company_reclassification_je"
```

Helper that creates a Journal Entry on same-company Material Transfers. **DM-6 full context MUST be set on every row:**

```python
def _create_same_company_reclassification_je(stock_entry):
    """S168 Phase 15.3: Create cost-center reclassification JE for BEI->BEI moves.

    Full DM-6 context per .claude/rules/frappe-development.md:
    - reference_type + reference_name on BOTH rows (not freetext in user_remark)
    - cost_center on both rows
    - user_remark with source SE, warehouses, and amount
    - party_type + party intentionally omitted (inventory accounts, same legal entity,
      no AR/AP — confirmed DM-1 exception with finance during S168 planning)
    """
    import frappe
    from frappe.utils import flt

    amount = sum(flt(row.basic_rate) * flt(row.qty) for row in stock_entry.items)
    if amount <= 0:
        return None

    source_cc = _resolve_warehouse_cost_center(stock_entry.from_warehouse)
    dest_cc = _resolve_warehouse_cost_center(stock_entry.to_warehouse)
    source_inv_account = _resolve_warehouse_inventory_account(stock_entry.from_warehouse)
    dest_inv_account = _resolve_warehouse_inventory_account(stock_entry.to_warehouse)

    if source_cc == dest_cc:
        return None  # same bucket, nothing to reclassify

    try:
        frappe.db.savepoint("s168_reclass_je")
        je = frappe.new_doc("Journal Entry")
        je.voucher_type = "Journal Entry"
        je.company = stock_entry.company
        je.posting_date = stock_entry.posting_date
        je.user_remark = (
            f"S168 same-company transfer reclassification: "
            f"{stock_entry.name} ({stock_entry.from_warehouse} -> {stock_entry.to_warehouse}) "
            f"amount={amount:.2f}"
        )
        je.append("accounts", {
            "account": dest_inv_account,
            "debit_in_account_currency": amount,
            "cost_center": dest_cc,
            "reference_type": "Stock Entry",    # DM-6: required
            "reference_name": stock_entry.name, # DM-6: required
            # party_type + party intentionally None — inventory account, same legal entity
        })
        je.append("accounts", {
            "account": source_inv_account,
            "credit_in_account_currency": amount,
            "cost_center": source_cc,
            "reference_type": "Stock Entry",    # DM-6: required
            "reference_name": stock_entry.name, # DM-6: required
        })
        je.insert(ignore_permissions=True)
        je.submit()
        frappe.db.release_savepoint("s168_reclass_je")
        return je.name
    except Exception:
        frappe.db.sql("ROLLBACK TO SAVEPOINT s168_reclass_je")
        frappe.log_error(
            f"S168 same-company reclassification JE failed for SE {stock_entry.name}: {frappe.get_traceback()}",
            "S168 Reclassification Error",
        )
        # Do NOT raise — stock entry already posted; don't roll it back
        return None
```

**DM-6 checklist for this JE:**
- [x] `reference_type="Stock Entry"` on BOTH rows
- [x] `reference_name=stock_entry.name` on BOTH rows
- [x] `cost_center` on BOTH rows (source CC on credit, dest CC on debit)
- [x] `user_remark` includes SE name, source+dest warehouses, amount
- [x] `party_type`+`party` intentionally omitted — both accounts are inventory, not AR/AP (DM-1 exception documented here)
- [x] Wrapped in savepoint; failure logs + swallows so SE isn't rolled back

Wire into same-company branch of `fulfill_store_order` (BEI→BEI) and `complete_receiving` (BEI intra-company path).

### Task 15.4: Verify no double-posting

**HARD BLOCKER:** Ensure this does NOT fire when source is BKI (that path gets an SI, not a reclassification JE). Add explicit guard:

```python
if source_company == target_company:  # same-company only
    _create_same_company_reclassification_je(...)
else:  # intercompany — SI handles it
    _create_draft_sales_invoice_for_fulfillment(...)
```

---

## Phase 16: Closeout

**Estimated units: 3**

**R2-C8 HARD BLOCKER — L3 evidence gate (must pass before any closeout step):**
```bash
for f in form_submissions.json api_mutations.json state_verification.json si_gl_entries.json; do
  test -f "output/l3/s168/$f" || { echo "STOP: output/l3/s168/$f missing — L3 did not produce evidence"; exit 1; }
done
git add -f output/l3/s168/
git commit -m "evidence(S168): L3 artifacts" && git push
```

1. Update plan YAML: `status: AWAITING_REVIEW` (NOT `COMPLETED` — see R2-C9 PR-Handoff fix), `completed_date`, `execution_summary` listing ALL phases. **Only Sam flips to COMPLETED after merging both PRs.**
2. Update `docs/plans/SPRINT_REGISTRY.md` S168 row.
3. `git add -f` both files, commit, push.
4. Verify CSV register intact.
5. Verify old code fully removed (grep counts from Phase 2 checks = 0).
6. Verify every new function has Sentry instrumentation.
7. Verify all new Custom Fields are live in Frappe (SSM query).
8. Verify the 48 BKI Customers + VAT template + BEI Settings exist.
9. Verify cost centers seeded (Phase 12).
10. Verify EWT toggle framework is OFF by default (Phase 13).
11. Verify billing holds dashboard renders for Accounts Manager (Phase 14).

---

## Sentry Observability

All new `@frappe.whitelist()` or mutation-carrying helpers in `hrms/api/commissary.py` and `hrms/api/store.py` MUST call `set_backend_observability_context(module=..., action=..., mutation_type=...)`.

Sentry project: `bei-hrms` (python). Org: `bebang-enterprise-inc`.

---

## Requirements Regression Checklist

Before writing ANY code, the executing agent must verify each item. YES or STOP.

### Policy decisions (from ICT-001 through ICT-006, BIL-005)

- [ ] Is `is_internal_customer = 0` set on every SI this sprint creates? *(ICT-001 — stores are external)*
- [ ] Is 12% VAT applied via `BKI Output VAT 12% Sales` template (not hardcoded)? *(ICT-001)*
- [ ] Is JV markup read from `BEI Settings.bki_markup_jv_percent` (default 2.75%)? *(ICT-002)*
- [ ] Is Managed Franchise markup read from `BEI Settings.bki_markup_managed_franchise_percent` (default 8%)? *(ICT-002, BIL-005)*
- [ ] Is Full Franchise markup also read from `BEI Settings.bki_markup_full_franchise_percent`? *(ICT-002)*
- [ ] Is **NO** mirror Purchase Invoice created on BEI side? *(ICT-004 — stores file own tax returns)*
- [ ] Is **NO** EWT withheld on BKI payments? *(ICT-004 — not Top 20k taxpayer)*
- [ ] Is BKI used as `Sales Invoice.company = "Bebang Kitchen Inc."`? *(ICT-005)*
- [ ] Is each store Customer resolved via `resolve_store_buyer_entity` → exact `buyer_entity_name` match? *(ICT-005 + S037 register)*
- [ ] Is `make_inter_company_purchase_invoice` REMOVED from the codebase? *(ICT-006 — not applicable)*
- [ ] Does the old `_create_intercompany_invoices_async` NOT exist anywhere? *(Replaced entirely)*
- [ ] Does the old `_get_store_type_and_customer` NOT exist? *(Replaced by `resolve_store_buyer_entity`)*

### Timing decisions (CEO directive 2026-04-07)

- [ ] Is the SI created as **Draft** at fulfillment (commissary fulfill_store_order)? *(Not submitted yet)*
- [ ] Is the SI **Submitted** at receiving (complete_receiving after acceptance)? *(NOT at fulfillment)*
- [ ] Does the SI `posting_date` match `receiving_date` (not fulfillment_date)?
- [ ] Does the SI carry `custom_delivery_receipt_no` from `BEI Store Receiving.delivery_receipt_no`?
- [ ] Does partial rejection reduce the SI qty to `received_qty - rejected_qty` before submission?
- [ ] Does full rejection delete the Draft SI (no empty SI submitted)?

### Billing hold respect

- [ ] Does the code check `buyer_entity_requires_billing_hold(entity_row)` before creating the SI?
- [ ] Does a provisional/missing entity row skip SI creation and log a notification?

### Atomicity and error handling

- [ ] Is draft SI creation wrapped in `frappe.db.savepoint("s168_draft_si")` so failures don't break fulfillment?
- [ ] Is SI submission wrapped in `frappe.db.savepoint("s168_submit_si")` so failures don't break receiving?
- [ ] Does SI submission failure log to `frappe.log_error` + notify Google Chat (not silently swallow)?

### DM (Frappe Deadly Mistakes) gates

- [ ] **DM-1:** Does the submitted SI have `party_type="Customer"` and `party=<store corp>` on the AR row via ERPNext's standard SI flow?
- [ ] **DM-2:** Are all multi-doc updates (SI row edit + save + submit) in a savepoint?
- [ ] **DM-3:** Is VAT applied (12% Output) via a template on every SI? EWT is NOT required per ICT-004 — confirmed.
- [ ] **DM-4:** Are all reference fields `Link` type (not Data)? `custom_bei_store_order`, `custom_bei_stock_entry`, `custom_bei_receiving`, `custom_sales_invoice_draft` — all Link.
- [ ] **DM-5:** Are markup rates computed at runtime from BEI Settings (not stored duplicates)?
- [ ] **DM-6:** Does the SI `remarks` include source document references (store order, stock entry, markup rate)?
- [ ] **DM-7:** Do all new whitelist/mutation functions call `set_backend_observability_context`?

### S163 compatibility

- [ ] Does `Sales Invoice.items.item_code` store the **real member SKU**, never `GRP-*`? *(S163 HARD BLOCKER #2)*
- [ ] Does one Material Transfer → one Draft SI regardless of grouped-order-item row count? *(Multi-row model flattened to SI rows by item_code aggregation)*

### Phase 9-15 expanded-scope requirements

- [ ] **Phase 9:** Does the bei-tasks receiving form expose a `delivery_receipt_no` input? Does the backend receive it?
- [ ] **Phase 10:** On delivery acceptance, is a `BEI Billing Schedule` row auto-created or updated for the store's current billing period?
- [ ] **Phase 10:** Is `approve_billing` extended to create a VAT-applied Sales Invoice for the delivery/logistics fees (CFO Q1 — already charging VAT but not issuing SIs)?
- [ ] **Phase 11:** Does `create_store_sale_credit_note` exist as a whitelist endpoint with permission gating?
- [ ] **Phase 11:** Does the credit note inherit the same VAT template as the original SI?
- [ ] **Phase 12:** Are per-store cost centers seeded for every register entry with `store_allocation_required=1`?
- [ ] **Phase 12:** Does every SI item row carry the correct store cost center?
- [ ] **Phase 13:** Does `BEI Settings.bki_ewt_on_store_sales_enabled` default to 0 (OFF per ICT-004)?
- [ ] **Phase 13:** When flipped to 1, does the SI include a 1% EWT tax row on goods?
- [ ] **Phase 14:** Does `/dashboard/accounting/billing-holds` render for Accounts Manager / System Manager roles only?
- [ ] **Phase 14:** Do the 4 endpoints (`get_billing_holds`, `release_billing_hold`, `reject_billing_hold`, `reassign_billing_hold_customer`) all have Sentry instrumentation and role gating?
- [ ] **Phase 15:** Was Finance asked whether same-company reclassification JEs are required? If yes, is the helper wired? If no, is the decision documented in the plan closeout?
- [ ] **Phase 15:** Does the reclassification JE (if implemented) carry cost centers on both debit and credit sides (DM-6)?

### Verification gates

- [ ] Does `scripts/s168_verify_phases.sh all` return zero exit code for ALL 16 phases?
- [ ] Does L3 run produce `form_submissions.json`, `api_mutations.json`, `state_verification.json` covering 11 scenarios?
- [ ] Does L3 scenario 4 (partial reject) show SI qty = received - rejected?
- [ ] Does L3 scenario 9 (credit note) show a negative-qty Sales Invoice linked to the original SI?
- [ ] Does L3 scenario 10 (EWT toggle) show an EWT tax row when the flag is flipped ON?
- [ ] Does L3 scenario 11 (billing hold dashboard) show an admin releasing a held Draft SI via the new UI?

---

## Zero-Skip Enforcement

Every task MUST be implemented. No exceptions. If a task cannot be completed, the agent STOPS and asks the user.

**Forbidden behaviors:**
- Skipping a task silently
- Marking partial work as "done"
- Replacing a task with a simpler version without user approval
- Saying "deferred to next sprint"
- Combining tasks and dropping features
- Implementing happy path only, skipping edge cases (especially: full reject, partial reject, billing hold, missing Customer)

### Phase verification script — `scripts/s168_verify_phases.sh`

```
MUST_CREATE: scripts/s168_verify_phases.sh
```

```bash
#!/bin/bash
# S168 phase verification gate. Run from BEI-ERP working dir.
# Usage: bash scripts/s168_verify_phases.sh <phase|all>
set -e
PHASE="${1:-all}"
err() { echo "FAIL: $1"; exit 1; }
ok() { echo "OK: $1"; }

phase1() {
  echo "=== Phase 1: DocType + Custom Field schema ==="
  grep -q "bki_markup_jv_percent" hrms/hr/doctype/bei_settings/bei_settings.json || err "BEI Settings field missing"
  grep -q "bki_sales_vat_template" hrms/hr/doctype/bei_settings/bei_settings.json || err "BEI Settings VAT template field missing"
  grep -q "Sales Invoice-custom_bei_receiving" hrms/fixtures/custom_field.json || err "SI custom_bei_receiving field missing"
  grep -q "BEI Store Receiving-delivery_receipt_no" hrms/fixtures/custom_field.json || err "Receiving DR field missing"
  grep -q "Stock Entry-custom_sales_invoice_draft" hrms/fixtures/custom_field.json || err "SE draft SI link field missing"
  ok "phase 1"
}

phase2() {
  echo "=== Phase 2: Draft SI at fulfillment ==="
  grep -q "def _create_draft_sales_invoice_for_fulfillment" hrms/api/commissary.py || err "new SI fn missing"
  if grep -q "def _create_intercompany_invoices_async" hrms/api/commissary.py; then err "old fn still exists"; fi
  if grep -q "def _get_store_type_and_customer" hrms/api/commissary.py; then err "old lookup still exists"; fi
  if grep -q "make_inter_company_purchase_invoice" hrms/api/commissary.py; then err "mirror PI helper still called"; fi
  if grep -q "is_internal_customer = 1" hrms/api/commissary.py; then err "internal customer flag still set"; fi
  grep -q 'savepoint("s168_draft_si"' hrms/api/commissary.py || err "draft SI savepoint missing"
  grep -q "resolve_store_buyer_entity" hrms/api/commissary.py || err "register lookup not called"
  grep -q "bki_sales_vat_template" hrms/api/commissary.py || err "VAT template not applied"
  # Customer lookup in store.py must use exact match
  grep -q "resolve_store_buyer_entity" hrms/api/store.py || err "store.py customer lookup not rewired"
  if grep -q 'customer_name.*LIKE' hrms/api/store.py | grep -q "_get_store_customer"; then err "LIKE match still in _get_store_customer"; fi
  ok "phase 2"
}

phase3() {
  echo "=== Phase 3: SI submission at receiving ==="
  grep -q "def _submit_sales_invoice_on_delivery_acceptance" hrms/api/store.py || err "submit fn missing"
  grep -q "def _compute_si_row_qty_from_receiving" hrms/api/store.py || err "qty compute helper missing"
  grep -q 'savepoint("s168_submit_si"' hrms/api/store.py || err "submit SI savepoint missing"
  grep -q "def _notify_billing_defect" hrms/api/store.py || err "defect notifier missing"
  ok "phase 3"
}

phase4() {
  echo "=== Phase 4: complete_receiving wired ==="
  grep -q "_submit_sales_invoice_on_delivery_acceptance(receiving)" hrms/api/store.py || err "wiring missing"
  grep -q "delivery_receipt_no" hrms/api/store.py || err "DR number param missing"
  ok "phase 4"
}

phase5() {
  echo "=== Phase 5: Seed scripts ==="
  test -f scripts/s168_seed_bki_customers.py || err "customer seed script missing"
  test -f scripts/s168_seed_bki_vat_template.py || err "VAT seed script missing"
  test -f scripts/s168_configure_bei_settings.py || err "settings script missing"
  ok "phase 5"
}

phase6() {
  echo "=== Phase 6: Sentry ==="
  grep -A 15 "def _create_draft_sales_invoice_for_fulfillment" hrms/api/commissary.py | grep -q "set_backend_observability_context" || err "Sentry missing on draft SI fn"
  grep -A 15 "def _submit_sales_invoice_on_delivery_acceptance" hrms/api/store.py | grep -q "set_backend_observability_context" || err "Sentry missing on submit fn"
  ok "phase 6"
}

phase7() {
  echo "=== Phase 7: L3 handoff ==="
  test -f output/s168/HANDOFF_FOR_L3.md || err "L3 handoff doc missing"
  ok "phase 7 (handoff only; actual L3 runs in fresh session)"
}

phase9() {
  echo "=== Phase 9: Frontend DR input ==="
  grep -rq "delivery_receipt_no" ../bei-tasks/app/dashboard/store-ops/receiving/ || err "DR input missing from receiving UI"
  ok "phase 9"
}

phase10() {
  echo "=== Phase 10: Logistics auto-billing ==="
  grep -q "def _create_delivery_fee_billing_on_acceptance" hrms/api/store.py || err "delivery fee billing helper missing"
  grep -q "_create_delivery_fee_billing_on_acceptance(receiving)" hrms/api/store.py || err "not wired in complete_receiving"
  grep -q "bki_sales_vat_template" hrms/api/billing.py || err "VAT template not applied on approve_billing"
  ok "phase 10"
}

phase11() {
  echo "=== Phase 11: Credit notes ==="
  grep -q "def create_store_sale_credit_note" hrms/api/store.py || err "credit note endpoint missing"
  grep -A 15 "def create_store_sale_credit_note" hrms/api/store.py | grep -q "is_return" || err "is_return flag missing"
  grep -A 15 "def create_store_sale_credit_note" hrms/api/store.py | grep -q "set_backend_observability_context" || err "Sentry missing"
  ok "phase 11"
}

phase12() {
  echo "=== Phase 12: Store P&L cost centers ==="
  test -f scripts/s168_seed_store_cost_centers.py || err "cost center seed script missing"
  grep -q "def _resolve_store_cost_center" hrms/api/commissary.py || err "cost center resolver missing"
  ok "phase 12"
}

phase13() {
  echo "=== Phase 13: EWT toggle ==="
  grep -q "bki_ewt_on_store_sales_enabled" hrms/hr/doctype/bei_settings/bei_settings.json || err "EWT toggle field missing"
  grep -q "bki_ewt_on_store_sales_enabled" hrms/api/commissary.py || err "EWT logic not in SI creation"
  ok "phase 13"
}

phase14() {
  echo "=== Phase 14: Billing hold dashboard ==="
  test -f ../bei-tasks/app/dashboard/accounting/billing-holds/page.tsx || err "billing holds page missing"
  test -f ../bei-tasks/app/api/billing-holds/route.ts || err "billing holds proxy missing"
  grep -q "def get_billing_holds" hrms/api/store.py || err "get_billing_holds endpoint missing"
  grep -q "def release_billing_hold" hrms/api/store.py || err "release endpoint missing"
  grep -q "def reject_billing_hold" hrms/api/store.py || err "reject endpoint missing"
  grep -q "def reassign_billing_hold_customer" hrms/api/store.py || err "reassign endpoint missing"
  grep -q "BILLING_HOLDS" ../bei-tasks/lib/constants.ts || err "route constant missing"
  ok "phase 14"
}

phase15() {
  echo "=== Phase 15: Same-company reclassification ==="
  test -f output/s168/same_company_transfer_audit.json || err "audit missing"
  # Conditional — helper may or may not exist based on Finance decision
  if grep -q "def _create_same_company_reclassification_je" hrms/api/store.py hrms/api/commissary.py; then
    echo "  same-company reclassification JE helper present"
  else
    echo "  NOTE: same-company reclassification JE not implemented — verify Finance decision in audit doc"
  fi
  ok "phase 15"
}

case "$PHASE" in
  1) phase1 ;;
  2) phase2 ;;
  3) phase3 ;;
  4) phase4 ;;
  5) phase5 ;;
  6) phase6 ;;
  7) phase7 ;;
  9) phase9 ;;
  10) phase10 ;;
  11) phase11 ;;
  12) phase12 ;;
  13) phase13 ;;
  14) phase14 ;;
  15) phase15 ;;
  all) phase1; phase2; phase3; phase4; phase5; phase6; phase7; phase9; phase10; phase11; phase12; phase13; phase14; phase15 ;;
  *) echo "Unknown phase: $PHASE"; exit 2 ;;
esac
```

---

## Phase Budget Contract

**Session A — Core sale-billing rewire (54 units)**

| Phase | Units | Session | Notes |
|---|---|---|---|
| Phase 0 (Audit + branch) | 4 | A | |
| Phase 1 (Schema extensions) | 6 | A | |
| Phase 2 (Draft SI at fulfillment) | 10 | A | DELETE old fn + NEW fn + rewire |
| Phase 3 (Receiving submit helpers) | 10 | A | Two helpers + notifier |
| Phase 4 (Wire complete_receiving) | 6 | A | |
| Phase 5 (Seed Customers + VAT + Settings) | 8 | A | 3 SSM scripts + runs |
| Phase 6 (Sentry — core) | 2 | A | |
| Phase 7 (L3 handoff — core scenarios 1-8) | 6 | A | |
| Phase 8 (Closeout checkpoint) | 2 | A | Checkpoint commit; NOT final closeout |
| **Session A total** | **54** | | |

**Session B — Completeness + Admin (60 units)**

| Phase | Units | Session | Notes |
|---|---|---|---|
| Phase 9 (Frontend DR input) | 4 | B | bei-tasks receiving form + detail page |
| Phase 10 (Logistics auto-billing + fee VAT SI) | 10 | B | Wire BEI Billing Schedule auto-creation + VAT SI on approve |
| Phase 11 (Post-submission credit notes) | 8 | B | New endpoint + UI trigger |
| Phase 12 (Store P&L cost centers) | 10 | B | Seed CCs + apply to SI rows |
| Phase 13 (EWT toggle framework) | 5 | B | Off by default per ICT-004 |
| Phase 14 (Billing hold admin dashboard) | 12 | B | New bei-tasks page + 4 endpoints + proxy + nav |
| Phase 15 (Same-company reclassification) | 8 | B | Conditional on Finance decision (Task 15.2 HARD BLOCKER) |
| Phase 16 (Final closeout) | 3 | B | Full closeout, plan → COMPLETED |
| **Session B total** | **60** | | |

| **GRAND TOTAL** | **114** | | **Exceeds 80-unit ceiling by 34** — must split execution across 2 sessions |

**Hard limit per phase:** 15 units. No phase exceeds this.
**Preferred limit per phase:** 12 units. Phase 14 (billing hold dashboard) is at 12 — at the preferred limit, not above.

### Why 2 sessions (not a hard sprint split)

Same branch, same plan, same PR — but two agent sessions. Session B starts fresh with full context from Session A's commits. Prevents the S092 corrupt-success failure mode where agents at 80+ units skip L3 and declare COMPLETED from exhaustion.

**Session A ends** when Phase 8 checkpoint commit is pushed and the Session A L3 handoff doc is written. The branch is NOT merged yet.

**Session B begins** in a fresh Claude Code window with: `/execute-plan-bei-erp docs/plans/2026-04-07-sprint-168-bki-store-sale-billing-on-delivery.md`. The agent's first action is the **R2-C6 Session B kickoff gate (HARD BLOCKER)**:

```bash
git fetch origin
git checkout s168-bki-store-sale-billing-on-delivery
git pull --ff-only
test -f output/s168/SESSION_A_COMPLETE.flag || { echo "STOP: Session A sentinel missing — Session A was never committed or branch is wrong"; exit 1; }
cat output/s168/SESSION_A_COMPLETE.flag  # audit trail
for n in 1 2 3 4 5 6 7 8; do
  bash scripts/s168_verify_phases.sh $n || { echo "STOP: Session A phase $n verify FAILED — do not start Session B until Session A is green"; exit 1; }
done
```

If the gate passes, Session B starts at **Phase 9** unconditionally. Phases 0-8 are NOT re-executed. If any check fails, the agent STOPS and asks Sam. The YAML `status` field is informational only; the sentinel file is the authoritative resume signal.

---

## Autonomous Execution Contract

- **completion_condition:**
  - All **16 phases** implemented across 2 sessions and verified via `scripts/s168_verify_phases.sh all`
  - All Phase 5 seed scripts executed (Customers + VAT template + BEI Settings)
  - Phase 12 seed scripts executed (per-store cost centers)
  - PR created for hrms + PR created for bei-tasks (Phases 9, 11, 14 touch bei-tasks)
  - L3 evidence files at `output/l3/s168/` cover all **11 scenarios** (8 core + 9 credit notes + 10 EWT toggle + 11 billing hold dashboard) in fresh session(s)
  - Test data cleaned up via `/frappe-bulk-edits`
  - Plan YAML status → COMPLETED with execution_summary listing all 16 phases
  - `docs/plans/SPRINT_REGISTRY.md` row → COMPLETED with PR numbers from both repos
  - Old code (`_create_intercompany_invoices_async`, `_get_store_type_and_customer`, `make_inter_company_purchase_invoice`, `is_internal_customer=1`) NOT in codebase
  - Frontend DR input live on receiving page (Phase 9)
  - Auto-billing triggers on delivery acceptance (Phase 10)
  - Credit note endpoint + UI live (Phase 11)
  - Store-level cost centers seeded and applied on SI rows (Phase 12)
  - EWT toggle framework in place, default OFF (Phase 13)
  - Billing hold admin dashboard live at `/dashboard/accounting/billing-holds` (Phase 14)
  - Same-company reclassification JE wired OR explicitly deferred per Finance decision (Phase 15 Task 15.2)

- **stop_only_for:**
  - Missing BKI company in Frappe (ICT-005 precondition)
  - Missing "Output VAT Payable" account in BKI chart of accounts
  - `bki_sales_income_account` unknown (Finance must specify via user input)
  - Register row missing for a store that the agent tries to bill during L3
  - Destructive action requiring user approval

- **continue_without_pause_through:** code → local verify → pr_creation → l3_handoff → closeout

- **blocker_policy:**
  - Programmatic → fix and continue
  - Missing Customer → run Phase 5 seed script, then continue
  - Missing VAT template → run Phase 5 seed script, then continue
  - SI submission failures during L3 → log defect, investigate, fix code, redeploy, retry
  - Billing hold hit during L3 → expected behavior, verify and move to next scenario

- **signoff_authority:** single-owner (Sam) with Finance consultation on VAT template setup

- **canonical_closeout_artifacts:**
  - `output/s168/missing_customers_audit.json`
  - `output/s168/vat_template_audit.json`
  - `output/s168/receiving_flow_baseline.json`
  - `output/s168/seed_customers_evidence.json`
  - `output/s168/seed_vat_template_evidence.json`
  - `output/s168/phase5_verification.json`
  - `output/s168/HANDOFF_FOR_L3.md`
  - `output/s168/cleanup_evidence.json`
  - `output/s168/verify_phase_*.json` per phase
  - `output/l3/s168/form_submissions.json`
  - `output/l3/s168/api_mutations.json`
  - `output/l3/s168/state_verification.json`
  - `output/l3/s168/si_gl_entries.json`
  - `docs/plans/2026-04-07-sprint-168-bki-store-sale-billing-on-delivery.md` (status → COMPLETED)
  - `docs/plans/SPRINT_REGISTRY.md` (row updated)

---

## Signoff Model

- **mode:** single-owner
- **approver_of_record:** Sam (CEO)
- **note:** Finance (Butch) should be consulted for BKI chart of accounts setup (Phase 5 VAT template requires "Output VAT Payable - BKI" account and `bki_sales_income_account` value). No formal departmental signoff row — single-owner execution.

---

## Agent Boot Sequence

**COLD-START READING ORDER (mandatory, R2-aware):**

0. **Read the AUDIT ROUND 2 ADDENDUM FIRST** (lines ~103-345 of this plan). It is declared authoritative — when it contradicts any later phase body, the addendum wins. Specifically note:
   - **ICT-008 LOCKED (Butch Option C, 2026-04-07 PM):** create NEW parent group `4000100 WHOLESALE / B2B SALES` + NEW posting child `4000101 SALES - BKI TO STORES`. Phase 5 Task 5.3 seed script creates both accounts in order. `BEI Settings.bki_sales_income_account = "4000101 SALES - BKI TO STORES - BKI"`. No swap needed.
   - **ICT-009 LOCKED (Butch, 2026-04-07 PM):** Output VAT = `2102205 OUTPUT VAT PAYABLE` (the old `2103100` was retired in the current COA).
   - **R2-C3 Resolution table** has the confirmed bei-tasks paths — use them verbatim (no "or equivalent" placeholders).
   - **R2-C5 field correction:** `custom_bei_store_billing` lives on **Sales Invoice**, not Material Request.
   - **R2-C6 Session A→B sentinel:** `output/s168/SESSION_A_COMPLETE.flag` is the resume signal.
   - **R2-C9 PR-Handoff:** closeout ends at `AWAITING_REVIEW`, NOT `COMPLETED`. Sam merges.
1. Read the Design Rationale and Requirements Regression Checklist.
2. **Create sprint branch:** `git fetch origin production && git checkout -b s168-bki-store-sale-billing-on-delivery origin/production`. Verify with `git branch --show-current`. NEVER write code on production.
3. Read `data/_CLEANROOM/factcheck_packets/commissary_decisions_2026-02-28/sources/CFO_INTERCOMPANY_Butch_Formoso_2026-02-20.md` — all 5 Q&As verbatim.
4. Read `data/_CONSOLIDATED/01_FINANCE/DECISIONS.md` lines 167-184 (BIL-005 + ICT-001 through ICT-006).
5. Read `data/_CLEANROOM/2026-03-12-s037-store-buyer-entity-register/README.md` and the first 10 rows of the CSV. **Canonical counts (verified 2026-04-07 PM): 35 unique buyer entities × 45 `active_fulfillment_status=active` rows; 3 non-active rows (2 billing-hold + 1 excluded).**
6. Read `hrms/utils/supply_chain_contracts.py:180-248` (register loader + billing hold).
7. Read `hrms/api/commissary.py:782-1071` (current fulfill + broken billing functions to replace).
8. Read `hrms/api/store.py:3683-4099, 5105-5112` (MR creation + receiving flow + current `_get_store_customer`).
9. **Check for Session A sentinel** — if `output/s168/SESSION_A_COMPLETE.flag` exists → this is Session B; run the R2-C6 Session B kickoff gate (see Round 2 addendum), then skip to step 12. If the flag does NOT exist → this is Session A; continue to step 10.
10. **Session A only:** Run Phase 0 audits BEFORE starting Phase 1 — `s168_audit_missing_customers.py`, `s168_vat_template_audit.json`, `s168_audit_bki_coa.py` (R2 addition — writes `output/s168/bki_coa_audit.json` listing `2102205 OUTPUT VAT PAYABLE` and candidate sales income accounts), `receiving_flow_baseline.json`. Phase 0 STOPS before Phase 1 if `2102205 OUTPUT VAT PAYABLE` is missing from BKI company CoA.
11. **Session A only:** Execute phases 0-8 in order. End at Phase 8 Task 8.5 STOP with `output/s168/SESSION_A_COMPLETE.flag` written and pushed.
12. **Session B only:** Execute phases 9-16 in order. End with PR creation (one per repo, same branch name — R2-C10 atomicity rule) and status `AWAITING_REVIEW`. Do NOT self-mark `COMPLETED`.
13. Run L3 in a fresh agent session per S099 — do NOT execute L3 in the same session as the build. L3 evidence files must be committed via `git add -f output/l3/s168/` before closeout (R2-C8 gate).
14. **Governor Feedback Loop:** After PR creation the agent STOPS. Re-enter only for the 4 events listed in the R2 addendum Governor Feedback Loop section (REJECT / NEEDS_FIX / Merge Conflict / Deploy Failure).

## Execution Authority

This sprint is intended for autonomous end-to-end execution (build phase 0-6 + PR creation + L3 handoff). L3 itself runs in a separate fresh session per S099. Do not stop for progress-only updates. Only pause for items listed in the Autonomous Execution Contract `stop_only_for` section.

## Execution Workflow

- Test Python changes: `/local-frappe`
- Deploy changes: `/deploy-frappe` (user-mediated)
- Full workflow: `/agent-kickoff`
- Frappe SSM scripts: `/frappe-bulk-edits`
- E2E testing: `/l3-v2-bei-erp` (run in a separate fresh session)

> **Note:** Deployment is user-mediated. Builder creates PR; Sam handles merge and deploy trigger.

---

## Closeout Phase (Mandatory)

After all phases are implemented and L3 evidence is collected:

0. **L3 evidence gate (R2-C8):** `for f in form_submissions.json api_mutations.json state_verification.json si_gl_entries.json; do test -f output/l3/s168/$f || exit 1; done && git add -f output/l3/s168/ && git commit -m "evidence(S168): L3 artifacts" && git push`
1. Update plan YAML: `status: AWAITING_REVIEW` (R2-C9 — agent does NOT self-mark COMPLETED), fill `completed_date` and `execution_summary`.
2. Update `docs/plans/SPRINT_REGISTRY.md` S168 row with COMPLETED status and PR number(s).
3. `git add -f docs/plans/2026-04-07-sprint-168-*.md docs/plans/SPRINT_REGISTRY.md && git commit -m "docs: S168 closeout"`
4. Push.
5. Verify: `grep -c "is_internal_customer = 1" hrms/api/commissary.py` → 0
6. Verify: `grep -c "make_inter_company_purchase_invoice" hrms/api/commissary.py` → 0
7. Verify: `grep -c "def _create_intercompany_invoices_async" hrms/api/commissary.py` → 0

---

## Verification Summary

1. **Phase 1:** All 5 BEI Settings fields + 3 SI custom fields + 3 Store Receiving custom fields + 1 Stock Entry link field appear in Frappe after `bench migrate`.
2. **Phase 2:** Fulfilling a Material Request creates a Draft SI in BKI company with correct customer, markup, VAT template, and `is_internal_customer=0`.
3. **Phase 3-4:** Completing a receiving submits the Draft SI with `received_qty - rejected_qty`, sets `posting_date = receiving_date`, links `custom_bei_receiving` and `custom_delivery_receipt_no`.
4. **Phase 5:** 35 Customers exist in BKI matching register entries; `BKI Output VAT 12% Sales` template exists with 12% rate; BEI Settings populated.
5. **Phase 6:** Sentry traces show `commissary.create_draft_sales_invoice_for_fulfillment` and `store_billing.submit_sales_invoice_on_delivery_acceptance` events.
6. **Phase 7 L3:** All 8 scenarios pass in fresh session, including partial reject (scenario 4) showing reduced SI qty and full reject (scenario 5) showing Draft SI deletion with stock still posted.
7. **Phase 8:** Plan + registry updated to COMPLETED; old code paths fully removed.

---

## Scope Size Warning

**Total estimated units: 114 (canonical; see YAML `canonical_unit_total`). This is above the 80-unit ceiling mandated by S089.**

Per user directive (2026-04-07), ALL 7 items previously marked out-of-scope are now IN scope because "otherwise the feature will be an unfinished job." The user has explicitly approved the combined scope.

**Execution split mandate:** This plan must be executed across **two fresh agent sessions** to avoid context exhaustion (S092/S099 corrupt-success lesson):

- **Session A (54 units, phases 0-8):** Core sale-billing rewire. Ends with Phase 8 checkpoint commit, Session A L3 handoff for scenarios 1-8, and `output/s168/SESSION_A_COMPLETE.flag` sentinel (R2-C6).
- **Session B (60 units, phases 9-16):** Completeness phases — frontend DR input (Phase 9), logistics auto-billing (Phase 10), credit notes (Phase 11), store P&L allocation (Phase 12), EWT framework (Phase 13), billing-hold admin dashboard (Phase 14), same-company reclassification (Phase 15), and closeout (Phase 16). Ends with PR creation + STOP for Sam review (R2-C9).

Both sessions write to the SAME branch `s168-bki-store-sale-billing-on-delivery`. Both produce PRs to `production` (or one accumulating PR that the user merges after both sessions complete — Session A does not merge until Session B is in the same PR).

Session B depends on Session A being code-complete (but NOT merged) because:
- The logistics auto-billing and credit note flows hook into the Session A `_submit_sales_invoice_on_delivery_acceptance` function
- The billing-hold admin dashboard surfaces Draft SIs created by Session A
- The same-company reclassification uses the same savepoint pattern Session A establishes

### Option to split into S168 + S169

If the user prefers a hard split:
- **S168:** phases 0-8 (core rewire, CFO-critical ICT-001/002/003/006 compliance) → S168 ships by itself
- **S169:** phases 9-15 (completeness items) → new plan, new branch, depends on S168 merged

Recommending against a hard split because items 1-3 (DR input, logistics auto-billing, credit notes) are user-visible pieces of the same billing story. Splitting risks shipping a partial feature that Finance/Store Ops sees as incomplete.

**User has chosen the single-plan path.** Continuing with phases 9-15 below.

---

## Previously "Out of Scope" — NOW IN SCOPE (Phases 9-15)

All of the following were out-of-scope in the draft plan. Per user directive 2026-04-07, they are now mandatory phases. See the new phase sections below the original Phase 8.

---

## Anti-Rewind / Concurrent-Run Protection Contract

- **ownership_matrix:**
  - `hrms/api/commissary.py` (lines 952-1071 area) — exclusive to S168
  - `hrms/api/store.py` (`_get_store_customer`, `complete_receiving`, new helpers) — exclusive to S168
  - `hrms/hr/doctype/bei_settings/bei_settings.json` — exclusive to S168
  - `hrms/fixtures/custom_field.json` — shared with other sprints; S168 only appends new fields, never removes existing entries
- **protected_surfaces:**
  - `fulfill_store_order` behavior (SE creation unchanged)
  - `_create_mr_for_store_order` (MR creation unchanged)
  - `_create_store_receiving_stock_entry` (Material Receipt unchanged)
  - `resolve_store_buyer_entity` (register loader unchanged)
  - All S163 code (`submit_order`, `resolve_group_order_item`, `_aggregate_store_item_groups`, multi-row BEI Store Order Item model)
- **remote_truth_baseline:**
  - Record the current `origin/production` SHA at branch creation
  - S163 is fully merged and live; S168 must not touch any S163 file outside the necessary `complete_receiving` extension
- **reintegration_gate:**
  - Before PR creation, rebase onto current `origin/production` and rerun `scripts/s168_verify_phases.sh all`
  - If any shared files drifted (`commissary.py`, `store.py`, `custom_field.json`), resolve conflicts preserving S163 changes

---

## Ground-Truth Lock

- **evidence_sources:**
  - `data/_CLEANROOM/factcheck_packets/commissary_decisions_2026-02-28/sources/CFO_INTERCOMPANY_Butch_Formoso_2026-02-20.md` — ICT-001 through ICT-005 verbatim CFO answers
  - `data/_CONSOLIDATED/01_FINANCE/DECISIONS.md` lines 167-184 — BIL-005 + ICT-001 through ICT-006 locked decisions
  - `data/_CLEANROOM/2026-03-12-s037-store-buyer-entity-register/store_buyer_entity_register_2026-03-12.csv` — 49 rows, authoritative store→corp mapping
  - `data/Valuation/STORE_OWNERSHIP_ANALYSIS.md` — 54 stores breakdown (JV 23, Managed Franchise 27, Full Franchise 3, Hybrid 1)
  - `hrms/utils/supply_chain_contracts.py:180-248` — existing register loader (code is the source of truth, not a plan description)
  - `hrms/api/commissary.py:952-1071` — current broken implementation (reference for what to replace)
- **count_method:**
  - metric: "stores needing billing"
  - basis: register rows where `buyer_entity_status IN ('confirmed_legal_entity', 'entity_confirmed_store_type_pending')` AND `active_fulfillment_status = 'active'`
  - method: SSM query in Phase 0 audit script
- **authoritative_sections:** Sections "Design Rationale", "End-to-End Target Flow", "Architecture", "Duplication Audit", Phase 0-8, Requirements Regression Checklist
- **unresolved_value_policy:** Any `[UNVERIFIED — requires resolution]` blocks GO

---

## Status Reconciliation Contract

Whenever counts, blockers, or status change, update in the same work unit:
1. `RUN_STATUS.json`
2. `RUN_SUMMARY.md`
3. `output/s168/verify_phase_*.json`
4. `DEFECT_REGISTER.csv` (create if defects found)
5. This plan's status line
6. `SPRINT_REGISTRY.md` S168 row
