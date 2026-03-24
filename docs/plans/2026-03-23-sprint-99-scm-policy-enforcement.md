---
canonical_sprint_id: S099
display: Sprint 99
status: COMPLETED
execution_started: 2026-03-23
lane: single
created_date: 2026-03-23
completed_date: 2026-03-24
execution_summary: "PR #321 merged 2026-03-24. L3 12/12 PASS. VAT math penny-exact. Approver identity enforced. Combined with S100 in same PR."
depends_on:
---

# S099 — SCM Policy Enforcement & Tax Compliance

**Goal:** Make every procurement calculation correct — VAT from supplier master, EWT from supplier master, approver identity enforced, account codes configurable, hardcoded thresholds moved to BEI Settings. Plus fix the 3 chat-reported bugs blocking the testing team.

**Origin:** ERP/HR Automation Committee chat review (2026-03-23) + 3-agent SCM audit finding 4 critical + 6 high issues.

**Evidence files:**
- `tmp/audit_scm_consolidated_2026-03-23.md` — severity-ranked findings
- `tmp/audit_supplier_fields.md` — dead DocType fields
- `tmp/audit_scm_e2e_flow.md` — full flow trace with line references
- `tmp/erp_committee_review_2026-03-23.md` — team-reported bugs + screenshots

---

## Design Rationale (For Cold-Start Agents)

### Why this exists
The ERP demo is being tested by the SCM team but calculations are wrong:
- **All suppliers get 12% VAT** regardless of their `vat_status` (VAT Registered / Non-VAT / Exempt). The `BEI Supplier` DocType has the field but `procurement.py:734` hardcodes 12%.
- **EWT rate never auto-populates** from supplier's `default_ewt_rate`. Manual entry only.
- **Anyone can approve POs** — `approve_mae()` at `bei_purchase_order.py:201` doesn't check `frappe.session.user`.
- **EWT JV failure is swallowed** — payment marked paid even when the Journal Entry fails (`procurement.py:2174`).
- **EWT ATC codes mismatch** — JV says WC100 (services), Form 2307 says WI100 (goods).
- **8 GL account codes hardcoded inline** instead of reading from company defaults.
- **PR form has hardcoded department list and UOM list** on the bei-tasks frontend.

### Why this architecture
- **BEI Settings DocType already exists** (`hrms/hr/doctype/bei_settings/`) with 4 fields. We extend it with procurement thresholds and account codes rather than creating a new DocType.
- **Supplier `vat_status` already exists** on `BEI Supplier` DocType. We wire it into existing code paths, not redesign.
- **This sprint is backend-heavy.** Only 2 frontend tasks (B1 dept list, B2 UOM list). The rest is Python.

### Key trade-offs
- **Extend BEI Settings vs. new Procurement Settings DocType:** Chose BEI Settings because it already exists, is a Single DocType (one record), and the commissary already reads `min_shelf_life_days` from it. Adding 15 more fields is simpler than a new DocType.
- **Fetch dept/UOM from API vs. just fix the hardcoded list:** Chose API fetch because hardcoded lists have already caused two bugs. The API endpoints already exist in procurement.py (department list, UOM list via Frappe).
- **Fix EWT ATC inline vs. add ATC to supplier master:** Chose adding an `atc_code` field to `BEI Supplier` because the correct ATC depends on supplier type (goods vs services vs rental). A single hardcoded default is always wrong for some suppliers.

### Known limitations
- **BEI Settings is cached by Frappe** — changes take effect on next request, not instantly. This is acceptable.
- **Input VAT 3-way split (1105104/1105105)** is in this sprint but requires knowing which suppliers provide services vs capital goods. We add the field but the population is a data task.
- **GL gap (H1 from audit)** is NOT in this sprint — it's architectural and goes to S100.

---

## Scope

### Phase A: BEI Settings Extension + Supplier Fields (12 units)

| Task | Type | File | Description | Units |
|------|------|------|-------------|-------|
| A1 | EXTEND | `bei_settings.json` | Add 10 threshold fields: `dual_approval_threshold` (Currency, default 500000), `tin_requirement_threshold` (Currency, default 250000), `price_variance_block_pct` (Percent, default 10), `price_variance_lookback_days` (Int, default 90), `new_supplier_window_days` (Int, default 30), `default_vat_rate` (Percent, default 12), `default_ewt_rate` (Percent, default 1), `fg_low_stock_threshold` (Int, default 7), `non_fg_low_stock_fallback` (Int, default 10), `shelf_life_dispatch_buffer_days` (Int, default 1) | 3 |
| A2 | EXTEND | `bei_settings.json` | Add 6 account code fields: `gr_ir_clearing_account` (Link→Account), `input_vat_goods_account` (Link→Account), `input_vat_services_account` (Link→Account), `input_vat_capital_goods_account` (Link→Account), `advances_to_suppliers_account` (Link→Account), `ewt_payable_account` (Link→Account), `ap_trade_account` (Link→Account), `default_cost_center` (Link→Cost Center) | 3 |
| A3 | EXTEND | `bei_supplier.json` | Add `atc_code` field (Select: WI100/WC100/WI010/WI020/WC010/WC020, default WI100). WC010/WC020 are for corporations — most BEI suppliers are corporations. Add `input_vat_category` field (Select: Goods/Services/Capital Goods, default Goods). | 2 |
| A4 | BUILD | `bei_settings.py` | Add `get_procurement_settings()` cached helper that reads all threshold + account fields from BEI Settings. Returns dict. Cache with `frappe.cache().get_value("bei_procurement_settings", ...)`. | 2 |
| A5 | BUILD | Migration script | Populate BEI Settings with current hardcoded defaults so existing behavior is unchanged. Populate `atc_code=WI100` and `input_vat_category=Goods` for all existing suppliers. | 2 |

### Phase B: Critical Fixes — Approver Identity + EWT Safety (10 units)

| Task | Type | File | Description | Units |
|------|------|------|-------------|-------|
| B1 | FIX | `bei_purchase_order.py:201` | **C1: Approver identity check.** Add `if frappe.session.user != settings.cpo_approver_email: frappe.throw(_("Only {0} can approve as CPO").format(settings.cpo_approver_email))` at top of `approve_mae()`. Same for `approve_butch()` with `cfo_approver_email`. **HARD BLOCKER:** Without this, any user can approve any PO. | 2 |
| B2 | FIX | `delivery_billing_policy.py:7-8` + `procurement.py:4567,4572` + `bei_match_exception.py:10-13` | Move `CPO_APPROVER_EMAIL` and `CFO_APPROVER_EMAIL` to BEI Settings fields (`cpo_approver_email`, `cfo_approver_email`, Link→User not Data). Read via `get_procurement_settings()`. **Must also fix 3 additional hardcoded locations** found by code verification: `procurement.py:4567`, `procurement.py:4572`, and `bei_match_exception.py:10-13`. | 3 |
| B3 | FIX | `procurement.py:2174-2177` | **C3: EWT JV failure handling.** Code verification found `frappe.throw()` already exists at line 2177, but the error message is misleading and the payment status update may still proceed in some code paths. **Audit finding:** Verify the full exception flow — ensure payment request status is NOT updated to "Paid" if JV creation fails. Add `frappe.db.savepoint()` around the payment status update + JV creation as an atomic unit (DM-2 compliance). If JV fails, roll back payment status too. | 3 |
| B4 | FIX | `procurement.py:2145` + `procurement.py:5142-5144` | **C2: EWT ATC alignment.** Read `atc_code` from `BEI Supplier` record. Use it in both EWT JV remarks and Form 2307 generation. Read `default_ewt_rate` from supplier. Fall back to BEI Settings `default_ewt_rate` only if supplier has none. **HARD BLOCKER:** EWT JV must include `party_type: "Supplier"`, `party: supplier_name`, `cost_center` from settings, and `reference_type`/`reference_name` pointing to the payment request (DM-1, DM-6 compliance). | 4 |

### Phase C: VAT & Tax Policy Enforcement (12 units)

| Task | Type | File | Description | Units |
|------|------|------|-------------|-------|
| C1 | FIX | `procurement.py:734` | **C4: Read supplier `vat_status`.** In `_normalize_purchase_order_payload()`, after resolving supplier identity, read `vat_status` from `BEI Supplier`. If `Non-VAT` or `Exempt`, set `vat_rate = 0` for all items. If `VAT Registered`, use BEI Settings `default_vat_rate` (12%). Only use item-level `vat_rate` if frontend explicitly sends one. | 4 |
| C2 | FIX | `bei_purchase_order.py:150` | Same VAT fix in the DocType's `calculate_totals()` method. Read supplier `vat_status` via `self.supplier` link. | 2 |
| C3 | FIX | `procurement.py:4699` | **H2: Input VAT 3-way split.** Read `input_vat_category` from supplier. Use correct account: `input_vat_goods_account` for Goods, `input_vat_services_account` for Services, `input_vat_capital_goods_account` for Capital Goods. Read accounts from `get_procurement_settings()`. | 3 |
| C4 | FIX | `bei_supplier.py` + `bei_payment_request.py:655` | **H4+H5: Wire `default_ewt_rate` and `ewt_exempt`.** When creating payment request, auto-populate `ewt_rate` from supplier's `default_ewt_rate`. If `ewt_exempt=1`, skip EWT entirely regardless of `ewt_applicable`. Add validation: `ewt_exempt` and `ewt_applicable` cannot both be 1. | 3 |

### Phase D: Replace All Hardcoded Values (10 units)

| Task | Type | File | Description | Units |
|------|------|------|-------------|-------|
| D1 | FIX | `procurement.py` (7 locations) | Replace all hardcoded account codes with `get_procurement_settings()` reads. Locations: line 2130 (AP), 2162 (EWT Payable), 4689 (GR/IR), 4699 (Input VAT), 4709 (Advances), 4694/4704/4714 (Cost Center). | 3 |
| D2 | FIX | `procurement.py` + `bei_purchase_order.py` | Replace all hardcoded thresholds: 500000 (4 locations), 250000 (2 locations). Read from `get_procurement_settings()`. Keep `DUAL_APPROVAL_THRESHOLD` constant as fallback if settings not configured. | 3 |
| D3 | FIX | `commissary_dashboard.py:183-184,423` | Replace FG low stock (7), non-FG fallback (10), shelf life buffer (1) with BEI Settings reads. | 2 |
| D4 | FIX | `bei_purchase_order.py:121,129` | Replace price variance 10% and 90-day lookback with BEI Settings reads. | 2 |

### Phase E: Frontend Fixes + Auto-Pricing + CEO Approval (14 units)

| Task | Type | File | Description | Units |
|------|------|------|-------------|-------|
| E1 | FIX | `bei-tasks/.../purchase-requisitions/new/page.tsx:94-105` | **B1: Fetch department list from API** instead of hardcoded list. Create `get_department_list()` endpoint in `procurement.py` if not exists, or use Frappe's `/api/method/frappe.client.get_list?doctype=Department`. | 3 |
| E2 | FIX | `bei-tasks/.../purchase-requisitions/new/page.tsx:108-123` | **B2: Fetch UOM list from API** instead of hardcoded 14 values. Create `get_uom_list()` endpoint or use Frappe's UOM list. Ensure case matches DB (SACK not Sack). | 2 |
| E3 | BUILD | `procurement.py` | **Auto-price lookup API.** Create `get_item_last_price(item_code, supplier)` endpoint that returns the last negotiated `unit_cost` from `BEI PO Item` (same query as `check_price_variance_blocks` at `bei_purchase_order.py:116-123`). If no history for this supplier+item, return null. Also return `avg_90d_price` for reference. | 2 |
| E4 | FIX | `bei-tasks/.../purchase-requisitions/new/page.tsx` | **PR auto-price.** When user selects an item, call `get_item_last_price()` and auto-populate the cost field. Rename field from "Est. Price" / "Est. Unit Cost" to **"Unit Cost"**. If API returns a price, show it as the default with a small label "(last PO: P80.24)". If no history, leave blank for manual entry. Nothing should say "estimated" — these are real negotiated prices. | 3 |
| E5 | FIX | `bei_purchase_requisition.json` | Rename DocType field: `estimated_unit_cost` → keep fieldname (avoid migration) but change **label** from "Est. Unit Cost" to "Unit Cost". Change `estimated_amount` label to "Amount". | 1 |
| E6 | BUILD | `bei_purchase_order.py` | **H6: CEO approval for new vendors.** In `on_submit()` or PO creation, check `is_new_supplier`. If true, add CEO approval step. Add `ceo_approver_email` to BEI Settings. Wire into approval flow: new vendor POs require 3-level approval (Mae → Butch → CEO) regardless of amount. | 3 |

### Phase F: Test Data + Sentry + Verification (8 units)

| Task | Type | File | Description | Units |
|------|------|------|-------------|-------|
| F1 | BUILD | Script | Load test data: raw materials stock (22 items), finished goods at commissary + 3PL warehouses, sample suppliers with varied `vat_status` (VAT Registered, Non-VAT, Exempt) and `atc_code` values. | 3 |
| F2 | FIX | Frappe config | Enable PR permission for warehouse test role (Ian's account). Verify S092 session timeout fix is deployed. | 1 |
| F3 | BUILD | All modified files | Add `set_backend_observability_context()` to every new/modified `@frappe.whitelist()` endpoint. Module: "procurement", "commissary", "warehouse". Actions: function names. | 2 |
| F4 | VERIFY | Production | Run L3 scenarios against production after deploy. **Run L3 in a FRESH agent session** — this plan is 67 units, above the 40-unit context exhaustion threshold. L3 shortcuts are the #1 cause of corrupt success. | 2 |

**Total: 67 work units across 6 phases.**

> **L3 Session Warning:** This sprint exceeds 40 work units. The executing agent MUST run L3 verification in a separate fresh session to avoid context-exhaustion bias that causes agents to shortcut L3 testing.

---

## L3 Workflow Scenarios

| User | Action | Expected Outcome | Failure Means |
|------|--------|-------------------|---------------|
| test.procurement@bebang.ph | Create PR: department=Commissary, item=Sago, qty=45, UOM=SACK | PR created successfully, dept from API dropdown, SACK in UOM list | B1/B2 fix failed |
| test.procurement@bebang.ph | Create PR: select item=Sago for supplier with prior PO history | Unit Cost auto-populates with last PO price (e.g., 80.24). Label says "Unit Cost" not "Est. Price". Small reference shows "(last PO: P80.24)" | E3/E4 auto-price failed |
| test.procurement@bebang.ph | Create PR: select item with NO prior PO history | Unit Cost field is blank, user enters manually. No "estimated" label anywhere. | E4 fallback logic wrong |
| test.procurement@bebang.ph | Create PO for Non-VAT supplier: item=Sago, qty=45, rate=80.24 | PO shows VAT=0%, grand_total=3,610.80 (no VAT added) | C1 VAT fix failed |
| test.procurement@bebang.ph | Create PO for VAT Registered supplier: same item | PO shows VAT=12%, grand_total=4,044.10 | C1 VAT fix regression |
| test.warehouse@bebang.ph | Try to approve PO as Mae (wrong user) | Error: "Only mae@bebang.ph can approve as CPO" | B1 approver identity fix failed |
| test.procurement@bebang.ph | Create payment request for supplier with `ewt_exempt=1` | No EWT deducted, full amount payable | C4 ewt_exempt fix failed |
| test.procurement@bebang.ph | Create payment request for supplier with `default_ewt_rate=2` | EWT auto-populated at 2%, not 1% default | C4 auto-populate fix failed |
| test.procurement@bebang.ph | Create PO for new supplier (< 30 days old) | CEO approval step added to workflow | E3 new vendor gate failed |
| test.procurement@bebang.ph | Trigger payment where EWT JV would fail (simulate) | Payment NOT marked as paid, error shown | B3 EWT safety fix failed |

Evidence files required before closeout:
```
output/l3/S099/form_submissions.json
output/l3/S099/api_mutations.json
output/l3/S099/state_verification.json
```

---

## Requirements Regression Checklist

- [ ] Does `_normalize_purchase_order_payload()` read supplier `vat_status` before defaulting VAT rate?
- [ ] Does `approve_mae()` verify `frappe.session.user == cpo_approver_email`?
- [ ] Does `approve_butch()` verify `frappe.session.user == cfo_approver_email`?
- [ ] Does EWT JV failure prevent payment from being marked as paid?
- [ ] Does EWT JV use the supplier's `atc_code`, not hardcoded WC100?
- [ ] Does Form 2307 use the supplier's `atc_code`, not hardcoded WI100?
- [ ] Does payment request auto-populate `ewt_rate` from supplier's `default_ewt_rate`?
- [ ] Does `ewt_exempt=1` override `ewt_applicable=1` and skip EWT?
- [ ] Are all 8 account codes read from BEI Settings, not hardcoded?
- [ ] Are all 10 thresholds read from BEI Settings, not hardcoded?
- [ ] Does the PR form fetch departments from API, not hardcoded list?
- [ ] Does the PR form fetch UOMs from API, not hardcoded list?
- [ ] Does the PR form auto-populate unit cost from last PO price for the supplier+item?
- [ ] Does the PR form label say "Unit Cost" (not "Est. Price" or "Est. Unit Cost")?
- [ ] Does the PO auto-load prices from supplier history when items are added?
- [ ] Does new vendor PO require CEO approval?
- [ ] Does Input VAT use correct account based on supplier's `input_vat_category`?
- [ ] Does the VAT logic distinguish between VAT-exempt (no VAT, no Input VAT claim) and zero-rated (0% VAT, Input VAT claimable)?
- [ ] Does every EWT JV row include party_type, party, cost_center, and reference_type/reference_name? (DM-1, DM-6)
- [ ] Does the payment + JV flow use frappe.db.savepoint() for atomicity? (DM-2)
- [ ] Are approver email fields Link→User (not Data) in BEI Settings?
- [ ] Are hardcoded approver emails replaced in ALL locations (delivery_billing_policy.py, procurement.py:4567,4572, bei_match_exception.py:10-13)?
- [ ] Does get_item_last_price() have proper @frappe.whitelist() and permission checks?
- [ ] Does the frontend PR form handle loading/error/empty states for API-fetched dropdowns?
- [ ] Does every new/modified `@frappe.whitelist()` call `set_backend_observability_context()`?

---

## Autonomous Execution Contract

- completion_condition:
  - All 6 phases complete
  - All L3 scenarios pass
  - Plan YAML status updated to COMPLETED
  - SPRINT_REGISTRY.md updated
  - All evidence files present in output/l3/S099/
- stop_only_for:
  - Missing credentials/access
  - BEI Settings migration fails (data integrity)
  - Destructive approval requiring Sam's consent
  - Business-policy decision on ATC code defaults
- continue_without_pause_through:
  - code → test → PR creation → L3 evidence commit → governor review → release gate → deploy → L2-L4 retest → closeout
- blocker_policy:
  - programmatic → fix and continue
  - environment/runtime → debug, research after 3 failures, continue
  - business-data/policy → pause
- signoff_authority: single-owner (Sam)
- governor_decisions:
  - **APPROVE + Merge** → Proceed to L2-L4 post-deploy verification
  - **REJECT** → Read PR comment reasoning, fix code, push to same branch
  - **NEEDS_FIX** → Read suggested fix in PR comment, apply, push
  - **Merge Conflict** → `git fetch origin production && git rebase origin/production`, resolve, force-push
  - **Deploy Failure** → Check deploy logs via `gh run list`, fix if code issue, push fix
  - **Low Confidence** → Review confidence < 0.80. Governor pauses auto-merge. Manual review recommended.
  - **Release Gate BLOCKED** → L3 evidence files missing or insufficient. Run L3, commit evidence: `git add -f output/l3/S099/ && git push`
- release_manager_gate:
  - **Deterministic layer ($0):** Checks L3 evidence files exist in branch, entry count >= 10 (plan scenario count)
  - **AI layer (~$0.10):** Verifies evidence is authentic (not fabricated test data)
  - Both must PASS. If either fails, PR comment lists exact missing items.
  - Builder must commit evidence BEFORE governor will merge.
- l3_evidence_commitment:
  - After running L3 tests, builder MUST commit evidence to the PR branch:
    ```
    git add -f output/l3/S099/form_submissions.json output/l3/S099/api_mutations.json output/l3/S099/state_verification.json
    git commit -m "test(S099): L3 evidence — 10 scenarios"
    git push
    ```
  - Governor will not merge without these files in the branch.
- canonical_closeout_artifacts:
  - `output/l3/S099/form_submissions.json` (committed to branch)
  - `output/l3/S099/api_mutations.json` (committed to branch)
  - `output/l3/S099/state_verification.json` (committed to branch)
  - `docs/plans/2026-03-23-sprint-99-scm-policy-enforcement.md` (status → COMPLETED)
  - `docs/plans/SPRINT_REGISTRY.md` (S099 row updated)

Note: `git add -f docs/plans/` and `git add -f output/l3/` required since these paths may be gitignored.

---

## Agent Boot Sequence

1. Read this plan fully.
2. Read `tmp/audit_scm_e2e_flow.md` for exact line references.
3. Read `tmp/audit_supplier_fields.md` for field status.
4. Read `hrms/hr/doctype/bei_settings/bei_settings.json` for current fields.
5. Read `.claude/rules/sentry-observability.md` for Sentry instrumentation pattern.
6. Read `.claude/rules/frappe-development.md` for DM-1 through DM-6.

## Execution Authority

This sprint is intended for autonomous end-to-end execution.
Do not stop for progress-only updates.
Only pause for items listed in the Autonomous Execution Contract `stop_only_for` section.

## Execution Workflow
- Test Python changes: `/local-frappe`
- Deploy changes: `/deploy-frappe`
- Full workflow: `/agent-kickoff`
- E2E testing: `/e2e-test` or `/test-full-cycle`
