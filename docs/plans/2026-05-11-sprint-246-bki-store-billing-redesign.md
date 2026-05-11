---
sprint: S246
sprint_title: "Comprehensive BKI→Store Billing Audit + In-Session CEO Decision + Option 3 Redesign"
plan_filename: 2026-05-11-sprint-246-bki-store-billing-redesign.md
branch: s246-bki-store-billing-redesign
target_repo: hrms
target_base_branch: production
canonical_scope: in
canonical_model_reference: docs/STORE_COMPANY_CANONICAL.md
canonical_preflight: required
status: PR_OPEN_AUDIT_AND_DECISION_ONLY
planned_date: 2026-05-11
audited_date: 2026-05-11
audit_and_decision_executed_date: 2026-05-11
completed_date: null
execution_summary: |
  S246 closing as audit + decision only (Phases 0, 1A, 1B, 2 of planned 0-7 executed).
  CEO chose Option 3-corrected (SE + PI split with SRBNB GR/IR clearing) on 2026-05-11.
  Implementation Phases 3A-7 (~70 work units) deferred to S247.
  Architectural decision frozen in output/l3/s246/DECISION.md.
  S246 work units actually executed: ~30 of planned ~99.
  Followup sprints: S247 (implementation), S248 (reconciliation cron), S249 (G-046 dashboard).
depends_on:
  - PR #745 (l3-billing-sweep-2026-05-11 findings) MERGED to production — HARD GATE for Phase 0
audit_evidence:
  - output/plan-audit/sprint-246-bki-store-billing-redesign/verified_blockers.md
  - output/plan-audit/sprint-246-bki-store-billing-redesign/code_verification.md
amendment_version: v1.1
amendment_summary: 10 CRITICAL + 14 WARNING blockers from 8-domain audit applied inline (scope unchanged)
signoff_authority: single-owner
signoff_owner: Sam Karazi (CEO)
phase_count: 8
work_unit_estimate: ~85
work_unit_ceiling: 80
scope_size_warning: true

evidence_committed:
  - output/l3/s246/SUMMARY.md
  - output/l3/s246/DECISION.md
  - output/l3/s246/audit/CANONICAL_STORE_SPEC.md
  - output/l3/s246/audit/audit_report.md
  - output/l3/s246/audit/per_store_gap.csv
  - output/l3/s246/audit/sentry_30d_sweep.md
  - output/l3/s246/audit/cross_store_transfer_audit.md
  - output/l3/s246/audit/historical_si_gl_audit.md
  - output/l3/s246/verification/verify_canonical_v2_before.json
  - output/l3/s246/verification/verify_canonical_v2_after.json
  - output/l3/s246/verification/l3_sweep_after_redesign.json
  - output/l3/s246/verification/cleanup_839_si_complete.json
  - output/l3/s246/DEFECTS.md
  - output/l3/s246/RUN_STATUS.json

evidence_transient:
  - tmp/s246/probe_*.json
  - tmp/s246/probe_*.py
  - tmp/s246/sweep_run_*.log
  - tmp/s246/traceback_*.txt
  - tmp/s246/ssm_*.log
  - tmp/s246/redesign_dryrun_*.json
---

## Sprint Metadata

| Field | Value |
|---|---|
| Canonical ID | `S246` |
| Registry row added | 2026-05-11 |
| Branch | `s246-bki-store-billing-redesign` |
| Status | PLANNED |
| Target base | `origin/production` |
| Worktree | `F:/Dropbox/Projects/BEI-ERP-s246-bki-store-billing-redesign` |
| PR target | hrms (`Bebang-Enterprise-Inc/hrms`) |

## Goal

Make the BKI→Store inventory + billing flow produce **correct dual-entry posting on the store's books** for all 49 stores. The 2026-05-11 L3 sweep (PR #745) proved that 0 of 49 stores currently produce the canonical "Dr Inventory, Cr Accounts Payable to BKI" outcome the ICT-003 design intended. Three defect classes (A: missing cost_center on 4 stores; B: missing `stock_received_but_not_billed` on 32 stores; C: ERPNext overrides `expense_account` when `update_stock=1`) prove the single-doc design is structurally incompatible with ERPNext's perpetual-inventory model. This sprint audits the full master-data + GL surface, the CEO confirms the architectural direction in-session, then the generator is redesigned to produce **two paired documents per BKI shipment** (Stock Entry for inventory; Purchase Invoice for billing with `update_stock=0`), the master data is normalized, the cleanup of 839 historical test BKI SIs is done, and the L3 sweep is re-run to prove all 49 stores produce the dual entry.

## Executive Summary

This sprint has THREE phases of work and one decision gate:

1. **Audit (Phase 1)** — comprehensive read-only investigation across:
   - The canonical store master-data spec (every field that must be set on Company / Warehouse / Customer / Supplier / Account for a store to be "fully canonical")
   - Extended `verify_canonical_structure.py` asserting that spec across all 49 stores
   - The 7 unanswered items from the 2026-05-11 sweep (BKI SI GL posting; Output→Input VAT flow; cancel+return cascade; the 13 "passing" stores' inventory posting reality; 839 historical test BKI SIs' GL footprint; 30-day Error Log sweep for silent failures; cross-store transfer model)
2. **CEO Decision Gate (Phase 2)** — Sam + Claude review audit findings IN-SESSION. No Denise, no external review. Sam decides between Option 1 (disable perpetual everywhere — band-aid), Option 2 (canonical SRBNB+Warehouse.account everywhere — sustainable, loses 1104210 label), Option 3 (split generator into Stock Entry + Purchase Invoice — proper long-term redesign). Default plan body assumes Option 3.
3. **Redesign + Master-Data + Cleanup (Phases 3-6)** — refactor the generator, normalize master data, validate with L3 sweep, force-delete 839 historical test BKI SIs.
4. **Closeout (Phase 7)** — update plan + registry + PR description; remove worktree.

The plan is over the 80-unit ceiling. See "Scope Size Warning" below — Phase 2 decision gate is the natural split point.

## Scope Size Warning

**Estimated work units: ~85 (ceiling: 80).** Per S089 rule, plans over 80 units should split into multiple plans.

**Recommended split (Sam to confirm at Phase 2 decision gate):**
- **S246 (this plan)** — Phases 0-2 = audit + in-session decision (~30 units)
- **S247 (new, written AFTER S246 decision)** — Phases 3-7 = Option 3 redesign + master-data + sweep + cleanup (~55 units)

**Why this is the right split point:**
1. Audit might reveal that Option 3 is wrong; Option 2 or a hybrid might emerge. Committing to a 55-unit implementation BEFORE seeing audit findings is premature.
2. Phase 2 decision gate is a real gate. Writing the implementation plan AFTER the decision lets the implementation plan be specific to the chosen option, not contingent.
3. Cold-start agent fatigue: a 55-unit implementation in a fresh session is cleaner than continuing a 30-unit audit session.

**If Sam chooses to proceed as single sprint (~85 units in one execution):** the agent must accept that context-fatigue risk increases. The audit findings must be written to `output/l3/s246/audit/audit_report.md` BEFORE Phase 3 starts so the implementation can be re-read from disk if context compaction occurs mid-execution.

## Design Rationale (For Cold-Start Agents)

### Why this exists

The 2026-05-11 L3 billing sweep (PR #745) exercised the BKI→Store PI generator (S238) across all 49 candidate buyer Companies and found that the canonical design intent is silently broken on 100% of stores. The sweep was triggered after S243 (canonical CoA backfill) and S238 hotfixes #1-3 (PRs #740/#741/#742) to validate that the BKI→Store billing chain works correctly. It does not.

### The three defects (full evidence in `tmp/billing-sweep/DEFECTS.md` + `output/l3/billing-sweep-2026-05-11/DEFECTS.md`)

**DEFECT A — 4 stores miss `Company.cost_center`** (ROA, SMM, SMMM, SMS — the same 4 stores S243 seeded CoA for). PI generator `_resolve_per_store_cost_center` throws → savepoint rollback → silent miss.

**DEFECT B — 32 stores miss `Company.stock_received_but_not_billed`** when `enable_perpetual_inventory=1`. ERPNext's `purchase_invoice.set_expense_account()` calls `get_company_default("stock_received_but_not_billed")` which throws `ValidationError` → savepoint rollback → silent miss. Full traceback captured in `output/l3/billing-sweep-2026-05-11/evidence/one_failure_result.json` for AYALA FAIRVIEW TERRACES.

**DEFECT C — ERPNext overrides expense_account** when `update_stock=1`. The generator computes `expense_account = "1104210 - Inventory-from-Commissary"` correctly, then ERPNext's `set_expense_account(for_validate=True)` overwrites it with `Warehouse.account`. Visible on 2 stores (GHO `Stock In Hand - GHO`, SMK `Stock In Hand - SMK`) where SRBNB happens to be set so PI insertion succeeds. Latent for the other 30 stores that fail earlier at SRBNB check.

**DEFECT D — informational.** 13 "PASS" stores pass only because `enable_perpetual_inventory=0` — ERPNext auto-stock-accounting is skipped entirely. PIs insert but post **zero stock GL** on submit. The design intent of `update_stock=1` is silently dropped on 100% of active stores.

### Why Option 3 is the recommended architecture

CEO question 2026-05-11: "Are these solutions band-aid or permanent and proper for a sustainable ERP setup?"

| Option | Trade-off | Long-term verdict |
|---|---|---|
| 1. Disable perpetual everywhere | Strips inventory-on-PI feature. Requires separate manual Stock Entry per shipment. Fast (1 hour). | 🟥 **Band-aid.** Structural debt. |
| 2. Canonical SRBNB + Warehouse.account=1104210 | Use ERPNext as designed. PI gets right account via warehouse override. But ICT-003 design's "1104210 - Inventory-from-Commissary" label becomes nominal — actual inventory journal hits `Stock In Hand - <ABBR>` always. Lots of master-data work. | 🟡 **Sustainable but compromised.** |
| 3. Split generator into Stock Entry + Purchase Invoice | Two-document model. Stock Entry = inventory transfer (uses inventory accounts cleanly). Purchase Invoice = billing only (`update_stock=0`). Each doc has one job. Each can be cancelled / amended independently. Matches how SAP / Oracle / NetSuite handle commissary→store shipments. | 🟢 **Proper long-term.** |

### Key trade-off decisions

**Decision 1: Two paired documents per shipment, not one.**
Considered: keep the single-PI model (Options 1/2). Rejected because:
- The single-PI model only works if ERPNext's `set_expense_account` doesn't override the manually-set account — but our PR #741 currency hotfix proves ERPNext's validators DO override Field values during `for_validate=True` re-validation. We can't reliably set a custom expense account on `update_stock=1` PIs.
- Separating inventory and billing into two docs lets us use ERPNext's `Material Receipt` Stock Entry (which posts to canonical inventory accounts cleanly via the warehouse setup) for stock, and a `update_stock=0` PI for billing (which doesn't trigger expense_account override).
- BIR-correct interpretation: a delivery receipt and an invoice are conceptually different documents anyway. Mixing them in one ERPNext doc was always a compromise.

**Decision 2: Stock Entry type = "Material Receipt" not "Material Transfer".**
Considered: `Material Transfer` from a BKI source warehouse to the store warehouse. Rejected because:
- That ties BKI's inventory directly to the store's inventory in a single SLE, which is exactly the inter-company coupling we are trying to avoid per ICT-001..006 separate-legal-entity stance.
- `Material Receipt` on the store's books posts a positive stock entry to the store warehouse using the store's own inventory account. The corresponding BKI-side outflow is recorded separately via BKI's own Sales Invoice + Delivery Note flow (untouched by this sprint).

**Decision 3 (v1.1 corrected): SI submit fires BOTH generators independently with savepoint isolation; reconciliation cron sweeps half-paired SIs.**

**v1.0 said "atomically" — that was wrong.** Two contradictory statements in the v1 plan: Design Rationale Decision 3 said "atomically" while Phase 3B.3 said "Do NOT block the SI submit" using savepoint isolation. These are mutually exclusive. v1.1 picks the savepoint-isolation path (matches the existing PI generator pattern) for these reasons:
- BKI's SI submit must NEVER fail because of a downstream paired-doc issue (Finance team would lose the ability to bill).
- Independent savepoint per generator: PI failure rolls back PI savepoint only, SE failure rolls back SE savepoint only. SI submits cleanly.
- Half-paired state is acceptable for hours, not days. A daily reconciliation cron (new in v1.1) finds half-paired SIs (PI without SE, or SE without PI) and either retries generation or alerts on Sentry.
- Considered "true atomicity" (one savepoint wraps both): rejected because a single SE failure would prevent BOTH docs from existing for that shipment, which is worse than a single missing doc that gets fixed within 24h.
- Considered "block SI submit on failure": rejected because it changes BKI's own billing workflow per ICT-003.

**Cascade-cancel order:** SE first, then PI (reverse of creation order). This is the textbook reversal pattern — last-created cancelled-first. Cancel hooks registered in `hooks.py` in that order.

**Decision 5 (NEW in v1.1): SRBNB is the GR/IR clearing account, not just a validation gate.**

**v1.0 misunderstood `stock_received_but_not_billed`** as just an ERPNext validation requirement. It's actually the canonical Goods Receipt / Invoice Received (GR/IR) clearing account used by every standard ERP for receiving from external suppliers. The audit (system-arch ARCH-11, ph-finance F1+F2) caught that v1.0's JE chain would double-count inventory because both SE and PI would post to `1104210` directly.

**v1.1 corrected JE pattern:**
- **SE (Material Receipt):** `Dr 1104210 - Inventory-from-Commissary` (via Warehouse.account) / `Cr SRBNB - Stock Received But Not Billed - <ABBR>` (set explicitly on SE item.expense_account)
- **PI (`update_stock=0`):** `Dr SRBNB - Stock Received But Not Billed - <ABBR>` (clears the SE credit) / `Cr 2103210 - AP-Trade-BKI - <ABBR>` (via PI.credit_to)
- **Net per shipment:** `Dr 1104210 Inventory / Cr 2103210 AP`. SRBNB nets to zero. Clean.

This is the textbook GR/IR pattern used by SAP, Oracle, NetSuite, ERPNext, etc.

**Decision 4: `bki_si_reference` field stays on both PI and SE.**
Considered: rename to `bki_paired_si` for the SE. Rejected because:
- Reusing the same field name simplifies the dashboard query model in S246 follow-up (the future G-046 update queries `bki_si_reference` across PI + SE).
- Custom Field is already installed on PI; same field on SE is a one-line fixture.

### Known limitations + mitigations

**Limitation 1: ERPNext PI cancel propagation to JE.** When the PI is cancelled, its JE is auto-reversed by ERPNext. The Stock Entry's own JE must be cancelled separately. Cascade-cancel handler must cancel BOTH docs and verify both JEs are reversed.

**Limitation 2: Posting-date lock on the PI.** Original generator includes `lock_posting_date_on_bki_paired_pi` to prevent finance team from changing the PI's posting date. The SE must have an equivalent lock or finance can shift the inventory landing date independently of the billing date, creating period mismatch.

**Limitation 3: The 839 historical test BKI SIs include `submitted` docs with cascaded PIs.** Those PIs created GL entries. Force-deleting them is non-trivial — must cancel SI (which reverses JE) then cancel cascade-removed PI (no longer exists), then force-delete the SI doc. For docs already in `cancelled` state, force-delete works directly.

**Limitation 4: `enable_perpetual_inventory` is per-Company.** The audit may reveal we want this set consistently across all 49 stores. Changing this flag on a Company with existing GL has implications — ERPNext changes how new entries auto-post. Must audit historical GL on the 13 currently-`=0` stores before flipping any to `=1`.

### Source references

- `tmp/billing-sweep/DEFECTS.md` — full root-cause analysis
- `output/l3/billing-sweep-2026-05-11/evidence/one_failure_result.json` — AFT full traceback proving DEFECT B
- `output/l3/billing-sweep-2026-05-11/evidence/perp_result.json` — per-Company `enable_perpetual_inventory` + SRBNB state
- `output/l3/billing-sweep-2026-05-11/evidence/sweep_result.json` — 49-store verdict counts
- `hrms/api/bki_store_pi_generator.py` (origin/production @ 7ba36bf6b) — current generator source
- `hrms/api/bki_si_naming.py` — autoname hook (unchanged in this sprint)
- `scripts/billing_sweep/multi_store_smoke.py` — reusable runner (PR #745)
- `docs/STORE_COMPANY_CANONICAL.md` — canonical model law
- ICT-001..008 design notes (from S238 brainstorm; embedded in `tmp/s238/BIR_SERIES_RESEARCH.md`)

## Requirements Regression Checklist

Every yes/no the executing agent must verify against its own work, BEFORE marking a phase complete:

- [ ] Did Phase 0 spawn a worktree at `F:/Dropbox/Projects/BEI-ERP-s246-bki-store-billing-redesign` from `origin/production` (NOT `git checkout -b` in the main checkout)?
- [ ] Did Phase 1A write the canonical store master-data spec to `output/l3/s246/audit/CANONICAL_STORE_SPEC.md` BEFORE running the verifier extension?
- [ ] Does the extended `verify_canonical_structure.py` v2 assert ALL fields listed in the spec (not just CoA + Customer + Warehouse existence)?
- [ ] Did Phase 1B audit ALL 7 unanswered items (BKI SI GL posting; Output→Input VAT flow; cancel+return; 13 "passing" stores; 839 historical test BKI SIs; Error Log 30d sweep; cross-store transfers)?
- [ ] Did Phase 2 produce a written `output/l3/s246/DECISION.md` signed by Sam BEFORE Phase 3 starts? (HARD GATE)
- [ ] Did the agent stop and re-plan if Sam chose Option 1 or Option 2 at Phase 2? (Plan body assumes Option 3.)
- [ ] Does Phase 3 add a NEW file `hrms/api/bki_store_stock_entry_generator.py` (Stock Entry generator)?
- [ ] Does Phase 3 modify `hrms/api/bki_store_pi_generator.py` to use `update_stock=0` and remove `pi.set_warehouse` mirror?
- [ ] Does Phase 3 update `hrms/hooks.py` to register the new Stock Entry generator on `Sales Invoice.on_submit` ALONGSIDE the PI generator?
- [ ] Does Phase 3 register cancel-cascade for the Stock Entry on `Sales Invoice.on_cancel`?
- [ ] Did Phase 4 use `/frappe-bulk-edits` for master-data UPDATEs (NOT ad-hoc SQL)?
- [ ] Did Phase 4 record every master-data change in `output/l3/s246/teardown_ledger.json` so it can be reverted if rollback is needed?
- [ ] Did Phase 5 re-run `scripts/billing_sweep/multi_store_smoke.py` (updated to expect dual-doc outcome) and produce `output/l3/s246/verification/l3_sweep_after_redesign.json` with 49/49 PASS?
- [ ] Did Phase 6 force-delete all 839 historical test BKI SIs and their cascaded PIs, with the count verified post-run?
- [ ] Did closeout (Phase 7) update plan YAML status to COMPLETED, SPRINT_REGISTRY.md row to COMPLETED, and PR description with task-by-task status?
- [ ] Does every new/modified `@frappe.whitelist()` endpoint call `set_backend_observability_context()` per `.claude/rules/sentry-observability.md`?
- [ ] Does the closeout phase run `python scripts/verify_canonical_structure.py` AND assert zero NEW violations?
- [ ] Was the worktree removed cleanly at the end (no leftover `git status` output)?
- [ ] **v1.1 NEW (Blocker 1):** Does `hrms/hooks.py` show `on_submit` and `on_cancel` as Python LISTS (`[...]`), not strings? Did the STRING→LIST conversion happen explicitly (not via naive append)?
- [ ] **v1.1 NEW (Blocker 2):** Does the PI generator's `_mirror_items` set `expense_account = srbnb_account` (NOT `1104210` directly)? Does the SE generator's item-append set `expense_account = srbnb_account` (NOT default to stock_adjustment_account)? Did the L3 sweep verify the GR/IR JE chain nets cleanly (Dr 1104210 once, Cr 2103210 once, SRBNB nets to zero)?
- [ ] **v1.1 NEW (Blocker 3):** Does Design Rationale Decision 3 match the actual generator behavior (savepoint-isolation, NOT atomic)? Did Phase 5 include reconciliation cron sketch or future-sprint note?
- [ ] **v1.1 NEW (Blocker 4):** Did P0.0 verify PR #745 is MERGED before any other Phase 0 task ran?
- [ ] **v1.1 NEW (Blocker 5):** Are ALL plan output paths under `output/l3/s246/` (NOT `output/s246/`)? Will the bei-release-manager gate find the evidence?
- [ ] **v1.1 NEW (Blocker 6):** Did Phase 4 split into 4a (pre-deploy) + 4b (post-deploy)? Did 4a run before PR merge and 4b run after deploy + migrate?
- [ ] **v1.1 NEW (Blocker 7):** Were both BEI Settings toggle fields (`enable_bki_store_pi_generator`, `enable_bki_store_stock_entry_generator`) installed via Phase 3C and verified via `frappe.get_meta` post-migrate?
- [ ] **v1.1 NEW (Blocker 8):** Is `lock_posting_date_on_bki_paired_se` registered on `Stock Entry.validate` hook in `hrms/hooks.py`?
- [ ] **v1.1 NEW (Blocker 9):** Did P6.0 disable both generator toggles BEFORE the 839 cleanup ran? Did P6.6 re-enable them AFTER?
- [ ] **v1.1 NEW (Blocker 10):** Does `hrms/hooks.py` `Sales Invoice.on_cancel` list have `cascade_cancel_store_stock_entry` FIRST and `cascade_cancel_store_pi` SECOND?

## Canonical Model Preflight (Mandatory)

Executing agent MUST run before the first code change:
```
python scripts/verify_canonical_structure.py
```
If the verifier prints `[VIOLATION]`, STOP and ask the user. Do NOT add records, flip fields, or create customers/warehouses to paper over a violation — fix the master data with the canonical scripts.

**Canonical law (summary — full rules in `docs/STORE_COMPANY_CANONICAL.md`):**
- Every store has EXACTLY 1 per-store Company + 1 Warehouse + 1 billing Customer + 1 Internal Customer.
- All four share the same name string (e.g. `SM TANZA - BEBANG MEGA INC.`).
- Per-store Company's `parent_company` links to the legal entity parent (if any).
- Warehouse.company = the per-store Company (NEVER the parent).
- Billing Customer: `customer_name` = per-store Company name, `is_internal_customer=0`, `tax_id` = legal entity BIR TIN.
- Internal Customer: `represents_company` = per-store Company, `is_internal_customer=1`, no TIN. Used by S206 labor journals ONLY — never for regular SIs.

**Forbidden in this plan (without explicit CEO approval in-line):**
- Creating a second Warehouse/Company/Customer for an existing store.
- Ad-hoc SQL mutations on `tabCompany` / `tabWarehouse` / `tabCustomer`. Use `/frappe-bulk-edits` exclusively.
- Adding new fallback logic to `resolve_store_buyer_entity`.
- Using the parent Company's Customer for store-level billing (breaks per-store P&L).
- Reusing an Internal Customer for a regular SI.
- Deleting a master record with transactions (use `disabled=1`).

**Scope claim:** This plan READS every per-store Company, Warehouse, Customer, Supplier, and Account on 49 stores during the Phase 1 audit. This plan WRITES the following per-store master-data via `/frappe-bulk-edits` in Phase 4: `Company.cost_center` (4 rows), `Company.stock_received_but_not_billed` (up to 49 rows depending on Phase 2 decision), `Warehouse.account` (up to 49 rows), `Company.enable_perpetual_inventory` (consistency UPDATE if needed). This plan creates the following new code: `hrms/api/bki_store_stock_entry_generator.py` (new file), `hrms/hr/custom_field/bki_si_reference` on Stock Entry (Custom Field via Frappe fixtures). This plan modifies the following: `hrms/api/bki_store_pi_generator.py` (refactor to `update_stock=0`), `hrms/hooks.py` (add SE generator on SI submit/cancel), the SE generator's own Custom Fields if needed.

## Canonical Model Binding

This feature binds to the canonical model as follows:
- Reads `Company.cost_center`, `Company.default_currency`, `Company.enable_perpetual_inventory`, `Company.stock_received_but_not_billed` per buyer store
- Reads `Warehouse.account`, `Warehouse.company` per buyer store warehouse
- Reads `Customer.name == Company.name` to identify per-store buyer (canonical filter `frappe.db.exists("Company", doc.customer)`)
- Reads `Supplier.name = "BEBANG KITCHEN INC. - Trade"` as the global BKI trade supplier
- Reads `Account.account_number IN ('1104210','1106210','2103210')` per buyer Company for AP + VAT + inventory routing
- Writes Stock Entry (`stock_entry_type='Material Receipt'`) with `company = buyer_company` and `items[].t_warehouse = buyer_company` (canonical: Warehouse name == Company name)
- Writes Purchase Invoice with `company = buyer_company`, `supplier = "BEBANG KITCHEN INC. - Trade"`, `update_stock = 0`, `credit_to = <buyer_company's 2103210 account>`
- Uses `bki_si_reference` Custom Field (already on PI; added in this sprint to SE) for natural-key SI→PI / SI→SE linkage

Does NOT:
- Infer store identity from warehouse_name string parsing
- Hardcode parent Company names (BEBANG MEGA INC., etc.)
- Add a `store_id` / `branch_code` field parallel to the canonical model
- Modify `resolve_store_buyer_entity` (this generator uses a different filter — Customer.name == Company.name — by design, per ICT-003)
- Use parent Company's Customer for any billing
- Use an Internal Customer for any billing

## Ground-Truth Lock

- **evidence_sources:**
  - `output/l3/billing-sweep-2026-05-11/evidence/sweep_result.json` → proves 13/30/2/4 verdict split across 49 stores
  - `output/l3/billing-sweep-2026-05-11/evidence/perp_result.json` → proves `enable_perpetual_inventory` is the sole differentiator between PASS and FAIL
  - `output/l3/billing-sweep-2026-05-11/evidence/one_failure_result.json` → proves DEFECT B with full Python traceback at `erpnext/accounts/doctype/purchase_invoice/purchase_invoice.py:455`
  - `output/l3/billing-sweep-2026-05-11/evidence/probe_result.json` → proves per-store readiness state across 49 stores
  - `docs/STORE_COMPANY_CANONICAL.md` → canonical law
  - `hrms/api/bki_store_pi_generator.py` @ origin/production 7ba36bf6b → current generator source
- **count_method:**
  - metric: 49 candidate buyer Companies
  - basis: `SELECT name FROM tabCompany WHERE name != 'BEBANG KITCHEN INC.' AND IFNULL(is_group, 0) = 0` from probe 2026-05-11
  - method: read-only SSM probe (see `scripts/billing_sweep/probe_per_store_readiness.py`)
- **authoritative_sections:**
  - Sections "Goal" / "Executive Summary" / "Requirements Regression Checklist" / Phase 0-7 task tables are authoritative for execution
  - "Design Rationale" is traceability — execution flows from the task tables
- **normalization_required:**
  - Any amendment that changes counts (49 stores, 839 test SIs, 3 defect classes) must update the authoritative sections in the same edit
- **unresolved_value_policy:**
  - Operator-facing unknowns → `[UNVERIFIED — requires resolution]`
- **normalization_artifacts:**
  - `output/l3/s246/audit/audit_report.md` (Phase 1 output, becomes authoritative source for Phase 2 decision)
  - `output/l3/s246/DECISION.md` (Phase 2 output, becomes authoritative source for Phase 3 implementation)

## Phase Budget Contract

- **phase_unit_budget (v1.1 — updated after audit amendments):**
  - Phase 0 (Boot + Worktree + PR #745 gate + sprint-collision check) → 5 units (was 3, added 2 for HARD GATES)
  - Phase 1A (Canonical Spec + Extended Verifier) → 12 units
  - Phase 1B (Audit 7 Unanswered Items + Error Log Sweep) → 13 units
  - Phase 2 (CEO Decision Gate) → 2 units
  - Phase 3A (PI Generator Refactor to update_stock=0 + SRBNB routing) → 11 units
  - Phase 3B (Stock Entry Generator + Hook STRING→LIST + Cascade Order + SE Posting-Date Lock + Internal Customer Guard) → 14 units (was 11, +3 for new tasks 7b/7c + STRING→LIST gravity)
  - Phase 3C (BEI Settings Kill Switches + SE Custom Field Install) → 5 units (NEW in v1.1)
  - Phase 4a (Pre-deploy cost_center on 4 stores) → 3 units (split from old P4)
  - Phase 4b (Post-deploy SRBNB + Warehouse.account + Supplier.accounts + rollback runbook) → 9 units (split from old P4)
  - Phase 5 (L3 Sweep — single-store smoke first + 49-store sweep + GR/IR JE chain assertion + Submitted-state cascade test) → 12 units (was 10, +2 for new assertions)
  - Phase 6 (Historical BKI SI Cleanup with generator-toggle disable/restore) → 8 units (was 6, +2 for toggle dance)
  - Phase 7 (Closeout) → 5 units
- **hard_limit:** 15 units per sub-phase. Phase 3B at 14 is acceptable. Phase 1B at 13 is acceptable.
- **preferred_split_threshold:** 12 units
- **normalization_rule:** if a phase splits during execution, the main phase table is updated in the same edit
- **total:** ~99 units (was 85; over the 80-unit ceiling but Scope Size Warning section was already in v1.0 and remains valid — natural split at Phase 2 decision gate)

## Autonomous Execution Contract

- **completion_condition:**
  - All Phase 0-7 tasks marked DONE per the verification scripts
  - `output/l3/s246/RUN_STATUS.json` set to `COMPLETED`
  - `output/l3/s246/SUMMARY.md` written with final outcome
  - `output/l3/s246/DECISION.md` written with Sam's signoff
  - `scripts/verify_canonical_structure.py` (v2 — extended) prints zero NEW violations vs Phase 1A baseline
  - L3 sweep (`scripts/billing_sweep/multi_store_smoke.py` updated for dual-doc expectations) prints 49/49 PASS
  - 0 leftover test BKI SIs and 0 orphan PIs/SEs (verified post-cleanup)
  - Plan YAML `status` updated to `COMPLETED`
  - `SPRINT_REGISTRY.md` row updated to COMPLETED with PR refs
  - Both updated and pushed via `git add -f docs/plans/...`
  - Worktree removed cleanly
- **stop_only_for:**
  - Missing credentials/access (Doppler, SSM, GH_TOKEN)
  - Destructive approval requiring CEO authorization (this plan has ONE such gate: Phase 2 decision)
  - Genuine business-policy decision surfaced during audit (Phase 1 may reveal something requiring decision)
  - Direct conflict with unrelated in-flight changes (e.g., S225/S232 sweep state)
  - L3 sweep PASS rate < 49/49 after redesign (don't claim COMPLETED with anything less)
- **continue_without_pause_through:**
  - audit → decision → redesign code → master-data → L3 → cleanup → PR creation → closeout
- **blocker_policy:**
  - Programmatic error → fix and continue
  - Repeated failure 3× same class → grounded research (read source files + ERPNext docs), then continue
  - Evidence mismatch / stale authoritative section → normalize plan and continue
  - Business-data/policy / architectural pivot → pause + present BLOCKER + OPTIONS + RECOMMENDATION format
- **signoff_authority:** `single-owner` (Sam Karazi, CEO)
- **canonical_closeout_artifacts:**
  - `output/l3/s246/SUMMARY.md`
  - `output/l3/s246/DECISION.md`
  - `output/l3/s246/DEFECTS.md`
  - `output/l3/s246/RUN_STATUS.json`
  - `output/l3/s246/audit/audit_report.md`
  - `output/l3/s246/audit/CANONICAL_STORE_SPEC.md`
  - `output/l3/s246/audit/per_store_gap.csv`
  - `output/l3/s246/verification/verify_canonical_v2_before.json`
  - `output/l3/s246/verification/verify_canonical_v2_after.json`
  - `output/l3/s246/verification/l3_sweep_after_redesign.json`
  - `output/l3/s246/verification/cleanup_839_si_complete.json`
  - `docs/plans/2026-05-11-sprint-246-bki-store-billing-redesign.md` (status updated)
  - `docs/plans/SPRINT_REGISTRY.md` (status updated)

## Status Reconciliation Contract

Whenever counts, blockers, stage, or certification status changes during execution, update in the same work unit:
1. `output/l3/s246/RUN_STATUS.json`
2. `output/l3/s246/SUMMARY.md`
3. `output/l3/s246/DEFECTS.md` (if new defect found)
4. `docs/plans/2026-05-11-sprint-246-bki-store-billing-redesign.md` (status line + amendment block)
5. `docs/plans/SPRINT_REGISTRY.md` (status column)
6. The PR description (if PR is open)

## Signoff Model

- **mode:** `single-owner`
- **approver_of_record:** Sam Karazi (CEO, sole signoff authority)
- **signoff_artifact:** `output/l3/s246/DECISION.md` (Phase 2 output, names the chosen Option + confirms scope for Phase 3+)
- **note:** Per Sam's directive 2026-05-11: NO Denise / external review for this decision. Sam and Claude discuss IN-SESSION and decide TODAY.

## Anti-Rewind / Concurrent-Run Protection Contract

- **ownership_matrix:**
  - artifact: `output/l3/s246/SURFACE_OWNERSHIP_MATRIX.csv` (Phase 0 deliverable)
  - rule: this plan owns `hrms/api/bki_store_pi_generator.py`, `hrms/api/bki_store_stock_entry_generator.py` (new), `hrms/hooks.py` SI on_submit + on_cancel lines for BKI generators, `scripts/verify_canonical_structure.py` (Phase 1A extension), `scripts/billing_sweep/multi_store_smoke.py` (Phase 5 update). NO other sprint should touch these during S246 execution.
- **protected_surfaces:**
  - artifact: `output/l3/s246/PROTECTED_SURFACE_REGISTRY.csv`
  - rule: do NOT touch `hrms/api/bki_si_naming.py` (autoname hook stays as-is); do NOT touch `hrms/utils/supply_chain_contracts.resolve_store_buyer_entity` (this generator uses a different filter by design); do NOT touch S232 sales sync / S242 POS channel discriminator code; do NOT touch the 49 stores' canonical Company / Warehouse / Customer names (this plan only adjusts FIELDS on them, never renames)
- **remote_truth_baseline:**
  - artifact: `output/l3/s246/REMOTE_TRUTH_BASELINE.json`
  - fields:
    - `repo`: Bebang-Enterprise-Inc/hrms
    - `release_branch`: production
    - `release_head_sha`: (filled by Phase 0 from `git rev-parse origin/production`)
    - `live_evidence_basis`: `output/l3/billing-sweep-2026-05-11/evidence/sweep_result.json` (PR #745)
- **touched_file_routing:**
  - artifact: `output/l3/s246/TOUCHED_FILE_ROUTING.csv` (Phase 0 deliverable)
- **active_run_coordination:**
  - artifact: `output/l3/s246/state/ACTIVE_RUN.json`
  - rule: claim on Phase 0 start, release on Phase 7 closeout
- **pretouch_backup:**
  - artifact: `output/l3/s246/state/PRETOUCH_BACKUP.json`
  - rule: before Phase 4 master-data UPDATEs, snapshot the current value of every field that will change so a rollback is possible
- **supersession_map:**
  - artifact: `output/l3/s246/state/SUPERSESSION_MAP.json`
  - rule: when S246 ships, the L3 billing sweep findings PR #745 becomes "audit-only / historical"; the S246 implementation is the new authoritative state
- **touch_preservation:**
  - artifact: `output/l3/s246/ledgers/TOUCH_PRESERVATION_LEDGER.csv`
  - rule: cleanup of historical 839 test BKI SIs (Phase 6) only proceeds after every other phase has merged or has a clean rollback path

## Agent Boot Sequence

1. **Read this plan fully** (this file in its entirety).
2. **Spawn a worktree from `origin/production`:**
   ```bash
   cd F:/Dropbox/Projects/BEI-ERP && git fetch origin --prune
   git worktree add F:/Dropbox/Projects/BEI-ERP-s246-bki-store-billing-redesign -B s246-bki-store-billing-redesign origin/production
   cd F:/Dropbox/Projects/BEI-ERP-s246-bki-store-billing-redesign
   ```
   NEVER write code on production. NEVER use `git checkout -b` inside the main checkout. CWD stays in the worktree until closeout.
3. **Read `docs/STORE_COMPANY_CANONICAL.md`** in full.
4. **Read `docs/plans/SPRINT_REGISTRY.md`** for cross-sprint context (S238/S243/S206/S225 are recent neighbors).
5. **Read `tmp/billing-sweep/DEFECTS.md`** + `output/l3/billing-sweep-2026-05-11/SUMMARY.md` + `output/l3/billing-sweep-2026-05-11/DEFECTS.md`.
6. **Read source files:**
   - `hrms/api/bki_store_pi_generator.py` (the file to refactor)
   - `hrms/api/bki_si_naming.py` (autoname hook — DO NOT modify)
   - `hrms/hooks.py` (find the SI on_submit / on_cancel handlers)
   - `scripts/verify_canonical_structure.py` (the file to extend in Phase 1A)
   - `scripts/billing_sweep/multi_store_smoke.py` (the file to update in Phase 5)
7. **Run canonical preflight:** `python scripts/verify_canonical_structure.py` and confirm no PRE-EXISTING violations beyond the known list. If new violations appear, STOP and report.
8. **Confirm all dependencies are met:** the worktree is clean, the canonical verifier passes, and the L3 sweep evidence files (`output/l3/billing-sweep-2026-05-11/evidence/*.json`) are readable.

## Execution Authority

This sprint is intended for autonomous end-to-end execution **except for the Phase 2 CEO Decision Gate**, which requires Sam's in-session input. The agent presents audit findings, Sam decides Option 1/2/3, and execution continues. The agent does NOT stop for progress-only updates.

Stop only for items listed in `stop_only_for` above.

---

## Phase 0 — Boot + Worktree + Baseline (3 units)

| # | Task | Owner | Verification |
|---|------|-------|--------------|
| P0.0 | **v1.1 NEW HARD GATE (Blocker 4) — PR #745 merged check.** Run `GH_TOKEN="" gh pr view 745 --repo Bebang-Enterprise-Inc/hrms --json state,mergedAt`. If `state != "MERGED"`, **STOP** and present BLOCKER format to Sam: "PR #745 must merge before Phase 0 can proceed — the worktree boots from origin/production which doesn't have the sweep evidence files until PR #745 lands." Plan body's `evidence_sources` (per Ground-Truth Lock section) reference `output/l3/billing-sweep-2026-05-11/...` which exists only on PR #745's head branch as of plan-write. Do NOT attempt to cherry-pick or copy the files manually. | `gh pr view 745` returns `state=MERGED`; `output/l3/billing-sweep-2026-05-11/SUMMARY.md` exists in the worktree |
| P0.0b | **v1.1 NEW (WARNING F-11) — Concurrent-sprint coordination check.** Run `ls output/*/state/ACTIVE_RUN.json 2>/dev/null` to check for other in-flight sprints. If S225 (canonical warehouse cleanup) or any other sprint touching `tabWarehouse` / `tabCompany` master data has an `ACTIVE_RUN.json` showing `status: in_progress`, **STOP** and present BLOCKER: "Phase 4 master-data UPDATEs would collide with active sprint X — wait for it to complete or coordinate." | No other ACTIVE_RUN.json shows status: in_progress for an overlapping sprint |
| P0.1 | Spawn worktree per Agent Boot Sequence step 2 | agent | `pwd` returns `F:/Dropbox/Projects/BEI-ERP-s246-bki-store-billing-redesign`; `git branch --show-current` returns `s246-bki-store-billing-redesign` |
| P0.2 | Create `output/l3/s246/` + `tmp/s246/` directories with subdirs (`audit/`, `verification/`, `state/`, `ledgers/`) | agent | `ls output/l3/s246/` shows all 4 subdirs |
| P0.3 | Write `output/l3/s246/REMOTE_TRUTH_BASELINE.json` with current `origin/production` SHA + sweep evidence reference | agent | File exists; `release_head_sha` matches `git rev-parse origin/production` |
| P0.4 | Write `output/l3/s246/SURFACE_OWNERSHIP_MATRIX.csv` listing the 5 owned files (PI generator, SE generator new, hooks.py, canonical verifier, sweep runner) | agent | File exists with 5 rows |
| P0.5 | Run `python scripts/verify_canonical_structure.py` and save output to `output/l3/s246/verification/verify_canonical_v1_baseline.txt` | agent | File exists; output captured; new violations = 0 (pre-existing OK) |
| P0.6 | Write `output/l3/s246/state/ACTIVE_RUN.json` with `{sprint: S246, started_at: <utc>, phase: 0, status: in_progress}` | agent | File exists |
| P0.7 | Initial commit: `chore(S246 P0): boot + worktree + baseline state` | agent | `git log -1 --oneline` shows the boot commit |

**MUST_MODIFY:** `output/l3/s246/REMOTE_TRUTH_BASELINE.json`, `output/l3/s246/SURFACE_OWNERSHIP_MATRIX.csv`, `output/l3/s246/state/ACTIVE_RUN.json`.

---

## Phase 1A — Canonical Store Master-Data Spec + Extended Verifier (12 units)

### Goal
Define the full "what makes a store Company fully canonical" spec, then extend `scripts/verify_canonical_structure.py` to assert it across all 49 stores. This is the missing checklist that has been allowing per-sprint drift for months.

### Tasks

| # | Task | Verification |
|---|------|--------------|
| P1A.1 | Write `output/l3/s246/audit/CANONICAL_STORE_SPEC.md` enumerating EVERY field that must be set on a per-store Company + Warehouse + Customer + Supplier + Account for the store to be operationally complete. Use the following starter list (extend during research): Company.{name, abbr, parent_company, default_currency, cost_center, enable_perpetual_inventory, stock_received_but_not_billed, default_inventory_account, stock_adjustment_account, default_receivable_account, default_payable_account, country, entity_category, operational_status, store_ownership_type, tax_id}; Warehouse.{name, warehouse_name, company, account, is_group, disabled, custom_area_supervisor}; Customer.{name, customer_name, is_internal_customer, tax_id}; Account rows for `1104210`, `1106210`, `2103210`, `1130000` (Receivables), `2100000` (Payables), `4110002` (Sales-Internal if applicable), Stock In Hand per warehouse, SRBNB, etc.; Supplier `BEBANG KITCHEN INC. - Trade` per-store `accounts[]` entry. **MUST_CONTAIN:** "stock_received_but_not_billed", "enable_perpetual_inventory", "Warehouse.account", "Supplier.accounts" | `grep -c '"stock_received_but_not_billed"' output/l3/s246/audit/CANONICAL_STORE_SPEC.md` returns ≥1 |
| P1A.2 | Categorize each field as REQUIRED / OPTIONAL / DEFAULTED (e.g. `Company.cost_center` = REQUIRED; `Company.default_bank_account` = OPTIONAL) | Spec has 3 sections matching the 3 categories |
| P1A.3 | Add the field-by-field rationale: WHY each field is needed, what breaks if it's missing | Each REQUIRED field has 1-2 sentences of rationale |
| P1A.4 | Extend `scripts/verify_canonical_structure.py` to a v2 mode that asserts the spec across all 49 stores: read all Companies non-BKI non-group, query each REQUIRED field, report missing values per store. **MUST_MODIFY:** `scripts/verify_canonical_structure.py` | `git diff origin/production scripts/verify_canonical_structure.py` shows additions; `grep -c "S246-v2" scripts/verify_canonical_structure.py` returns ≥1 |
| P1A.5 | Run the v2 verifier in `--report` mode (read-only, no auto-fix) and save output to `output/l3/s246/verification/verify_canonical_v2_before.json` + `output/l3/s246/audit/per_store_gap.csv` (one row per store, one column per REQUIRED field, value = present|missing|wrong) | Both files exist; CSV has 49 rows + 1 header; JSON has store-keyed dict |
| P1A.6 | Commit: `feat(S246 P1A): canonical store spec + extended verifier v2 + 49-store gap report` | `git log -1 --oneline` shows it |

**HARD BLOCKER:** if Phase 1A v2 verifier prints PRE-EXISTING violations beyond the ones documented in `output/l3/billing-sweep-2026-05-11/DEFECTS.md`, STOP and present a BLOCKER format to Sam before continuing. New violations may indicate concurrent drift.

---

## Phase 1B — Audit 7 Unanswered Items + 30-Day Error Log Sweep (13 units)

### Goal
Investigate the 7 items the CEO listed that the L3 sweep didn't cover. Produce a single consolidated audit report.

### Tasks

| # | Task | Verification |
|---|------|--------------|
| P1B.1 | **BKI SI GL posting audit:** sample 5 random submitted historical BKI SIs (from the 560 submitted), trace their GL Entries on BKI's books. Confirm Dr `Debtors - BKI` to the right Customer + Cr `4110002 - Sales - Internal` + Cr `Output VAT 12% - BKI`. Write findings to `output/l3/s246/audit/bki_si_gl_audit.md` | File has ≥5 sampled SI examples with GL entries shown |
| P1B.2 | **Tax flow Output VAT → Input VAT:** for the 13 PASS stores with cascaded PIs (or their historical equivalents), trace Output VAT JE on BKI's books → Input VAT JE on store's books. Confirm matching amounts + accounts. Write findings to `output/l3/s246/audit/tax_flow_audit.md` | File has tax-flow trace for ≥5 store-PI pairs |
| P1B.3 | **Cancel + return flow audit:** sample 3 historical cancelled BKI SIs that had cascaded PIs. Confirm the cancel-cascade actually deleted the paired PI AND reversed the JE on the store's side. Write findings to `output/l3/s246/audit/cancel_cascade_audit.md` | File has 3 cases with state before/after |
| P1B.4 | **13 "PASS" stores inventory posting reality:** for each of the 13 stores with `enable_perpetual_inventory=0`, query their inventory tree + recent stock movements. Confirm whether any inventory IS being posted via these PIs (likely NOT). Write findings to `output/l3/s246/audit/13_pass_stores_inventory_audit.md` | File has per-store inventory state |
| P1B.5 | **839 historical test BKI SIs GL audit:** breakdown by docstatus (49 Draft, 560 Submitted, 230 Cancelled). For Submitted+Cancelled, tally GL entry count, total amount, paired PI count. Identify any orphan GL entries or stranded JEs. Write findings to `output/l3/s246/audit/historical_si_gl_audit.md` | File has summary table + counts |
| P1B.6 | **30-day Error Log sweep:** query `tabError Log` for entries created in last 30 days with method LIKE '%S238%' OR error LIKE 'S238%'. Group by unique tail-stacktrace, count occurrences, identify failure classes that weren't surfaced by the 2026-05-11 sweep. Write findings to `output/l3/s246/audit/sentry_30d_sweep.md` | File has unique-error-fingerprint table |
| P1B.7 | **Cross-store transfer model audit:** check whether `resolve_store_buyer_entity` or any existing API supports store→store stock movement (e.g. SM TANZA borrows from SM MEGAMALL). Determine if such transfers happen in production today and how. Write findings to `output/l3/s246/audit/cross_store_transfer_audit.md` | File answers: does store-to-store transfer work? How? Yes/no with evidence |
| P1B.8 | Consolidate P1B.1-P1B.7 into a single `output/l3/s246/audit/audit_report.md` with: per-item findings, defects discovered, architectural implications for the Option 1/2/3 choice. **MUST_CONTAIN:** "BKI SI GL", "Output VAT", "Cancel cascade", "13 PASS stores", "839 historical", "Error Log", "Cross-store transfer" | `grep -c -E "BKI SI GL|Output VAT|Cancel cascade|13 PASS|839 historical|Error Log|Cross-store transfer" output/l3/s246/audit/audit_report.md` returns ≥7 |
| P1B.9 | Commit: `feat(S246 P1B): 7-item audit + 30d Error Log sweep + consolidated report` | `git log -1 --oneline` shows it |

**HARD BLOCKER:** if Phase 1B audit reveals that the canonical model itself is broken (e.g. cross-store transfers happening via undocumented mechanism), STOP and present BLOCKER to Sam.

---

## Phase 2 — CEO Decision Gate (2 units) **HARD GATE**

### Goal
Sam reviews Phase 1A + 1B audit findings IN-SESSION. Confirms or pivots architectural direction. The plan body assumes Option 3 (proper redesign). If Sam picks Option 1 or 2, this plan amends or splits.

### Tasks

| # | Task | Verification |
|---|------|--------------|
| P2.1 | Present audit findings to Sam in chat: top 5 bullet points from `audit_report.md`, the 3 options table from "Design Rationale", and a recommendation. | Sam responds with a chosen option |
| P2.2 | Write `output/l3/s246/DECISION.md` containing: chosen Option (1, 2, or 3), Sam's signoff name + date, rationale, scope of Phase 3+ (which files will change, which master-data UPDATEs), any pivots from the default plan body | File exists; contains exactly one "Chosen Option:" line |

**HARD GATE:** Phase 3 does NOT start until `output/l3/s246/DECISION.md` exists AND contains a chosen Option AND that Option matches the plan body's default (Option 3). If Sam chose Option 1 or 2, the agent STOPS and asks whether to amend this plan or split into S247.

**BLOCKER format if Sam chooses non-Option-3:**
> **BLOCKER:** CEO chose Option N at Phase 2 gate, but plan body assumes Option 3.
> **OPTIONS:**
> 1. Amend S246 plan in-session: rewrite Phases 3-7 for Option N, audit, then execute
> 2. Split into S246 (close as audit+decision only) + S247 (new plan for Option N implementation)
> 3. Stop and re-plan tomorrow
> **RECOMMENDATION:** Option 2 (split) — keeps S246 scope contained and the implementation plan focused.
> Waiting for your decision before proceeding.

---

## Phase 3A — PI Generator Refactor (update_stock=0) (11 units)

### Goal (Option 3 path)
Refactor `hrms/api/bki_store_pi_generator.py` to produce billing-only PIs. Remove inventory mirror logic. Remove warehouse field on PI. Keep currency / cost_center / tax / supplier / credit_to logic. Keep cancel cascade hook.

### Tasks

| # | Task | Verification |
|---|------|--------------|
| P3A.1 | In `build_store_pi`, set `pi.update_stock = 0`. Remove `pi.set_warehouse = buyer_warehouse`. **MUST_MODIFY:** `hrms/api/bki_store_pi_generator.py` | `grep -c "pi.update_stock = 0" hrms/api/bki_store_pi_generator.py` returns ≥1; `grep -c "pi.set_warehouse" hrms/api/bki_store_pi_generator.py` returns 0 |
| P3A.2 | **v1.1 GR/IR fix (Blocker 2):** In `_mirror_items`, remove `warehouse` from the appended dict. Change `expense_account` resolution from `inv_account` (1104210) to `srbnb_account` (the SRBNB account on buyer Company). Add new constant `ACCT_SRBNB = "1402000"` (or whatever the canonical SRBNB account_number is — verify in Phase 1A spec) and `srbnb_account = resolve_account_by_number(buyer_company, ACCT_SRBNB)`. With `update_stock=0`, ERPNext won't override expense_account during validate. | `grep -c "srbnb_account" hrms/api/bki_store_pi_generator.py` returns ≥1 |
| P3A.3 | Add a smoke-test guard: if `update_stock=0` but the buyer Company's `stock_received_but_not_billed` is set, log a Sentry breadcrumb noting that SRBNB is set but unused (so future cleanup can NULL it if desired) | grep for "stock_received_but_not_billed" + "breadcrumb" |
| P3A.4 | Update `maybe_generate_store_pi`'s comment block + docstring to reflect Option 3 design (billing-only, paired with Stock Entry from new generator) | Docstring contains "Option 3", "billing-only", "paired with Stock Entry" |
| P3A.5 | Keep `cascade_cancel_store_pi` intact (no logic change). Add a TODO comment that SE cascade will run alongside PI cascade. | grep for "TODO" + "SE cascade" in cascade_cancel_store_pi |
| P3A.6 | Add Sentry observability context per `.claude/rules/sentry-observability.md`: confirm `set_backend_observability_context(module="billing", action="maybe_generate_store_pi", mutation_type="create")` is present | grep for "set_backend_observability_context" |
| P3A.7 | Write unit-style sanity test (Python script in `tmp/s246/test_pi_refactor.py`) that imports the function and inspects its source for the changes. Run on local. | Script runs and prints OK |
| P3A.8 | Commit: `feat(S246 P3A): PI generator refactor — update_stock=0 (billing only)` | `git log -1 --oneline` shows it |

**MUST_MODIFY:** `hrms/api/bki_store_pi_generator.py`.
**MUST_CONTAIN (in `hrms/api/bki_store_pi_generator.py`):** `pi.update_stock = 0`, `# Option 3-corrected`, `# billing-only`, `# GR/IR via SRBNB`, `srbnb_account = resolve_account_by_number`, `set_backend_observability_context`.

---

## Phase 3B — Stock Entry Generator + Hook Wiring (11 units)

### Goal (Option 3 path)
Create `hrms/api/bki_store_stock_entry_generator.py` — a new file that creates a `Material Receipt` Stock Entry on the buyer store's books, paired to the BKI SI by `bki_si_reference`. Wire it as a second `Sales Invoice.on_submit` hook. Wire cancel-cascade as a second `Sales Invoice.on_cancel` hook. Add `bki_si_reference` Custom Field to Stock Entry.

### Tasks

| # | Task | Verification |
|---|------|--------------|
| P3B.1 | Create `hrms/api/bki_store_stock_entry_generator.py` with: `maybe_generate_store_stock_entry(doc, method)` (SI on_submit), `cascade_cancel_store_stock_entry(doc, method)` (SI on_cancel), `build_store_stock_entry(si, buyer_company)`. Mirror the existing PI generator's filter logic (only fires when `doc.company == BKI` AND `doc.customer == valid_buyer_company`). | File exists at the path |
| P3B.2 | **v1.1 GR/IR fix (Blocker 2):** `build_store_stock_entry` constructs: `frappe.new_doc("Stock Entry")` with `stock_entry_type = "Material Receipt"`, `company = buyer_company`, `posting_date = si.posting_date`, `set_posting_time = 1`, `posting_time = si.posting_time`. Each item: `t_warehouse = buyer_company`, `item_code/qty/uom` from SI line, `basic_rate = si_item.rate`. **CRITICAL:** explicitly set `expense_account = srbnb_account` (NOT default to Company.stock_adjustment_account) so the SE's Cr posts to SRBNB, which the PI's Dr then clears. Set `bki_si_reference = si.name` on the SE doc. **MUST_CONTAIN:** `expense_account = srbnb_account` | `grep -c "expense_account.*srbnb" hrms/api/bki_store_stock_entry_generator.py` returns ≥1 |
| P3B.3 | Use savepoint pattern from `maybe_generate_store_pi` (`frappe.db.savepoint("s246_se_gen")` + try/except + `ROLLBACK TO SAVEPOINT` on failure + `frappe.log_error`). Do NOT block the SI submit. | grep for savepoint pattern |
| P3B.4 | Add `set_backend_observability_context(module="warehouse", action="maybe_generate_store_stock_entry", mutation_type="create")` at function start. | grep for context call |
| P3B.5 | Add Custom Field `bki_si_reference` to Stock Entry doctype via fixture or `frappe.custom_field.create_custom_field` in a one-shot script `scripts/s246/install_se_custom_field.py`. | Script exists; running it creates the field; verifier post-check confirms `frappe.get_meta("Stock Entry").has_field("bki_si_reference") == True` |
| P3B.6 | **v1.1 STRING→LIST + CASCADE ORDER fix (Blocker 1 + Blocker 10):** Update `hrms/hooks.py` `Sales Invoice` doc_events. **HARD BLOCKER:** the existing entries are STRINGS, not lists. A naive append would silently overwrite the PI generator handler → 100% of BKI billing breaks. Required code edit pattern:<br><br>```python<br># BEFORE (origin/production state at hooks.py:227):<br># "Sales Invoice": {<br>#     "on_submit": "hrms.api.bki_store_pi_generator.maybe_generate_store_pi",<br>#     "on_cancel": "hrms.api.bki_store_pi_generator.cascade_cancel_store_pi",<br># }<br><br># AFTER (v1.1 — STRING→LIST conversion + cancel order = SE-then-PI):<br>"Sales Invoice": {<br>    "on_submit": [<br>        "hrms.api.bki_store_pi_generator.maybe_generate_store_pi",<br>        "hrms.api.bki_store_stock_entry_generator.maybe_generate_store_stock_entry",<br>    ],<br>    "on_cancel": [<br>        "hrms.api.bki_store_stock_entry_generator.cascade_cancel_store_stock_entry",  # SE FIRST (reverse-creation order)<br>        "hrms.api.bki_store_pi_generator.cascade_cancel_store_pi",  # PI SECOND<br>    ],<br>}<br>```<br>**Cancel order rationale:** SE was created last → cancelled first (textbook reversal). If PI cancelled first, SRBNB goes Dr-positive momentarily (visible in mid-cancel GL reports). SE-then-PI keeps SRBNB at zero throughout. **MUST_MODIFY:** `hrms/hooks.py` | `grep -B1 -A2 "Sales Invoice" hrms/hooks.py` shows BOTH on_submit and on_cancel as Python lists (`[...]`) AND cascade_cancel_store_stock_entry appears BEFORE cascade_cancel_store_pi |
| P3B.7 | Write `cascade_cancel_store_stock_entry`: find SE by `{bki_si_reference: si.name}`, if Draft delete, if Submitted cancel + log. Same try/except pattern as cascade_cancel_store_pi. **v1.1 backwards-compat (WARNING F-04):** must gracefully skip when no SE found — historical SIs created before S246 deploy have no paired SE; cancelling them should NOT throw. | grep for the cascade function body; grep for `if not frappe.db.exists` defensive check |
| P3B.7b | **v1.1 NEW (Blocker 8) — SE posting-date lock:** Add `lock_posting_date_on_bki_paired_se(doc, method)` to `hrms/api/bki_store_stock_entry_generator.py`. Logic mirrors `lock_posting_date_on_bki_paired_pi`: when `bki_si_reference` is set on the SE, prevent edits to `posting_date`. Register on `Stock Entry.validate` in `hrms/hooks.py`. Prevents PFRS matching violations when finance edits SE posting_date independently. **MUST_MODIFY:** `hrms/api/bki_store_stock_entry_generator.py` (function added), `hrms/hooks.py` (validate hook registered) | `grep -c "lock_posting_date_on_bki_paired_se" hrms/hooks.py` returns ≥1 |
| P3B.7c | **v1.1 NEW (Blocker 7) — Internal Customer defense-in-depth guard:** In `maybe_generate_store_stock_entry` (and mirror in `maybe_generate_store_pi` if missing), add explicit check: if `frappe.db.get_value("Customer", doc.customer, "is_internal_customer")` returns 1, skip generation. The existing `frappe.db.exists("Company", doc.customer)` filter already excludes Internal Customers by naming convention (`SM TANZA (Internal)` doesn't match Company `SM TANZA - BEBANG MEGA INC.`), but explicit defense prevents future naming-convention changes from accidentally triggering generators on S206 labor JEs. **MUST_CONTAIN:** `is_internal_customer` | grep returns ≥1 in each generator file |
| P3B.8 | Update `scripts/billing_sweep/multi_store_smoke.py` per-store assertion block: for each store, after SI submit, expect BOTH a Draft PI (existing assertion) AND a Draft SE (new assertion) where `bki_si_reference == si.name`. SE.items[0].t_warehouse == buyer_company; SE.items[0].basic_rate matches SI rate. **v1.1 GR/IR assertion (Blocker 2):** also verify PI.items[0].expense_account ends in the SRBNB account_number AND SE.items[0].expense_account ends in the SRBNB account_number (proves the GR/IR clearing pattern is wired). **MUST_MODIFY:** `scripts/billing_sweep/multi_store_smoke.py` | `grep -c "Stock Entry" scripts/billing_sweep/multi_store_smoke.py` higher than before; grep for srbnb assertion |
| P3B.9 | Commit: `feat(S246 P3B v1.1): Stock Entry generator + hook STRING→LIST + GR/IR SRBNB routing + SE posting-date lock + Internal Customer guard + sweep dual-doc assertion` | `git log -1 --oneline` shows it |

**MUST_MODIFY:** `hrms/api/bki_store_stock_entry_generator.py` (new), `hrms/hooks.py`, `scripts/billing_sweep/multi_store_smoke.py`.

---

## Phase 3C — BEI Settings Kill Switches + Custom Fields Install (5 units) **NEW in v1.1 — Blocker 7**

### Goal
Add `enable_bki_store_pi_generator` and `enable_bki_store_stock_entry_generator` toggle fields to BEI Settings doctype. v1.0 plan assumed the PI toggle already existed — code-verifier Claim 2 confirmed it does NOT. Without these toggles, there's no kill switch to disable the generators in production if a defect surfaces. Also install the Custom Fields on Stock Entry before any SE generator runs.

### Tasks

| # | Task | Verification |
|---|------|--------------|
| P3C.1 | Edit `hrms/hr/doctype/bei_settings/bei_settings.json` to add two new Check fields: `enable_bki_store_pi_generator` (default=1, label="Enable BKI Store-Side PI Generator") and `enable_bki_store_stock_entry_generator` (default=1, label="Enable BKI Store-Side Stock Entry Generator"). Insert after the existing `bki_*` field cluster. **MUST_MODIFY:** `hrms/hr/doctype/bei_settings/bei_settings.json` | `grep -c "enable_bki_store_pi_generator" hrms/hr/doctype/bei_settings/bei_settings.json` returns ≥1; `grep -c "enable_bki_store_stock_entry_generator"` returns ≥1 |
| P3C.2 | Verify `bki_store_pi_generator.maybe_generate_store_pi` reads `enable_bki_store_pi_generator` (it does, per existing `getattr(settings, "enable_bki_store_pi_generator", 1)` line — but the field didn't exist so it always defaulted to 1). With the field installed in P3C.1, the kill switch becomes operational. | grep confirms |
| P3C.3 | Mirror in `bki_store_stock_entry_generator.maybe_generate_store_stock_entry`: add `if not getattr(settings, "enable_bki_store_stock_entry_generator", 1): return` early-exit check. **MUST_CONTAIN:** `enable_bki_store_stock_entry_generator` | grep returns ≥1 |
| P3C.4 | Install Custom Field `bki_si_reference` on Stock Entry via `scripts/s246/install_se_custom_field.py` — call `frappe.custom_field.create_custom_field` idempotently (skip if exists). Run via SSM after Phase 3 code lands on origin/production. | `frappe.get_meta("Stock Entry").has_field("bki_si_reference") == True` post-install |
| P3C.5 | Commit: `feat(S246 P3C): BEI Settings kill switches + SE Custom Field install` | `git log -1 --oneline` shows it |

**v1.1 deploy-sequence note (addresses Blocker 6 + WARNING F-09):** P3C lands as part of the code PR. The Custom Field install script (P3C.4) is run AFTER PR merge + Frappe migrate, before Phase 4b (master-data UPDATEs). Sequence: P3 code → PR → deploy → migrate → P3C.4 install script → Phase 4a (cost_center only — safe pre-deploy) actually pulls FORWARD to before deploy; Phase 4b (SRBNB + Warehouse.account + Supplier.accounts) runs POST-deploy.

---

## Phase 4 — Master-Data UPDATEs via /frappe-bulk-edits (split into 4a + 4b per v1.1 Blocker 6)

### Goal (Option 3-corrected path) — v1.1 ordering fix per Blocker 6
**v1.0 ran all master-data UPDATEs in one block BEFORE PR merge.** Setting `Warehouse.account = 1104210` while the live PI generator still has `update_stock=1` would surface DEFECT C on 30+ stores immediately — ERPNext would start overriding `expense_account` to the new Warehouse.account on every BKI SI submit between Phase 4 and PR merge.

**v1.1 split into 4a (pre-deploy, safe) + 4b (post-deploy, after generators are refactored):**

- **Phase 4a runs BEFORE PR merge:** safe UPDATEs that don't interact with the live `update_stock=1` PI generator (currently in production). Only fixes DEFECT A (cost_center on 4 stores).
- **Phase 4b runs AFTER PR merge + deploy + migrate + P3C.4 install:** SRBNB + Warehouse.account + Supplier.accounts. These fields are referenced by the new (post-deploy) generators only; safe at this stage.

### Phase 4a — Pre-deploy safe UPDATEs (3 units)

| # | Task | Verification |
|---|------|--------------|
| P4a.1 | Capture pre-touch backup: snapshot current `Company.cost_center` (NULL for 4) per store. Write to `output/l3/s246/state/PRETOUCH_BACKUP_4a.json`. | File exists |
| P4a.2 | Use `/frappe-bulk-edits` UPDATE_SQL to set `Company.cost_center = 'Main - <ABBR>'` for the 4 stores (ROA → 'Main - ROA', SMM → 'Main - SMM', SMMM → 'Main - SMMM', SMS → 'Main - SMS'). FIRST verify each `Main - <ABBR>` Cost Center exists per store. If absent, create via Frappe API in a one-shot script. Wrap account-existence checks with `if not frappe.db.exists("Account", {...})` (Blocker WARNING F-09 idempotency). | Post-UPDATE: 4 rows with non-null cost_center |
| P4a.3 | Update `output/l3/s246/teardown_ledger.json` with the 4 cost_center changes. | File has entries |
| P4a.4 | Commit: `feat(S246 P4a v1.1): pre-deploy cost_center fix for 4 BEI Enterprise stores` | `git log -1 --oneline` shows it |

### Phase 4b — Post-deploy GR/IR master-data UPDATEs (9 units)

**Runs AFTER:** PR merged, deployed, `bench migrate` complete, P3C.4 Custom Field installer run, smoke verifying the new generators work on at least one store.

| # | Task | Verification |
|---|------|--------------|
| P4b.1 | Capture additional pre-touch backup: snapshot current `Company.stock_received_but_not_billed` (NULL for 47) + `Warehouse.account` (NULL for 49) per store. Append to `output/l3/s246/state/PRETOUCH_BACKUP_4b.json`. | File exists |
| P4b.2 | For each of 49 stores: verify a per-store SRBNB Account exists (parent = `Current Liabilities - <ABBR>`, `account_type = 'Stock Received But Not Billed'`, name pattern: `1402000 - Stock Received But Not Billed - <ABBR>` or whatever canonical pattern Phase 1A spec defines). If absent, create via Frappe API with `if not frappe.db.exists("Account", {...})` idempotency. | Per-store SRBNB account exists |
| P4b.3 | Use `/frappe-bulk-edits` UPDATE_SQL to set `Company.stock_received_but_not_billed = '<per-store SRBNB account name>'` for all 49 Companies. | 49/49 Companies have SRBNB non-null post-UPDATE |
| P4b.4 | Use `/frappe-bulk-edits` UPDATE_SQL to set `Warehouse.account = '<per-store 1104210 - Inventory-from-Commissary - <ABBR> account name>'` for all 49 store Warehouses. | 49/49 Warehouses have account non-null |
| P4b.5 | **Phase 2 conditional (WARNING F-10):** Add `perpetual_inventory_consistency: yes\|no` line to Phase 2 DECISION.md checklist. If `yes`, use `/frappe-bulk-edits` to set `Company.enable_perpetual_inventory = 1` on the 13 stores currently `=0` (matching the other 36). If `no`, skip. **CONDITIONAL.** | DECISION.md has the line; UPDATE conditional |
| P4b.6 | Add `Supplier.accounts[buyer_company]` row to `BEBANG KITCHEN INC. - Trade` for each of 49 buyer Companies, pointing to that Company's `2103210 - AP-Trade-BKI - <ABBR>` account. Use Frappe API (`Supplier.accounts` child table). Idempotency: skip if row already exists. | `SELECT COUNT(*) FROM tabParty Account WHERE parent='BEBANG KITCHEN INC. - Trade'` returns 49 |
| P4b.7 | Update `output/l3/s246/teardown_ledger.json` with all 4b changes — doctype, name, field, old_value, new_value. | Entries appended |
| P4b.8 | **v1.1 Rollback runbook (WARNING F-08):** Write `output/l3/s246/audit/phase4_rollback_runbook.md` documenting step-by-step rollback for cost_center / SRBNB / Warehouse.account / Supplier.accounts / created Accounts. Reference `teardown_ledger.json` as authoritative source. | File exists with 4-step procedure |
| P4b.9 | Re-run extended verifier: `python scripts/verify_canonical_structure.py --report` → `output/l3/s246/verification/verify_canonical_v2_after.json`. Diff against P1A.5's `_before.json`. The diff must show the gaps closed. | Diff is non-empty (gaps closed); no NEW gaps added |
| P4b.10 | Commit: `feat(S246 P4b v1.1): post-deploy GR/IR master-data (SRBNB + Warehouse.account + Supplier.accounts + rollback runbook)` | `git log -1 --oneline` shows it |

---

## Phase 5 — L3 Sweep Re-Run + Verification (12 units, was 10 — added single-store smoke + GR/IR JE verification)

### Goal (Option 3-corrected path)
Run the updated `multi_store_smoke.py` from Phase 3B.8 against all 49 stores. Verify each store produces BOTH a Draft PI AND a Draft SE per SI submit. Verify the GR/IR JE chain nets cleanly. Verify cascade-cancel removes BOTH on SI cancel (SE-first). Verify production is clean post-run.

### Tasks

| # | Task | Verification |
|---|------|--------------|
| P5.0 | **v1.1 NEW (WARNING F-07) — Single-store smoke first.** Before the 49-store sweep, run the smoke test on ARANETA only. Verify: SE created with `expense_account=SRBNB`, PI created with `expense_account=SRBNB`, both `bki_si_reference=SI.name`, cascade-cancel removes SE first then PI, SE cleanup leaves no orphan. If single-store smoke fails, STOP — do NOT proceed to the 49-store sweep. Saves blast radius. Output to `output/l3/s246/verification/single_store_smoke.json`. | File shows PASS for ARANETA before P5.1 runs |
| P5.1 | Run `python scripts/billing_sweep/run_sweep.py` (the SSM wrapper from PR #745, now using the updated `multi_store_smoke.py`). Output to `output/l3/s246/verification/l3_sweep_after_redesign.json`. | File exists with 49 results |
| P5.2 | Assert verdict counts: 49 PASS, 0 FAIL, 0 DEFECT_CONFIRMED. | grep + jq returns the expected counts |
| P5.3 | Per-store assertion: every store has both a Draft PI and a Draft SE created. Both share `bki_si_reference == si.name`. SE.items[0].t_warehouse == buyer_company. SE.items[0].basic_rate == 1.0 (test rate). **v1.1 NEW (Blocker 2):** SE.items[0].expense_account contains SRBNB. PI.items[0].expense_account contains SRBNB. PI.credit_to contains "2103210". | Script asserts and exits 0 |
| P5.3b | **v1.1 NEW GR/IR JE chain assertion:** simulate-submit (without actually submitting — read the planned GL entries via ERPNext's `accounts_view`). Verify the planned JE per shipment: `Dr 1104210` once (not twice), `Cr SRBNB` from SE + `Dr SRBNB` from PI net to zero, `Cr 2103210` once. NO orphan Stock Adjustment posting. | jq query on simulated GL shows exactly 2 net non-zero lines per shipment |
| P5.4 | Cancel cascade test: every cancelled SI removes BOTH its PI and its SE (cascade verification). **v1.1 (Blocker 10):** verify SE is cancelled BEFORE PI. Check by reading docstatus modification timestamps. | Per-store result has `cascade_se_worked_first: true` + `cascade_pi_worked_second: true` |
| P5.4b | **v1.1 NEW (Blocker 9 follow-up) — Submitted-state cascade test:** for at least 3 stores, after the Draft PI/SE are created, manually submit them (`pi.submit()`, `se.submit()`) BEFORE cancelling the SI. Then cancel the SI. The cascade must call `.cancel()` (not `.delete()`) on the Submitted PI and Submitted SE. Verify their docstatus = 2 (Cancelled), not 0 (deleted). | 3 stores have docstatus=2 PIs and SEs post-cancel |
| P5.5 | Post-sweep cleanup audit: re-run `scripts/billing_sweep/run_aftermath.py` to confirm leftover_si=0, leftover_pi=0, leftover_se=0, orphan_pi=0, orphan_se=0. | `output/l3/s246/verification/aftermath_after_redesign.json` shows all zeros |
| P5.6 | If any store fails: classify per failure mode (Pattern A=cost_center, Pattern B=SRBNB unrelated, Pattern C=SE creation, Pattern D=hook ordering). If <3 failures: fix and re-run. If ≥3 failures: stop and present BLOCKER. | All failures < 3 OR plan amended |
| P5.7 | Commit: `feat(S246 P5): L3 sweep after redesign — 49/49 PASS with dual-doc cascade` | `git log -1 --oneline` shows it |

---

## Phase 6 — Historical 839 Test SI Cleanup (8 units, was 6 — added pre-cleanup guard + re-count)

### Goal
Force-delete all historical test BKI SIs and their cascaded PIs/SEs (where they still exist). Per CEO directive 2026-05-10: "All of these are test transactions no transaction in Frappe now is real."

### v1.1 Pre-cleanup safety guard (Blocker 9)
**The new SE generator from Phase 3B fires on EVERY SI on_cancel.** When Phase 6 cancels Submitted historical SIs, the cascade-cancel SE hook will fire for SIs that have NO paired SE (created pre-S246). Even with the graceful "skip when no SE found" guard in P3B.7, the hook still fires. To eliminate this risk entirely:

- **Before Phase 6 starts:** Set `BEI Settings.enable_bki_store_stock_entry_generator = 0` AND `BEI Settings.enable_bki_store_pi_generator = 0` via `/frappe-bulk-edits`. This makes both generators no-op during cleanup. The cascade hooks still get called but the early-exit guards (`if not getattr(settings, "enable_...", 1): return`) immediately return.
- **After Phase 6 finishes:** Set both back to 1 to re-enable.

### Tasks

| # | Task | Verification |
|---|------|--------------|
| P6.0 | **v1.1 NEW guard (Blocker 9):** Use `/frappe-bulk-edits` to set `BEI Settings.enable_bki_store_pi_generator = 0` AND `BEI Settings.enable_bki_store_stock_entry_generator = 0`. Confirm via SSM probe. **MUST_VERIFY:** both toggles return 0 before P6.2 runs. | `SELECT enable_bki_store_pi_generator, enable_bki_store_stock_entry_generator FROM tabSingles WHERE doctype='BEI Settings'` returns both = 0 |
| P6.1 | Pre-cleanup snapshot: `SELECT name, docstatus, customer, custom_bei_store_order, grand_total, creation FROM tabSalesInvoice WHERE company = 'BEBANG KITCHEN INC.'` → save to `output/l3/s246/state/historical_si_snapshot.json`. **v1.1 re-count (Blocker 9 follow-up):** the count may have changed since 2026-05-11 (was 839). Use the LIVE count from this probe. Record actual count in `snapshot.json` metadata. | File has ≥1 row (probably ~839, may be higher if other sprints touched BKI SIs) |
| P6.2 | Write `scripts/s246/cleanup_historical_test_bki_si.py`: for each docstatus=1 SI, find its paired PI/SE, cancel both, then cancel the SI, then force-delete all three. For docstatus=2 SI (already cancelled), find any orphan PI/SE, delete those, then force-delete the SI. For docstatus=0 (Draft), just force-delete. | Script exists with these branches |
| P6.3 | Dry-run first: script supports `--dry-run` flag that reports what WOULD be deleted without doing it. Run dry, save to `output/l3/s246/verification/cleanup_dryrun.json`. | File shows ≥839 SIs in scope |
| P6.4 | Live run: `python scripts/s246/cleanup_historical_test_bki_si.py --apply` via SSM. | Script runs to completion; commits per-doc |
| P6.5 | Post-cleanup verification: `SELECT COUNT(*) FROM tabSalesInvoice WHERE company='BEBANG KITCHEN INC.'` returns 0. Same for cascaded PIs and SEs. Save to `output/l3/s246/verification/cleanup_839_si_complete.json`. | All three counts = 0 |
| P6.6 | **v1.1 NEW (Blocker 9) — Restore generators:** Use `/frappe-bulk-edits` to set `BEI Settings.enable_bki_store_pi_generator = 1` AND `BEI Settings.enable_bki_store_stock_entry_generator = 1`. Verify post-set with SSM probe. | Both = 1 |
| P6.7 | Commit: `feat(S246 P6 v1.1): historical BKI SI cleanup — generators disabled during cleanup, restored post` | `git log -1 --oneline` shows it |

**HARD BLOCKER:** if any of the 839 SIs cannot be cleaned (e.g. JEs that won't reverse), STOP and present BLOCKER. Do NOT force a DELETE that leaves orphan GL entries.

---

## Phase 7 — Closeout (5 units)

### Goal
Update plan + registry + PR; remove worktree; declare COMPLETED.

### Tasks

| # | Task | Verification |
|---|------|--------------|
| P7.1 | Write `output/l3/s246/SUMMARY.md` with phase-by-phase outcome, defect resolutions, final verdict counts | File exists |
| P7.2 | Write/refresh `output/l3/s246/DEFECTS.md` listing DEFECT A/B/C/D status (all RESOLVED via Option 3 if successful) | File exists with statuses |
| P7.3 | Update `output/l3/s246/RUN_STATUS.json` to `COMPLETED` | File status field = COMPLETED |
| P7.4 | Update plan YAML: `status: COMPLETED`, `completed_date: 2026-05-11`, `execution_summary: "<one-paragraph outcome>"` | grep YAML for COMPLETED |
| P7.5 | Update `SPRINT_REGISTRY.md` S246 row: STATUS = COMPLETED, PR refs added | grep for "COMPLETED" in S246 row |
| P7.6 | `git add -f docs/plans/2026-05-11-sprint-246-bki-store-billing-redesign.md docs/plans/SPRINT_REGISTRY.md output/l3/s246/ scripts/s246/ scripts/billing_sweep/multi_store_smoke.py hrms/api/bki_store_pi_generator.py hrms/api/bki_store_stock_entry_generator.py hrms/hooks.py scripts/verify_canonical_structure.py` | All paths in `git status` |
| P7.7 | `git push -u origin s246-bki-store-billing-redesign` | Push succeeds |
| P7.8 | `GH_TOKEN="" gh pr create --repo Bebang-Enterprise-Inc/hrms --base production --head s246-bki-store-billing-redesign --title "feat(S246): BKI→Store billing redesign — Stock Entry + Purchase Invoice split" --body "<PR body with task-by-task status>"` | PR URL captured |
| P7.9 | Update `SPRINT_REGISTRY.md` S246 row with the new PR number | grep for PR # |
| P7.10 | Final closeout commit + push: `chore(S246 P7): closeout — plan + registry + summary updated` | `git log -1 --oneline` shows it |
| P7.11 | Worktree exit: `cd F:/Dropbox/Projects/BEI-ERP-s246-bki-store-billing-redesign && git status --short` (must be clean); then `cd F:/Dropbox/Projects/BEI-ERP && git worktree remove F:/Dropbox/Projects/BEI-ERP-s246-bki-store-billing-redesign` | `git worktree list` no longer shows S246 worktree |

**STOP HERE.** Per PR-handoff rule: agent does NOT merge. Sam reviews PR + merges + deploys + L1 smoke.

---

## L3 Workflow Scenarios

| User | Action | Expected Outcome | Failure Means |
|---|---|---|---|
| Administrator (via SSM) | Submit a test BKI SI for ARANETA with `custom_bei_store_order = 'BEI-ORD-2026-00981'`, item `PM003`, qty 1, rate 1.00 | (1) SI gets autoname `BKI-SI-2026-00981-N`. (2) A new Draft PI is created on ARANETA's books with `bki_si_reference = SI.name`, `update_stock=0`, `credit_to = '2103210 - ... - ARGW'`, `pi.items[0].expense_account = '1104210 - ... - ARGW'`. (3) A new Draft Stock Entry is created on ARANETA's books with `stock_entry_type='Material Receipt'`, `bki_si_reference = SI.name`, `items[0].t_warehouse = ARANETA`, `basic_rate = 1.00`. | Phase 3A or 3B is broken; expense_account override defect persists |
| Administrator (via SSM) | Cancel the test SI | (1) PI cascade fires: paired Draft PI deleted. (2) SE cascade fires: paired Draft SE deleted. (3) SI moves to docstatus=2. | Cascade hook missing or wrong order |
| Administrator (via SSM) | Force-delete the cancelled SI | SI fully removed; no orphan PI/SE | Cleanup path broken |
| Test sweep runner | Run `multi_store_smoke.py` against all 49 stores | All 49 produce dual-doc (PI + SE), all 49 cascade clean, all 49 produce 0 leftover artifacts | Phase 3/4/5 incomplete |

**Browser-only is not required for THIS sprint** because the workflow under test is a backend hook chain (SI on_submit → PI generator + SE generator), not a UI workflow. Per `.claude/skills/l3-v2-bei-erp/SKILL.md`, browser-only applies to UI workflow tests. This sprint validates a backend hook chain via SSM-based scripted smoke (the canonical pattern established by PR #745). Sentry observability covers any user-triggered SI submit in production.

**Cleanup ledger** (canonical fixture pattern):
- All 49 test SIs (during Phase 5 sweep) tracked in the script's `CREATED` list
- All test SIs force-deleted in finally block
- Aftermath probe confirms leftover_si=0, leftover_pi=0, leftover_se=0
- 839 historical test SIs cleaned in Phase 6 (separate from sweep cleanup)

## Test Data Seeding Contract

### Records the scenarios depend on
- **Item:** `PM003 (LONG SPOON GREEN W/ POUCH)` — exists in production, `is_stock_item=1`. Verified via probe 2026-05-11.
- **BEI Store Order:** one per store (real existing orders found via `probe_order_per_store.py`). Verified 49/49.
- **Customer per store:** matches Company name — verified 45/49 (4 BEI-parent stores have it; ROA/SMM/SMMM/SMS verified via 2026-05-11 probe).
- **Warehouse per store:** matches Company name — verified 45/49.
- **Account `1104210`, `1106210`, `2103210` per store:** verified 45/49 after S243; 49/49 if Phase 4 succeeds.
- **Supplier `BEBANG KITCHEN INC. - Trade`:** exists globally — verified 2026-05-11.
- **Tax Template `BKI Output VAT 12% Sales - BKI`:** exists — verified 2026-05-11.

### Pre-test seeding
No new records needed BEFORE the sweep — all existing data is sufficient AFTER Phase 4 master-data UPDATEs. The Phase 4 UPDATEs ARE the seeding.

### Teardown
- **In-sweep test data (49 test SIs + 49 test PIs + 49 test SEs):** force-deleted by `_final_cleanup` in `multi_store_smoke.py`. Ledger: in-memory `CREATED` list.
- **Master-data UPDATEs from Phase 4:** documented in `output/l3/s246/teardown_ledger.json`. Rollback path exists if Phase 5 reveals breakage.
- **Historical 839 test SIs:** force-deleted by `scripts/s246/cleanup_historical_test_bki_si.py` in Phase 6. Snapshot pre-cleanup: `output/l3/s246/state/historical_si_snapshot.json`.

### Teardown verification
- `output/l3/s246/verification/aftermath_after_redesign.json` confirms 0 leftover sweep artifacts
- `output/l3/s246/verification/cleanup_839_si_complete.json` confirms 0 leftover historical SIs

### Reference skill
`/frappe-bulk-edits` for all master-data UPDATEs. Manual `bench execute` snippets are acceptable for the historical SI cleanup script in Phase 6 (file is committed to scripts/s246/, not ad-hoc SSM).

## Failure Response (qa-test-library-discipline)

- **Mode A (app bug):** discovered during Phase 5 sweep → file as `output/l3/s246/DEFECTS.md` entry, don't change the test, re-run after the product fix.
- **Mode B (test bug in `multi_store_smoke.py`):** fix the script, re-run the sweep. If the fix is general-purpose (e.g. better SE assertion logic), promote to `scripts/billing_sweep/` reusable assertion helpers.
- **Mode C (brittleness/flakiness):** fix the LIBRARY (`scripts/billing_sweep/`), not the spec. No `time.sleep(N)` hacks. No retry-3 masking. If ≥3 library fixes happen during execution, emit `output/l3/s246/LIBRARY_IMPROVEMENTS.md` as a closeout artifact.

## Sentry Observability

Per `.claude/rules/sentry-observability.md` (DM-7):

| File | Function | module | action | mutation_type |
|---|---|---|---|---|
| `hrms/api/bki_store_pi_generator.py` | `maybe_generate_store_pi` | `billing` | `maybe_generate_store_pi` | `create` |
| `hrms/api/bki_store_pi_generator.py` | `cascade_cancel_store_pi` | `billing` | `cascade_cancel_store_pi` | `delete` |
| `hrms/api/bki_store_stock_entry_generator.py` (NEW) | `maybe_generate_store_stock_entry` | `warehouse` | `maybe_generate_store_stock_entry` | `create` |
| `hrms/api/bki_store_stock_entry_generator.py` (NEW) | `cascade_cancel_store_stock_entry` | `warehouse` | `cascade_cancel_store_stock_entry` | `delete` |

Backend Sentry project: `bei-hrms`. Frontend project not affected (no API route changes).

## Zero-Skip Enforcement

Every task in Phases 0-7 MUST be implemented. If a task cannot be completed, the agent STOPS and asks Sam.

### Forbidden agent behaviors
- ❌ Skipping a task silently
- ❌ Marking partial work as "done"
- ❌ Replacing a task with a simpler version without Sam's approval
- ❌ "Deferred to next sprint" — Phases 0-7 ship together
- ❌ Implementing happy path only, skipping edge cases (e.g. cascade-cancel must handle Submitted PI/SE state)
- ❌ **v1.1 NEW (WARNING F-06):** Combining two tasks into one work unit and silently dropping a feature from the dropped task. Each task ships independently with its own verification.
- ❌ **v1.1 NEW (Blocker 1):** Appending to `Sales Invoice.on_submit` or `on_cancel` without first verifying it's a list. The existing entry is a STRING. Naive append breaks 100% of BKI billing.

### Verification script
The agent writes `output/l3/s246/verify_phase_N.py` BEFORE starting each phase. After completing the phase, runs the script. Script uses `git diff --name-only` and `grep -c` to assert filesystem facts. PASS → next phase. FAIL → fix and re-run.

```python
# Template — adapt per phase
import subprocess

CHECKS = [
    ("Phase 3A: PI generator update_stock=0", "grep", "-c", "pi.update_stock = 0", "hrms/api/bki_store_pi_generator.py", lambda c: c >= 1),
    ("Phase 3B: SE generator file created", "test", "-f", "hrms/api/bki_store_stock_entry_generator.py"),
    ("Phase 3B: hooks.py wired", "grep", "-c", "maybe_generate_store_stock_entry", "hrms/hooks.py", lambda c: c >= 1),
    # ...
]

for check in CHECKS:
    name, *cmd = check
    # ... run + assert
```

### PR description gate
PR description must include a task-by-task status table. Unchecked tasks need explanation. Sam rejects PRs with unexplained gaps.

## Execution Workflow

- **Test Python changes:** `/local-frappe` (Phase 3A/3B sanity testing)
- **Deploy changes:** `/deploy-frappe` (post-PR-merge, by Sam)
- **E2E testing:** Phase 5 sweep via `scripts/billing_sweep/run_sweep.py`
- **Full workflow:** `/agent-kickoff` reads this plan + executes Phases 0-7

> **Deployment is user-mediated.** Builder session creates the PR; Sam handles merge, deploy trigger, and L1 smoke. Builder polls PR state and continues only after merge.

## Phase Completion Checklist (template — agent fills in during execution)

| Phase | Status | Evidence | Skipped? | If skipped, why? |
|---|---|---|---|---|
| 0 | | output/l3/s246/state/ACTIVE_RUN.json | | |
| 1A | | output/l3/s246/audit/CANONICAL_STORE_SPEC.md | | |
| 1B | | output/l3/s246/audit/audit_report.md | | |
| 2 | | output/l3/s246/DECISION.md | | |
| 3A | | git diff hrms/api/bki_store_pi_generator.py | | |
| 3B | | git diff hrms/api/bki_store_stock_entry_generator.py + hrms/hooks.py | | |
| 4 | | output/l3/s246/teardown_ledger.json | | |
| 5 | | output/l3/s246/verification/l3_sweep_after_redesign.json | | |
| 6 | | output/l3/s246/verification/cleanup_839_si_complete.json | | |
| 7 | | docs/plans/SPRINT_REGISTRY.md (S246 = COMPLETED) | | |

## Amendment History
- 2026-05-11 — v1.0 — Initial plan written per CEO directive after PR #745 findings.
- 2026-05-11 — v1.1 — 8-domain audit + code-verifier surfaced 10 CRITICAL + 14 WARNING blockers. All 10 CRITICAL applied inline as v1.1 amendments. Scope unchanged. Phase budget grew from ~85 to ~99 units (Scope Size Warning still applies).

### v1.1 Amendment Map

| Blocker | Source | Where Applied |
|---|---|---|
| **1: hooks.py STRING vs list** | frappe-backend F-01, ph-finance F9, design-review WARNING, code-verifier CONFIRMED Claim 1 | P3B.6 — explicit STRING→LIST conversion code block + cascade order fix |
| **2: JE chain double-counts inventory** | system-arch ARCH-11, ph-finance F1+F2, code-verifier CONFIRMED Claim 4 | Design Rationale Decision 5 (NEW) + P3A.2 (PI uses SRBNB) + P3B.2 (SE uses SRBNB) + P3B.8 (sweep asserts SRBNB on both) + P5.3b (GR/IR JE chain assertion) |
| **3: Atomicity contradiction** | cold-start CRITICAL 2, system-arch ARCH-02, code-verifier CONFIRMED Claim 5 | Design Rationale Decision 3 (rewritten — picks savepoint-isolation + reconciliation cron path) |
| **4: PR #745 still OPEN** | cold-start CRITICAL 1, code-verifier CONFIRMED Claim 3 | YAML `depends_on` (HARD GATE) + P0.0 (PR #745 merged check before worktree spawn) |
| **5: Release-gate path mismatch** | deployment-qa CRITICAL | Global rename `output/s246/` → `output/l3/s246/` (matches release manager regex) |
| **6: Phase 4 ordering** | deployment-qa CRITICAL | Phase 4 split into 4a (pre-deploy cost_center) + 4b (post-deploy SRBNB + Warehouse.account) |
| **7: BEI Settings toggles missing** | design-review CRITICAL, code-verifier CONFIRMED Claim 2 | NEW Phase 3C (install toggle fields + run migrate) |
| **8: Missing SE posting-date lock** | ph-finance F4 | NEW P3B.7b (register `lock_posting_date_on_bki_paired_se` hook) |
| **9: P6 recursive cascade risk** | frappe-backend CRITICAL | Phase 6 toggles BOTH generators off (P6.0) before cleanup, restores on (P6.6) after |
| **10: Cancel cascade order** | system-arch ARCH-05 | P3B.6 hook order: SE first, PI second (reverse-creation pattern) |

### v1.1 WARNING fixes applied

- F-02 (filter-gate duplication) → noted; consider extracting to `bki_store_paired_doc_base` in execution
- F-03 (t_warehouse validation) → P5.0 single-store smoke tests this
- F-04 (in-flight PI backwards-compat) → P3B.7 graceful skip when no SE found
- F-05 (SSM refs missing from plan body) → added to canonical_closeout_artifacts section: `INSTANCE_ID = "i-026b7477d27bd46d6"`, site = `hq.bebang.ph`, container = `frappe_backend`
- F-06 ("combining tasks" missing from forbidden behaviors) → added in Zero-Skip Enforcement section
- F-07 (no single-store smoke) → NEW P5.0
- F-08 (no rollback runbook) → P4b.8 produces `phase4_rollback_runbook.md`
- F-09 (account-creation idempotency) → P4a.2 / P4b.2 wrap with `if not frappe.db.exists`
- F-10 (perpetual_inventory_consistency missing from DECISION.md) → P4b.5
- F-11 (no glob-scan for active sprint collision) → P0.0b
- F-12 (DEFECT-D inventory backfill stance) → noted in scope: existing inventory preserved; new generators only fire on NEW SIs post-deploy
- F-13 (BIR 2550Q legal-entity ambiguity) → noted: Frappe is internal-only; legal-entity Input VAT comes from external BIR-accredited channel (per Frappe-not-accredited research from S238)
- F-14 (PI line count 370 vs 405) → cosmetic; Design Rationale source ref updated implicitly

### Audit evidence

- `output/plan-audit/sprint-246-bki-store-billing-redesign/verified_blockers.md` (Top 10 verdict)
- `output/plan-audit/sprint-246-bki-store-billing-redesign/code_verification.md` (7 of 7 CRITICAL claims CONFIRMED against actual `origin/production` source)
- `output/plan-audit/sprint-246-bki-store-billing-redesign/{frappe_backend,ph_finance,deployment_qa,team_orchestration,system_arch,design_review,cold_start,zero_skip}_findings.md` (8 domain findings)
