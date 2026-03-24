---
canonical_sprint_id: S100
display: Sprint 100
status: COMPLETED
lane: single
created_date: 2026-03-23
execution_started: 2026-03-23
completed_date: 2026-03-24
execution_summary: All 22 tasks (57 units) delivered. Backend PR #321 merged. Hotfix d90aafa95 for savepoint. Frontend C4 merged to bei-tasks main. L3 8/8 PASS.
depends_on:
---

# S100 — SCM Operational Hardening

**Goal:** Harden the procurement-to-payment pipeline with operational safeguards: approval notifications, over-receipt prevention, duplicate invoice detection, payment terms enforcement, invoice line items, configurable 3PL patterns, and GL architecture documentation.

**Origin:** SCM audit findings (2026-03-23) — 8 medium issues + GL architecture gap (H1).

**Independence from S099:** This sprint does NOT depend on S099. Every fix here works against the current codebase. If S099 moves thresholds to BEI Settings, these fixes read from Settings too. If S099 hasn't run yet, these fixes work with existing hardcoded values. No shared files conflict.

**Evidence files:**
- `tmp/audit_scm_consolidated_2026-03-23.md` — severity-ranked findings
- `tmp/audit_scm_e2e_flow.md` — full flow trace with line references

---

## Design Rationale (For Cold-Start Agents)

### Why this exists
The SCM audit found 8 medium-priority operational gaps that don't block testing but will cause problems in production:
1. **Nobody gets notified** of pending PO approvals — all notification functions are `pass` (TODO stubs)
2. **Warehouse can receive more than dispatched** — no over-receipt cap
3. **Same invoice can be entered twice** — no duplicate detection
4. **Payment terms are stored but never enforced** — suppliers could be paid outside agreed terms
5. **Invoice has no child table** — line-item 3-way matching impossible
6. **3PL partner list is hardcoded** — adding Pinnacle Cold required a code change
7. **Approver emails hardcoded** — already moved to BEI Settings by S099 if it ran; this sprint adds the notification system that uses them
8. **GL architecture gap** — BEI tracking docs don't create Frappe GL entries (needs documentation + plan, not a quick fix)

### Why these are independent of S099
- S099 fixes correctness (VAT, EWT, approver identity). This sprint fixes operational robustness.
- If S099 has already run, notifications will read approver emails from BEI Settings. If not, they'll read from `delivery_billing_policy.py` constants. Either path works.
- The invoice child table, over-receipt cap, and duplicate detection are new features that don't touch any S099 files.

### Why this architecture
- **BEI Invoice Item as a Frappe child DocType** (not a JSON blob or separate table) because Frappe's ORM handles parent-child cascading (delete, submit, cancel), and child table fields are queryable in report builder and list views. Line-item 3-way matching requires SQL joins on `item_code`, `qty`, `rate`.
- **Google Chat for notifications** because the team already communicates there. The integration exists at `hrms/api/google_chat.py` with DWD (domain-wide delegation) via `credentials/task-manager-service.json`. Email is optional CC, not primary channel.
- **GL gap as documentation, not code fix** because the dual-DocType architecture (BEI custom tracking → Frappe standard GL) is load-bearing. BEI GR/Invoice/Payment are workflow documents; Frappe Purchase Receipt/Invoice/Payment Entry are GL documents. Merging them requires a design session — the risk of breaking the workflow layer while fixing the GL layer is too high for a sprint task.
- **BEI Settings for 3PL patterns and company names** rather than a separate config DocType because BEI Settings already exists as a Single DocType (`hrms/hr/doctype/bei_settings/`) and is the established pattern (commissary already reads `min_shelf_life_days` from it).

### Key trade-offs
- **Invoice child table as BEI Invoice Item DocType vs. JSON field:** Chose proper child DocType because line-item matching requires queryable fields (item_code, qty, rate, matched_gr_item).
- **Notifications via Google Chat vs. email:** Chose Google Chat because the team already uses it and the integration exists (`hrms/api/google_chat.py`). Email as optional CC.
- **GL gap: fix now vs. document and plan:** Chose document + plan. The dual-DocType architecture is load-bearing — BEI custom workflow on top of Frappe standard GL. Changing this requires a design session, not a sprint task. We document the gap and create a dedicated architecture sprint.

### Known limitations
- **BEI Settings is cached by Frappe** — changes to 3PL patterns or company names take effect on next request, not instantly. Acceptable for config that changes rarely.
- **Google Chat API rate limits** — DWD impersonation is limited to ~60 requests/minute per user. The escalation cron (A4) must batch notifications to avoid hitting limits. If >60 approvals pending, spread across multiple cron runs.
- **Invoice child table migration** — existing BEI Invoices have no child rows. The migration will not retroactively populate line items for historical invoices. Only new invoices created after deployment will have line items.
- **S099 independence** — if S099 has NOT run, approver emails are still hardcoded in `delivery_billing_policy.py`. Notifications in A1-A3 must read from BEI Settings first, fall back to `delivery_billing_policy.py` constants. The Boot Sequence Step 6 checks this.

---

## Scope

### Phase A: Approval Notification System (12 units)

| Task | Type | File | Description | Units |
|------|------|------|-------------|-------|
| A1 | BUILD | `procurement.py` | **M2: Wire PO approval notifications.** Replace `notify_mae()`, `notify_butch()` TODO stubs with real Google Chat notifications. Send to the approver's DM space (resolve via Admin Directory). Include: PO number, supplier, grand_total, items summary, link to my.bebang.ph PO detail page. | 4 |
| A2 | BUILD | `procurement.py` | Wire PR approval notifications. When PR is submitted, notify the designated approver via Google Chat. | 2 |
| A3 | BUILD | `procurement.py` | Wire payment request notifications. When payment request reaches each approval stage (Review → Budget → CFO → CEO), notify the next approver. | 3 |
| A4 | BUILD | `procurement.py` | Add escalation timer. If PO/PR/Payment approval pending > 24 hours, re-notify. Implement as a scheduled task (frappe.cron) that checks pending approvals and sends reminders. | 3 |

### Phase B: Over-Receipt Prevention + Receiving Hardening (8 units)

| Task | Type | File | Description | Units |
|------|------|------|-------------|-------|
| B1 | FIX | `procurement.py:1345-1433` | **M3: Cap received quantity.** In `create_goods_receipt()`, validate each item's `received_qty <= ordered_qty - already_received_qty`. Allow configurable tolerance (default 5% from BEI Settings field `gr_over_receipt_tolerance_pct`). Block if exceeded. **Use `frappe.db.savepoint()` around GR creation (DM-2).** | 3 |
| B2 | FIX | `warehouse.py` | Same over-receipt check for `complete_warehouse_receiving()`. Validate `received_qty <= expected_qty` per item. | 2 |
| B3 | BUILD | `bei_settings.json` | Add `gr_over_receipt_tolerance_pct` (Percent, default 5) to BEI Settings if not already present. | 1 |
| B4 | BUILD | `procurement.py` | Add Purchase Receipt rejection workflow. When GR items are rejected, create a return/credit note record and log the rejection reason. | 2 |

### Phase C: Invoice Hardening (10 units)

| Task | Type | File | Description | Units |
|------|------|------|-------------|-------|
| C1 | BUILD | New DocType | **M8: Create BEI Invoice Item child DocType.** Fields: `item_code` (Link→Item, reqd), `item_name` (Data, fetch_from item_code.item_name), `qty` (Float, reqd), `rate` (Currency, reqd), `amount` (Currency, read_only — computed in validate as qty*rate), `vat_rate` (Percent), `vat_amount` (Currency, read_only — computed), `matched_gr_item` (Link→BEI Goods Receipt Item), `match_status` (Select: Matched/Unmatched/Variance, default Unmatched). **HARD BLOCKER:** `item_code` MUST be Link→Item not Data (DM-4). All computed fields (`amount`, `vat_amount`) must be calculated in `validate()` not stored directly (DM-5). | 5 |
| C2 | EXTEND | `procurement.py:1626-1731` | Update `create_invoice()` to accept and store line items in the new child table. Compute line-level totals. **Use `frappe.db.savepoint()` around invoice + child table insertion (DM-2).** | 3 |
| C3 | BUILD | `procurement.py` | **M6: Duplicate invoice detection.** Before creating invoice, check if `supplier_invoice_no` + `supplier` combination already exists. If so, block with error. Allow override with reason for legitimate duplicates (credit notes). **Override requires Procurement Manager role.** | 2 |
| C4 | BUILD | `bei-tasks` frontend | Update invoice creation form to include line items table matching the child DocType. Includes add/remove rows, auto-compute line totals, loading states. | 3 |

### Phase D: Payment Terms + 3PL Config + Supplier Metrics (12 units)

| Task | Type | File | Description | Units |
|------|------|------|-------------|-------|
| D1 | BUILD | `procurement.py` | **M7: Payment terms enforcement.** When creating payment request, check if payment is within supplier's agreed terms. If payment_terms_days is set on supplier and invoice age < payment_terms_days, allow. If overdue, add warning flag but don't block (configurable). | 3 |
| D2 | EXTEND | `bei_settings.json` | **M4: Move 3PL patterns to BEI Settings.** Add `three_pl_warehouse_patterns` (Small Text, default "3MD,Pinnacle,Royal Cold,RCS"). Parse as comma-separated list. | 1 |
| D3 | FIX | `warehouse.py:413` | Read `_3PL_PATTERNS` from BEI Settings instead of hardcoded tuple. Fall back to hardcoded if settings empty. | 2 |
| D4 | FIX | `warehouse.py:503` | Move `"Bebang Kitchen Inc."` and allowed target companies to BEI Settings. Add `commissary_company` (Link→Company, default "Bebang Kitchen Inc.") and `allowed_target_companies` (Small Text, default "Bebang Kitchen Inc.,Bebang Enterprise Inc."). **`commissary_company` must be Link→Company not Data (DM-4).** | 2 |
| D5 | FIX | `bei_supplier.py:93-120` | **SF5: Compute `avg_delivery_days`** in `update_metrics()`. Calculate average days between PO date and GR received_date from `BEI Goods Receipt` for last 12 months. Currently always 0/null. | 2 |
| D6 | FIX | `bei_supplier.py` + `procurement.py:517` | **SF6: Consolidate `total_outstanding` computation.** `update_metrics()` computes outstanding from invoices minus payments, but `procurement.py:517` independently computes it from a different query. Remove the inline computation and read from the supplier's `total_outstanding` field (single source of truth). | 2 |
| D7 | FIX | `bei_supplier.py` + `procurement.py` | **SF2: Wire `sec_registration` into compliance audit.** Add SEC registration number validation to `procurement.py` compliance audit alongside TIN, BIR 2307, and business permit checks. Return in supplier detail API. Currently stored but never read. | 1 |

### Phase E: GL Architecture Documentation + Sentry (10 units)

| Task | Type | File | Description | Units |
|------|------|------|-------------|-------|
| E1 | BUILD | `docs/architecture/` | **H1: GL Architecture Gap Documentation.** Write a comprehensive document explaining: the dual DocType architecture (BEI custom → Frappe standard), which Frappe GL entries are created and which aren't, the accounting implications, and the recommended path forward. This is NOT a code fix — it's a design document for a future architecture sprint. | 4 |
| E2 | BUILD | `docs/architecture/` | Write the GL reconciliation runbook: how to manually verify that BEI tracking docs match Frappe GL state. Include SQL queries for cross-checking. | 3 |
| E3 | BUILD | All modified files | Add `set_backend_observability_context()` to every new/modified `@frappe.whitelist()` endpoint. Module: "procurement", "warehouse". Actions: function names. | 2 |
| E4 | VERIFY | Production | Run L3 scenarios. | 1 |

**Total: 57 work units across 5 phases.**

> **L3 Session Warning:** This sprint exceeds 40 work units. The executing agent MUST run L3 verification in a separate fresh session to avoid context-exhaustion bias.

---

## L3 Workflow Scenarios

| User | Action | Expected Outcome | Failure Means |
|------|--------|-------------------|---------------|
| test.procurement@bebang.ph | Submit PR for approval | Approver receives Google Chat notification with PR details | A1/A2 notification fix failed |
| test.procurement@bebang.ph | Submit PO for Mae approval | Mae receives Google Chat DM with PO number, supplier, amount | A1 notification failed |
| test.warehouse@bebang.ph | Receive GR: set received_qty = ordered_qty + 20% | Error: "Received quantity exceeds ordered + 5% tolerance" | B1 over-receipt cap failed |
| test.warehouse@bebang.ph | Receive GR: set received_qty = ordered_qty + 3% | GR accepted (within 5% tolerance) | B1 tolerance logic wrong |
| test.procurement@bebang.ph | Create invoice with supplier_invoice_no=INV-001, then try again with same number | Second attempt blocked: "Duplicate invoice number for this supplier" | C3 duplicate detection failed |
| test.procurement@bebang.ph | Create invoice with line items: 3 items matching PO | Invoice created with child table rows, match_status=Matched | C1/C2 child table failed |
| test.procurement@bebang.ph | Create payment for invoice with supplier terms = Net 30, invoice age = 5 days | Payment allowed, no warning | D1 terms logic wrong |
| test.warehouse@bebang.ph | Check 3PL detection after adding new pattern to BEI Settings | New warehouse recognized as 3PL | D2/D3 configurable 3PL failed |

Evidence files required before closeout:
```
output/l3/S100/form_submissions.json
output/l3/S100/api_mutations.json
output/l3/S100/state_verification.json
```

---

## Requirements Regression Checklist

- [ ] Do approval notifications send to Google Chat (not email-only)?
- [ ] Does over-receipt prevention use configurable tolerance from BEI Settings?
- [ ] Does duplicate invoice detection check supplier + invoice number combination?
- [ ] Does the BEI Invoice now have a child table for line items?
- [ ] Are 3PL patterns read from BEI Settings, not hardcoded?
- [ ] Are company names read from BEI Settings, not hardcoded?
- [ ] Does payment terms check use supplier's `payment_terms_days`?
- [ ] Does the GL architecture document cover ALL gaps identified in the audit?
- [ ] Does every new/modified `@frappe.whitelist()` call `set_backend_observability_context()`?
- [ ] Are notification TODO stubs (`pass`) all replaced with real implementations?
- [ ] Is `item_code` on BEI Invoice Item a Link→Item field, not Data? (DM-4)
- [ ] Are `amount` and `vat_amount` on BEI Invoice Item computed in validate(), not stored directly? (DM-5)
- [ ] Does GR creation use `frappe.db.savepoint()`? (DM-2)
- [ ] Does invoice + child table creation use `frappe.db.savepoint()`? (DM-2)
- [ ] Is `commissary_company` in BEI Settings a Link→Company, not Data? (DM-4)
- [ ] Does duplicate invoice override require Procurement Manager role?
- [ ] Does notification error handling use try/except with `frappe.log_error()` (feeds Sentry)?
- [ ] Does the invoice frontend handle loading/error/empty states for the line items table?

---

## Autonomous Execution Contract

- completion_condition:
  - All 5 phases complete
  - All L3 scenarios pass
  - All evidence files present in output/l3/S100/
  - GL architecture document reviewed
  - Plan YAML status updated to COMPLETED
  - SPRINT_REGISTRY.md updated
- stop_only_for:
  - Missing Google Chat credentials/space access
  - BEI Invoice child DocType migration fails
  - GL architecture decisions requiring Sam's input
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
  - **Release Gate BLOCKED** → L3 evidence files missing or insufficient. Run L3, commit evidence: `git add -f output/l3/S100/ && git push`
- release_manager_gate:
  - **Deterministic layer ($0):** Checks L3 evidence files exist in branch, entry count >= 8 (plan scenario count)
  - **AI layer (~$0.10):** Verifies evidence is authentic (not fabricated test data)
  - Both must PASS. If either fails, PR comment lists exact missing items.
  - Builder must commit evidence BEFORE governor will merge.
- l3_evidence_commitment:
  - After running L3 tests, builder MUST commit evidence to the PR branch:
    ```
    git add -f output/l3/S100/form_submissions.json output/l3/S100/api_mutations.json output/l3/S100/state_verification.json
    git commit -m "test(S100): L3 evidence — 8 scenarios"
    git push
    ```
  - Governor will not merge without these files in the branch.
- canonical_closeout_artifacts:
  - `output/l3/S100/form_submissions.json` (committed to branch)
  - `output/l3/S100/api_mutations.json` (committed to branch)
  - `output/l3/S100/state_verification.json` (committed to branch)
  - `docs/plans/2026-03-23-sprint-100-scm-operational-hardening.md` (status → COMPLETED)
  - `docs/plans/SPRINT_REGISTRY.md` (S100 row updated)

Note: `git add -f docs/plans/` and `git add -f output/l3/` required since these paths may be gitignored.

---

## Agent Boot Sequence

1. Read this plan fully.
2. Read `tmp/audit_scm_e2e_flow.md` for exact line references.
3. Read `hrms/hr/doctype/bei_settings/bei_settings.json` for current fields.
4. Read `.claude/rules/sentry-observability.md` for Sentry instrumentation.
5. Read `.claude/rules/frappe-development.md` for DM-1 through DM-6.
6. Check if S099 has run — if BEI Settings has procurement fields, use them. If not, use hardcoded fallbacks.

## Execution Authority

This sprint is intended for autonomous end-to-end execution.
Do not stop for progress-only updates.
Only pause for items listed in the Autonomous Execution Contract `stop_only_for` section.

## Execution Workflow
- Test Python changes: `/local-frappe`
- Deploy changes: `/deploy-frappe`
- Full workflow: `/agent-kickoff`
- E2E testing: `/e2e-test` or `/test-full-cycle`
