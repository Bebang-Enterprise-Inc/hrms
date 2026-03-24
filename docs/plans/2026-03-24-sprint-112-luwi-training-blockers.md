---
canonical_sprint_id: S112
display: Sprint 112
status: DEPLOYED
branch: s112-luwi-training-blockers
lane: single
created_date: 2026-03-24
completed_date:
deployed_at: 2026-03-24
backend_pr: "#344"
frontend_pr: "#237"
l3_result: pending
execution_summary: "Phase A+B implemented, PRs merged (#237 bei-tasks, #344 hrms), deploy triggered. L3 pending in separate session."
depends_on: S108
---

# S112 — Close All Blockers for Luwi's Procurement Training

**Goal:** Make every section of the Procurement Training Guide (Google Doc `1QcawN8c5rTOgeqv0UHDRxq5K1dBtoXNk`) work 100% on my.bebang.ph by tomorrow morning. Luwi Azusano and Cayla Cabagnot cannot hit a dead page, a broken form, or a permissions wall during training.

**Origin:** S108 L3 testing (2026-03-24) tested all 6 procurement forms from the training guide. 5/6 PASS, 1 BLOCKED (Payment Request). Plus 4 collateral bugs found across all pages. Full evidence in `output/l3/S108/TRAINING_FORM_TESTS.md` and `output/l3/S108/COLLATERAL_BUGS.md`.

**Deadline:** Must be deployed TONIGHT (2026-03-24). Luwi trains tomorrow morning.

---

## Design Rationale (For Cold-Start Agents)

### Why this exists
S108 fixed PR creation but L3 testing of ALL training guide forms revealed 6 blockers that prevent Luwi from completing 100% of her training:

1. **OR Follow-up page 404** — Page exists at `bei-tasks/app/dashboard/procurement/or-follow-up/page.tsx` but is missing from the sidebar navigation in `layout.tsx`. Users can't find it.
2. **Payment Request BLOCKED** — No verified invoices exist. The API enforces `invoice.status in ["Verified", "Partially Paid"]` at `procurement.py:2146-2149`. Need to seed a verified invoice.
3. **Empty error toast on every page** — A shared API call fails silently, showing an empty error notification on all 9 procurement pages.
4. **Payments page 500** — Secondary API call returns 500. Page still shows data but some stats are missing.
5. **Supplier Code UX mismatch** — UI placeholder says "leave blank to auto-generate" but backend doesn't auto-generate. Field is optional in Zod schema but confusing.
6. **Warehouse RBAC for GR** — `WAREHOUSE_USER` role is excluded from `MODULES.PROCUREMENT` in `bei-tasks/lib/roles.ts:553-560`. Warehouse staff can't access Goods Receipts.

### Why these specific fixes
Every fix maps directly to a training guide section that would block Luwi:
- Section 7 (Goods Receipts) → RBAC fix
- Section 9 (Payments) → Seed data + 500 fix
- Section 10 (Suppliers) → Supplier code UX
- Section 11 (OR Follow-up) → Sidebar navigation
- All sections → Empty error toast

### Key trade-offs
- **Sidebar nav vs new page:** OR Follow-up page already exists and works — just need to add it to sidebar. No new code needed.
- **Seed data vs mock:** We need a REAL verified invoice in the pipeline, not a mock. This means running the PR→PO→GR→Invoice→Verify chain via API.
- **RBAC scope:** Adding WAREHOUSE_USER to PROCUREMENT module is the right fix. Warehouse staff DO need procurement access for GR workflows.

### Known limitations
- Python Playwright is broken on this machine. Use Node.js Playwright for L3.
- Governor may not be running. Use `gh pr merge --admin` or API merge as fallback.

---

## Scope

### Phase A: Frontend Fixes — bei-tasks only (6 units)

| Task | Type | File | Description | Units |
|------|------|------|-------------|-------|
| A1 | FIX | `bei-tasks/app/dashboard/procurement/layout.tsx` | Add OR Follow-up to sidebar `navItems` array (after "Payments", before "Reports"). Use the constant `PROCUREMENT_OR_FOLLOWUP` from `lib/constants.ts` (line 234). Icon: `Receipt` from lucide-react. Label: "OR Follow-up". **HARD BLOCKER:** The route path is `/dashboard/procurement/or-follow-up` (with hyphens), NOT `/or-followup`. Verify against the actual folder name. | 1 |
| A2 | FIX | `bei-tasks/lib/roles.ts` | Add `ROLES.WAREHOUSE_USER` to `MODULES.PROCUREMENT` array at line 553-560. This lets warehouse staff access GR pages. **HARD BLOCKER:** Do NOT remove any existing roles from the array. Only ADD `ROLES.WAREHOUSE_USER`. | 1 |
| A3 | FIX | `bei-tasks/app/dashboard/procurement/suppliers/new/page.tsx` | Fix supplier_code field UX: either (a) add auto-generation in the frontend (`SUPP-${Date.now()}` as default), or (b) change placeholder from "leave blank to auto-generate" to "Required: enter a unique supplier code". Option (a) is preferred. | 1 |
| A4 | FIX | `bei-tasks/hooks/use-procurement.ts` or procurement layout | Debug the empty error toast. Check what shared query or useEffect fires on every procurement page load and returns an error with no message. Fix by either: (a) suppressing empty-message toasts, or (b) fixing the API call that fails. Likely candidates: `useDashboardKPIs()`, `useOutstandingBySupplier()`, `usePendingPaymentApprovals()`. | 2 |
| A5 | VERIFY | Terminal | Run `npx tsc --noEmit` — zero TS errors on modified files before committing. **HARD BLOCKER.** | 1 |

### Phase B: Backend Fix + Data Seed (5 units)

| Task | Type | File | Description | Units |
|------|------|------|-------------|-------|
| B1 | FIX | `hrms/api/procurement.py` | Debug the 500 error on Payments page. Find which endpoint is called on load (likely `get_payment_request_stats` or similar). Fix the error. Add Sentry instrumentation to the fixed endpoint (DM-7). | 2 |
| B2 | BUILD | Script / API calls | Seed a verified invoice through the full procurement chain so Payment Request form can be tested. Steps: (1) Find an existing approved PO with a matching GR, (2) Create an invoice against it via API, (3) Verify the invoice via `verify_invoice_match` API. If no suitable PO+GR pair exists, create the full chain: PR → PO → approve → GR → Invoice → verify. Write seed results to `output/l3/S112/seed_data.json`. | 2 |
| B3 | VERIFY | `hrms/api/procurement.py` | Verify `create_supplier` auto-generates supplier_code if not provided. If it doesn't, add auto-generation: `data["supplier_code"] = f"SUPP-{frappe.utils.now_datetime().strftime('%Y%m%d%H%M%S')}"`. Add Sentry to `create_supplier` if missing (DM-7). | 1 |

### Phase C: Deploy + L3 Verify All Training Sections (8 units)

| Task | Type | Description | Units |
|------|------|-------------|-------|
| C1 | BUILD | Commit + push bei-tasks branch. Create PR. Merge (governor or manual). | 1 |
| C2 | BUILD | Commit + push hrms branch. Create PR. Merge. Trigger deploy workflow. Wait for completion. | 2 |
| C3 | VERIFY | L3: Login as test.warehouse@bebang.ph → navigate to /dashboard/procurement/goods-receipts → page loads (not "Access Restricted"). | 1 |
| C4 | VERIFY | L3: Navigate using sidebar → "OR Follow-up" link exists → click → page loads with OR tracking data. | 1 |
| C5 | VERIFY | L3: Navigate to /dashboard/procurement/payments/new → select verified invoice from dropdown → fill payment mode=Bank Transfer, amount → click Create Payment Request → POST returns 200. | 1 |
| C6 | VERIFY | L3: Visit all 9 procurement pages → no empty error toast flashes. | 1 |
| C7 | BUILD | Closeout: update plan YAML status to COMPLETED, update SPRINT_REGISTRY.md, `git add -f docs/plans/ output/l3/S112/` and push to production. | 1 |

**Total: 19 units.**

---

## L3 Workflow Scenarios

| User | Action | Expected Outcome | Failure Means |
|------|--------|-------------------|---------------|
| test.warehouse@bebang.ph | Login → navigate to Procurement > Goods Receipts | GR list page loads, not "Access Restricted" | A2 RBAC fix not working |
| luwi@bebang.ph | Login → look at sidebar under Procurement | "OR Follow-up" link visible between Payments and Reports | A1 nav fix not working |
| luwi@bebang.ph | Click "OR Follow-up" in sidebar | OR tracking page loads with table of awaiting ORs | A1 route wrong |
| test.hr@bebang.ph | Navigate to Payments > New Payment Request → invoice dropdown | At least 1 verified invoice appears in dropdown | B2 seed data not created |
| test.hr@bebang.ph | Select verified invoice → fill amount, mode=Bank Transfer → click Create | Payment request created (POST 200) | B2 invoice not verified, or API bug |
| test.hr@bebang.ph | Navigate to Suppliers > Add Supplier → leave supplier_code blank → fill name → Create | Supplier created with auto-generated code | A3/B3 auto-gen not working |
| test.hr@bebang.ph | Visit all 9 procurement pages sequentially | No empty error toast flash on any page | A4 toast fix not working |
| test.hr@bebang.ph | Visit Payments page | No 500 console error | B1 fix not working |

Evidence files required before closeout:
```
output/l3/S112/form_submissions.json
output/l3/S112/api_mutations.json
output/l3/S112/state_verification.json
output/l3/S112/seed_data.json
```

---

## Requirements Regression Checklist

- [ ] Is OR Follow-up in the sidebar nav between Payments and Reports?
- [ ] Does the OR Follow-up route use `/or-follow-up` (hyphens, matching folder name)?
- [ ] Is WAREHOUSE_USER added to MODULES.PROCUREMENT in roles.ts?
- [ ] Are all existing roles in MODULES.PROCUREMENT preserved (not removed)?
- [ ] Does supplier_code auto-generate when left blank?
- [ ] Is the empty error toast fixed on all 9 procurement pages?
- [ ] Is the Payments 500 error fixed?
- [ ] Does a verified invoice exist for Payment Request testing?
- [ ] Does `npx tsc --noEmit` pass with zero errors on modified files?
- [ ] Does every new/modified @frappe.whitelist() endpoint call set_backend_observability_context()?
- [ ] Does PR creation still work (S107+S108 regression check)?
- [ ] Does department dropdown still show API-fetched departments (S107 regression)?

---

## Autonomous Execution Contract

- **completion_condition:**
  - All 8 L3 scenarios PASS on live production
  - OR Follow-up visible in sidebar and functional
  - Warehouse user can access GR page
  - Payment Request can be created with a verified invoice
  - No empty error toasts on procurement pages
  - Evidence files exist with matching entry counts
  - Plan YAML status = COMPLETED, pushed to production
  - SPRINT_REGISTRY.md updated, pushed to production

- **stop_only_for:**
  - Missing credentials/access
  - Governor down AND manual merge unauthorized
  - Cannot find any PO with matching GR for invoice seeding (business-data)

- **continue_without_pause_through:**
  - code → test → PR → deploy → L3 → closeout

- **blocker_policy:**
  - programmatic → fix and continue
  - TS type error → fix before pushing (S107/S108 lesson)
  - empty toast root cause unclear → add generic `if (!error.message) return;` guard and continue
  - business-data → pause

- **signoff_authority:** single-owner (Sam Karazi, CEO)

---

## Remote-Truth Baseline

| Repo | Branch | HEAD SHA |
|------|--------|---------|
| hrms | production | `6599773c7` |
| bei-tasks | main | `a8fd280` |

---

## Agent Boot Sequence

1. Read this plan fully — including all L3 scenarios and the Requirements Regression Checklist.
2. **Create sprint branches:**
   - hrms: `git fetch origin production && git checkout -b s112-luwi-training-blockers origin/production`
   - bei-tasks: `cd ../bei-tasks && git fetch origin main && git checkout -b s112-luwi-training-blockers origin/main`
3. Read `output/l3/S108/TRAINING_FORM_TESTS.md` — the evidence of what's broken.
4. Read `output/l3/S108/COLLATERAL_BUGS.md` — the collateral bug report.
5. Read `bei-tasks/app/dashboard/procurement/layout.tsx` — the sidebar nav to fix.
6. Read `bei-tasks/lib/roles.ts` lines 550-570 — the RBAC config to fix.
7. Read `bei-tasks/hooks/use-procurement.ts` — hooks that may cause empty toasts.

## Execution Authority

This sprint is intended for autonomous end-to-end execution.
Do not stop for progress-only updates.
Only pause for items listed in the Autonomous Execution Contract `stop_only_for` section.

## Execution Workflow
- Test Python changes: `/local-frappe`
- Deploy backend: create hrms PR → governor or manual merge → trigger deploy workflow (ID: 226200303)
- Deploy frontend: push bei-tasks branch → merge to main → Vercel auto-deploys
- E2E testing: Node.js Playwright (`node script.cjs`). Python Playwright is broken on this machine.
