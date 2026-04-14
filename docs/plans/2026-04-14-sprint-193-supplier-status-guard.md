# S193 — Supplier Status Guard

**v2 — 2026-04-14: Amended after audit. 6 blockers resolved (3 CRITICAL + 3 WARNING). Zero features removed. Scope unchanged: same helper, same 3 call sites, same 4 tests, same policy (B/PV block all, Inactive blocks PO only). Fixes are placement/robustness details caught by code verification against production.**

- canonical_sprint_id: `S193`
- status: PR_CREATED
- completed_date: 2026-04-14
- execution_summary: PR hrms#569. Helper + 3 call sites + Sentry for create_purchase_order + 5 unit tests (all pass). Phase 0a controller check confirmed DocType allows direct status set. Awaiting deploy (skip_build=false) and L3 run in fresh session.
- created: 2026-04-14
- owner: Sam
- branch: `s193-supplier-status-guard` (hrms)
- depends_on: None (standalone hardening of existing procurement flow)
- estimated_units: ~10 (single-file backend + tests + Sentry + closeout)
- registry_lock: `| S193 | Sprint 193 | s193-supplier-status-guard (hrms) | — | PLANNED 2026-04-14 |`

## Mission

Make the BEI Supplier master status (`Blacklisted`, `Pending Verification`) actually enforce procurement policy. Today these statuses are informational only — the UI shows them but the backend will still accept POs, Invoices, and Payment Requests for suppliers in those states. Add a single shared guard called from the three creation endpoints.

## Why Now

During the S186 supplier hub audit (2026-04-14), Sam asked whether supplier master status propagates through the PO → Invoice → Payment Request chain. Investigation confirmed:

- The **Link field** (supplier → BEI Supplier) prevents free-text garbage in every DocType ✅
- The **TIN threshold gate** (line 1491 of `procurement.py`) works for >₱250K annual spend ✅
- **Status is NOT enforced** — `grep -n "status.*Blacklisted\|Blacklisted.*supplier"` in `hrms/api/procurement.py` returns zero meaningful hits. A supplier marked `Blacklisted` or `Pending Verification` in the master can still receive new POs, Invoices, and RFPs.

This is a silent control gap. The fix is small (one guard function, three call sites) and high-leverage (closes the loop between master data hygiene and transaction authorization).

## Design Rationale (For Cold-Start Agents)

**Why this exists:**
- BEI Supplier DocType has a `status` Select field with four values: `Active`, `Inactive`, `Blacklisted`, `Pending Verification` (see `hrms/hr/doctype/bei_supplier/bei_supplier.json`).
- `Active` → normal operation.
- `Inactive` → historical supplier, no new business. **This sprint does NOT block Inactive.** An existing PO for an Inactive supplier may still have invoices and payments processed (tail of prior relationship). Only the create-new step is considered for Inactive (see below).
- `Blacklisted` → policy violation (fraud, failed audit, regulatory issue). **Must block all new PO/Invoice/Payment Request creation.**
- `Pending Verification` → onboarding incomplete (e.g. missing TIN, SEC cert, bank details). **Must block all new PO/Invoice/Payment Request creation.** Once Ops completes the verification, the status flips to `Active` and flow resumes.

**Why a single shared guard function, not scattered checks:**
- DRY: three call sites (create_purchase_order, create_invoice, create_payment_request), one rule.
- Auditable: one function name (`_assert_supplier_active`) that shows up in every call trace.
- Future-proof: when we add a new status (e.g. `On Hold`), one place to update.
- Testable: one function to unit test, three integration tests to verify it's called.

**Key trade-off decisions:**
1. **Block Inactive on create_purchase_order, NOT on create_invoice/create_payment_request.** The PO is the "new business" step — if a supplier is Inactive we don't want a new PO. But invoices/payments settle against POs that already exist, and those POs were approved when the supplier was Active. Blocking invoice/payment for an Inactive supplier would strand legitimate in-flight transactions. (Confirmed with Sam 2026-04-14.)
2. **`Blacklisted` and `Pending Verification` block ALL three create endpoints.** No in-flight exception — if a supplier was wrongly approved and is now Blacklisted, we do NOT want to pay their open invoices until they're cleared. Ops can re-activate via the supplier edit approval workflow (already exists — see `submit_supplier_edit_for_approval`).
3. **Error message uses `frappe.ValidationError` with a clear reason + next step.** Not a silent log — the frontend will surface it. Message template: `"Cannot create {doctype}: Supplier {name} is {status}. {next_step}"`.
4. **No frontend change in this sprint.** The supplier hub grid and overview already display status badges (S186). When the backend guard fires, the frontend shows the Frappe error toast. Good enough; a dedicated inline "this supplier is blacklisted" disabled-button UX is S194+ work.

**Known limitations:**
- The guard runs at the `@frappe.whitelist()` API boundary, not as a DocType `validate` hook. This means a direct `frappe.get_doc("BEI Purchase Order", {...}).insert()` from Python/console bypasses the guard. Trade-off: simpler, no DocType override, and all legitimate creation paths go through the API. Internal scripts that bulk-insert are out of scope and owned by the operator.
- `Inactive` is NOT blocked at invoice/payment — if Finance believes an Inactive supplier has a legitimate open invoice, they can still process it. The supplier master status is advisory for existing flow; blocking-grade only for new POs.

**Source references:**
- Status enum: `hrms/hr/doctype/bei_supplier/bei_supplier.json` — field `status`, options `Active\nInactive\nBlacklisted\nPending Verification`
- Existing Supplier resolver: `hrms/api/procurement.py:111` (`_resolve_supplier_identity`)
- TIN gate precedent (same pattern we're copying): `hrms/api/procurement.py:1491` inside `create_purchase_order`
- create_purchase_order: `hrms/api/procurement.py:1455`
- create_invoice: `hrms/api/procurement.py:2392`
- create_payment_request: `hrms/api/procurement.py:2709`

## Scope Summary

### In-Scope
- New helper `_assert_supplier_active(supplier: str, operation: str) -> None` in `hrms/api/procurement.py`
- Call the helper at the top of `create_purchase_order`, `create_invoice`, `create_payment_request`
- Unit test covering the four statuses × three endpoints
- Sentry DM-7 observability — the helper raises with a tagged breadcrumb

### Out-of-Scope
- Frontend UI changes (status badges already exist in supplier hub grid + overview)
- DocType `validate()` hook (trade-off documented above)
- Blocking `Inactive` on invoice/payment endpoints (policy decision — see Design Rationale #1)
- Supplier status workflow changes (Pending Verification → Active transitions remain in existing supplier-edit approval flow)
- Backfill / audit of historical POs/invoices/payments for Blacklisted suppliers

## Non-Negotiable Rules

1. **One helper, three call sites.** No duplicated status checks.
2. **Blacklisted and Pending Verification block all three create endpoints.** Inactive blocks only PO creation.
3. **Error message names the supplier, the status, and the next step.** No generic "permission denied."
4. **Must raise before any DB write.** Guard is the first check after supplier ID resolution, before any supplier_doc fetch that would incur overhead.
5. **No silent fallback.** If the supplier doesn't exist, that's still a hard error (existing behavior).

## Existing Assets (Duplication Audit)

| Asset | Location | Classification | Notes |
|-------|----------|----------------|-------|
| BEI Supplier DocType | `hrms/hr/doctype/bei_supplier/bei_supplier.json` | REFERENCE | `status` field is authoritative |
| `_resolve_supplier_identity()` | `hrms/api/procurement.py:111` | REFERENCE | DO NOT modify — already used by 7 endpoints |
| `create_purchase_order()` | `hrms/api/procurement.py:1455` | EXTEND | Add guard call after data parse, before TIN check |
| `create_invoice()` | `hrms/api/procurement.py:2392` | EXTEND | Add guard call after supplier resolution |
| `create_payment_request()` | `hrms/api/procurement.py:2709` | EXTEND | Add guard call after supplier resolution |
| TIN threshold gate | `hrms/api/procurement.py:1491` | PATTERN | Mirror this style — `frappe.throw(_("..."))` |
| Sentry helper | `hrms.utils.sentry.set_backend_observability_context` | REUSE | Add breadcrumb in the guard when it fires |

## Architecture Context

```
┌───────────────────────────────────────────────────────────────┐
│  hrms/api/procurement.py                                      │
│                                                               │
│  NEW:                                                         │
│  _assert_supplier_active(supplier, operation)                 │
│    └─ reads tabBEI Supplier.status                            │
│    └─ raises ValidationError if Blacklisted|Pending           │
│    └─ for create_purchase_order: also blocks Inactive         │
│                                                               │
│  CALL SITES:                                                  │
│  create_purchase_order()      — blocks B|PV|I                 │
│  create_invoice()             — blocks B|PV                   │
│  create_payment_request()     — blocks B|PV                   │
└───────────────────────────────────────────────────────────────┘

Legend: B = Blacklisted, PV = Pending Verification, I = Inactive
```

## Agent Boot Sequence

1. Read this plan fully.
2. **Create sprint branch:** `cd F:/Dropbox/Projects/BEI-ERP && git fetch origin production && git checkout -b s193-supplier-status-guard origin/production`. NEVER write code on production.
3. Read `hrms/api/procurement.py` lines 111-135 (existing `_resolve_supplier_identity`) to confirm the helper pattern.
4. Read `hrms/api/procurement.py` lines 1455-1500, 2392-2420, 2709-2750 (the three create endpoints — confirm insertion points).
5. Read `hrms/hr/doctype/bei_supplier/bei_supplier.json` — verify `status` Select options are exactly `Active`, `Inactive`, `Blacklisted`, `Pending Verification`.
6. Confirm the TIN threshold pattern at line 1491 — use the same `frappe.throw(_(...))` style.
7. Execute **Phase 0a** (controller read + frontend error surface check) — 1 unit — **before any code change**.
8. Write the guard, call sites, Sentry instrumentation for create_purchase_order, and tests in a single commit per phase.

## Execution Authority

This sprint is intended for autonomous end-to-end execution.
Do not stop for progress-only updates.
Only pause for items listed in the Autonomous Execution Contract `stop_only_for` section.

---

## Delivery Phases

### Phase 0a — Verify controller + frontend error surface (~1 unit) — AUDIT AMENDMENT

**Purpose:** De-risk assumptions before writing code.

**Task 0a.1 — Supplier status transition check (Blocker 4):**
Read `hrms/hr/doctype/bei_supplier/bei_supplier.py` (controller) and confirm:
- Can `status` be set directly to all four values (`Active`, `Inactive`, `Blacklisted`, `Pending Verification`) on `insert()`?
- If a `validate` or `before_save` hook restricts certain values (e.g., new suppliers must start as `Pending Verification`, or `Blacklisted` requires an approval workflow), the Phase 2 test fixture MUST bypass via `frappe.db.set_value(..., update_modified=False)` after creation in the `Active` state.
- Record findings in `output/s193/controller_check.md` with the exact code snippet that determines policy.

**Task 0a.2 — Frontend error surface spot-check (Blocker 6):**
Read `bei-tasks/lib/frappe-api.ts` → confirm `parseFrappeError` extracts the `message` field from a Frappe `ValidationError` response (HTTP 417). Grep for usage: `grep -rn "parseFrappeError" bei-tasks/app/dashboard/procurement/ | head`.

Spot-check ONE create page (e.g., `bei-tasks/app/dashboard/procurement/purchase-orders/new/page.tsx`). Confirm it renders the extracted message in a toast or inline error (not a generic "Failed to create"). If it does NOT surface the message cleanly, add a single-line TODO comment to the plan's S194 follow-up notes — do NOT block S193 merge on this.

**Verification:**
- [ ] `output/s193/controller_check.md` exists with snippet and conclusion
- [ ] `parseFrappeError` confirmed to extract Frappe error message
- [ ] One create-page error path confirmed (or TODO logged)

### Phase 0 — Implement `_assert_supplier_active` helper (~3 units)

**MUST_MODIFY:** `hrms/api/procurement.py`
**MUST_CONTAIN after:** `def _assert_supplier_active` AND `Pending Verification` AND `Blacklisted`

Add the helper immediately after `_resolve_supplier_identity` (around line 135) so it's a sibling of the existing supplier utilities.

**Signature and behavior:**
```python
# Statuses that block ALL create flows (new business)
_SUPPLIER_BLOCK_ALL_STATUSES = frozenset({"Blacklisted", "Pending Verification"})
# Statuses that additionally block new PO creation (no new business with inactive)
_SUPPLIER_BLOCK_NEW_PO_STATUSES = frozenset({"Inactive"})

def _assert_supplier_active(supplier: str, operation: str) -> None:
    """Block creation against suppliers in forbidden statuses.

    operation: one of "purchase_order", "invoice", "payment_request".
    Raises frappe.ValidationError with supplier name, status, and next step.

    Policy:
      - Blacklisted / Pending Verification: block all three operations.
      - Inactive: block purchase_order only (invoices/payments on pre-existing
        POs remain allowed so in-flight work is not stranded).
    """
    status = frappe.db.get_value("BEI Supplier", supplier, "status")
    if not status:
        # Supplier does not exist — Link field would normally catch this, but
        # if we got here via a stale ID let the caller handle non-existence.
        return

    blocked = status in _SUPPLIER_BLOCK_ALL_STATUSES
    if operation == "purchase_order" and status in _SUPPLIER_BLOCK_NEW_PO_STATUSES:
        blocked = True

    if not blocked:
        return

    # Supplier display name for the error
    name_display = frappe.db.get_value("BEI Supplier", supplier, "supplier_name") or supplier

    if status == "Blacklisted":
        next_step = "Contact Procurement Manager to review the blacklist decision."
    elif status == "Pending Verification":
        next_step = "Complete supplier verification (TIN, SEC, bank details) before transacting."
    else:  # Inactive
        next_step = "Re-activate the supplier in the Supplier Hub if business continues."

    op_label = {
        "purchase_order": "Purchase Order",
        "invoice": "Invoice",
        "payment_request": "Payment Request",
    }.get(operation, operation)

    # Sentry breadcrumb so policy denials are observable
    try:
        from hrms.utils.sentry import set_backend_observability_context
        set_backend_observability_context(
            module="procurement",
            action="assert_supplier_active_denied",
            extras={"supplier": supplier, "status": status, "operation": operation},
        )
    except Exception:
        pass  # Observability must never break the guard

    frappe.throw(
        _("Cannot create {0}: Supplier {1} is {2}. {3}").format(
            op_label, name_display, status, next_step
        ),
        frappe.ValidationError,
    )
```

**Verification:**
- [ ] `grep -c "def _assert_supplier_active" hrms/api/procurement.py` returns `1`
- [ ] `grep -c "_SUPPLIER_BLOCK_ALL_STATUSES" hrms/api/procurement.py` returns at least `2` (definition + use)
- [ ] Helper is placed between `_resolve_supplier_identity` and the next major section (`SUPPLIER ENDPOINTS`)

### Phase 1 — Wire guard into three create endpoints (~3 units)

**MUST_MODIFY:** `hrms/api/procurement.py`
**MUST_CONTAIN after (procurement.py):** `_assert_supplier_active(supplier_name, "purchase_order")` AND `_assert_supplier_active(` (at least 3 call sites total)

**Task 1.1 — `create_purchase_order` (line 1455):**

**AMENDMENT (Blocker 3):** `create_purchase_order` is missing `set_backend_observability_context` entirely — this is a pre-existing DM-7 gap. Since we are already editing this function, add Sentry instrumentation in the same commit.

**HARD BLOCKER:** Do NOT remove or weaken the TIN threshold check at line 1491. Only ADD lines.

Step 1 — Add Sentry at the very top of the function (before the `if not data` check):
```python
from hrms.utils.sentry import set_backend_observability_context
set_backend_observability_context(module="procurement", action="create_purchase_order", mutation_type="create")
```

Step 2 — Insert the status guard immediately after the `supplier_name` extraction at line 1467 and before `_normalize_purchase_order_payload` at line 1468 (so we block before any normalization work runs):
```python
# Guard: block new PO for Blacklisted/Pending Verification/Inactive suppliers (S193)
if supplier_name:
    _assert_supplier_active(supplier_name, "purchase_order")
```

**Task 1.2 — `create_invoice` (line 2392):**

**AMENDMENT (Blocker 1):** Invoices are commonly created from a Purchase Order or Goods Receipt. When that happens, `data.get("supplier")` is `None` at the top — supplier is populated later by `_populate_invoice_context` (lines 2412, 2443). A top-of-function check silently skips the guard for the normal 3-way-match flow.

**Fix:** Resolve supplier with PO/GR fallback before calling the guard. Place this block at **line 2405** (after `_normalize_invoice_payload(data)`, before the `_populate_invoice_context` calls) so denial fires before any DB writes:

```python
# Guard: block new invoice for Blacklisted/Pending Verification suppliers (S193)
# supplier may be set directly, populated from GR/PO context, or derivable from linked docs.
# We resolve via fallback so the guard fires for PO-linked and GR-linked flows, not just
# direct-supplier invoices.
_s193_supplier = data.get("supplier")
if not _s193_supplier and data.get("purchase_order"):
    _s193_supplier = frappe.db.get_value("BEI Purchase Order", data["purchase_order"], "supplier")
if not _s193_supplier and data.get("goods_receipt"):
    _s193_supplier = frappe.db.get_value("BEI Goods Receipt", data["goods_receipt"], "supplier")
if _s193_supplier:
    _assert_supplier_active(_s193_supplier, "invoice")
```

**Task 1.3 — `create_payment_request` (line 2709):**

**AMENDMENT (Blocker 2):** Payment Requests are typically created against an Invoice (via `data["invoice"]`). Supplier is NOT a required input — it's derived from the invoice by `_populate_payment_request_invoice_context`. A top-of-function `data.get("supplier")` check would be `None` and silently skip.

**Fix:** Resolve supplier with Invoice/PO fallback. Place this block **after `data = frappe.parse_json(data)` at line 2722** and **before the Double-Payment guard at line 2724** so S193 denial takes precedence:

```python
# Guard: block new payment request for Blacklisted/Pending Verification suppliers (S193)
# supplier may be set directly, or derivable from the linked invoice / PO.
_s193_supplier = data.get("supplier")
if not _s193_supplier and data.get("invoice"):
    _s193_supplier = frappe.db.get_value("BEI Invoice", data["invoice"], "supplier")
if not _s193_supplier and data.get("purchase_order"):
    _s193_supplier = frappe.db.get_value("BEI Purchase Order", data["purchase_order"], "supplier")
if _s193_supplier:
    _assert_supplier_active(_s193_supplier, "payment_request")
```

**Verification:**
- [ ] `grep -n '_assert_supplier_active(' hrms/api/procurement.py` shows at least 4 hits (1 def + 3 call sites)
- [ ] `grep -n '_assert_supplier_active.*"purchase_order"' hrms/api/procurement.py` shows exactly 1 hit
- [ ] `grep -n '_assert_supplier_active.*"invoice"' hrms/api/procurement.py` shows exactly 1 hit
- [ ] `grep -n '_assert_supplier_active.*"payment_request"' hrms/api/procurement.py` shows exactly 1 hit
- [ ] `grep -n 'set_backend_observability_context.*create_purchase_order' hrms/api/procurement.py` shows exactly 1 hit (NEW — Blocker 3 fix)
- [ ] `grep -c "_s193_supplier" hrms/api/procurement.py` returns at least 6 (3 assignments + 3 uses across invoice + payment_request fallback chains)
- [ ] TIN threshold check at line 1491 (search `tin_requirement_threshold`) still present — DO NOT remove

### Phase 2 — Tests (~3 units)

**MUST_MODIFY:** `hrms/api/tests/test_procurement_supplier_guard.py` (new file)
**MUST_CONTAIN:** `def test_assert_supplier_active_blacklisted` AND `def test_assert_supplier_active_pending_verification` AND `def test_assert_supplier_active_inactive_po_only` AND `def test_assert_supplier_active_active_allowed`

Create a new test file. Structure:

1. **Fixture:** four test suppliers, one per status. Create them in `setUp`, delete in `tearDown`.
2. **Test 1 — `test_assert_supplier_active_blacklisted`:** call `_assert_supplier_active(blacklisted_sup, op)` for each of the three operations; each must raise `frappe.ValidationError` with "Blacklisted" in the message.
3. **Test 2 — `test_assert_supplier_active_pending_verification`:** same, with Pending Verification supplier.
4. **Test 3 — `test_assert_supplier_active_inactive_po_only`:** Inactive supplier — `purchase_order` raises, `invoice` and `payment_request` return None.
5. **Test 4 — `test_assert_supplier_active_active_allowed`:** Active supplier — all three operations return None.

Use `frappe.tests.utils.FrappeTestCase` and existing test patterns in `hrms/api/tests/`. If a tests folder doesn't exist, create it.

**Verification:**
- [ ] `grep -c "def test_assert_supplier_active" hrms/api/tests/test_procurement_supplier_guard.py` returns `4`
- [ ] Tests can be collected by pytest (syntactically valid) — even if Frappe runtime isn't available locally, the file must import cleanly

### Phase 3 — PR Creation + Closeout (~1 unit)

**MUST_MODIFY:** `docs/plans/2026-04-14-sprint-193-supplier-status-guard.md` (status update)
**MUST_MODIFY:** `docs/plans/SPRINT_REGISTRY.md` (add PR#, update status)

**Task 3.1 — Pre-PR rebase check:**
```bash
cd F:/Dropbox/Projects/BEI-ERP
git fetch origin production
GH_TOKEN="" gh api "repos/Bebang-Enterprise-Inc/hrms/compare/s193-supplier-status-guard...production" --jq '.behind_by'
# If >0 behind: git rebase origin/production, verify no conflict markers, push
```

**Task 3.2 — Create PR:**
```bash
GH_TOKEN="" gh pr create --repo Bebang-Enterprise-Inc/hrms \
  --base production --head s193-supplier-status-guard \
  --title "feat(S193): supplier status guard — block PO/Invoice/RFP for Blacklisted + Pending Verification suppliers" \
  --body "..."
```

**Task 3.3 — Closeout:**
- Update plan YAML: status `PLANNED` → `PR_CREATED`, add `completed_date: 2026-04-14`, `execution_summary: ...`
- Update `SPRINT_REGISTRY.md` S193 row with PR number and `PR_CREATED` status
- `git add -f docs/plans/...` and commit
- STOP. Sam handles merge + deploy.

**Verification:**
- [ ] PR URL printed
- [ ] Plan YAML status is `PR_CREATED`
- [ ] SPRINT_REGISTRY row shows the PR number

---

## Requirements Regression Checklist

Before marking any task complete, verify each of the following is yes/true:

- [ ] Is the helper named `_assert_supplier_active` (underscore-prefixed, NOT `assert_supplier_active`)? (Helpers in `procurement.py` are consistently underscore-prefixed.)
- [ ] Does the helper accept `(supplier, operation)` as args, NOT `(supplier_doc, operation)`? (We fetch status via `frappe.db.get_value` to avoid loading the full doc.)
- [ ] Does the helper use `frappe.ValidationError`, NOT `frappe.PermissionError`? (Policy violation, not permission issue — surfaces as 417 not 403.)
- [ ] Does the PO guard trigger for `Inactive` AND `Blacklisted` AND `Pending Verification`?
- [ ] Does the Invoice guard trigger for `Blacklisted` AND `Pending Verification` ONLY (NOT Inactive)?
- [ ] Does the Payment Request guard trigger for `Blacklisted` AND `Pending Verification` ONLY (NOT Inactive)?
- [ ] Is the error message template `Cannot create {op_label}: Supplier {name_display} is {status}. {next_step}` (names all four variables)?
- [ ] Does the helper emit a Sentry breadcrumb via `set_backend_observability_context` when it denies? (DM-7)
- [ ] Is the Sentry call wrapped in `try/except` so observability failure never breaks the guard?
- [ ] Are there exactly three call sites (one per create endpoint)?
- [ ] Is the TIN threshold check at line 1491 still intact in `create_purchase_order`? (Do not remove when inserting the new guard.)
- [ ] Does every modified function still have its existing `set_backend_observability_context` call at the top?
- [ ] Is the test file at `hrms/api/tests/test_procurement_supplier_guard.py` with four test methods named exactly as listed in Phase 2?
- [ ] Does the test for Inactive assert that `invoice` and `payment_request` return `None` (not raise)?
- [ ] **(AUDIT AMENDMENT — Blocker 1)** In `create_invoice`, does the guard resolve supplier via `data.get("supplier")` → PO fallback → GR fallback BEFORE calling `_assert_supplier_active`? (A top-of-function `data.get("supplier")` ONLY check will silently skip for PO/GR-linked invoices.)
- [ ] **(AUDIT AMENDMENT — Blocker 2)** In `create_payment_request`, does the guard resolve supplier via `data.get("supplier")` → Invoice fallback → PO fallback BEFORE calling `_assert_supplier_active`? (Payment requests are typically linked via invoice; supplier is rarely passed directly.)
- [ ] **(AUDIT AMENDMENT — Blocker 3)** Does `create_purchase_order` now have `set_backend_observability_context(module="procurement", action="create_purchase_order", mutation_type="create")` at the top of the function body? (Pre-existing DM-7 gap — fix is mandatory in this sprint.)
- [ ] **(AUDIT AMENDMENT — Blocker 4)** Did Phase 0a produce `output/s193/controller_check.md` documenting whether the Supplier DocType controller allows direct status sets for all 4 values?
- [ ] **(AUDIT AMENDMENT — Blocker 5)** Are the 4 stable test supplier codes (`TEST-S193-ACTIVE`, `TEST-S193-INACTIVE`, `TEST-S193-BLACKLIST`, `TEST-S193-PENDING`) pre-staged before L3 via the setup script? (L3 scenarios reference these specific codes, not "any Blacklisted supplier".)
- [ ] **(AUDIT AMENDMENT — Blocker 6)** Has `parseFrappeError` in `bei-tasks/lib/frappe-api.ts` been verified to extract the Frappe `ValidationError` message so the frontend surfaces it, not a generic "Failed to create"?

## Zero-Skip Enforcement

Every task MUST be implemented, no exceptions. If a task cannot be completed, the agent STOPS and asks the user.

### Forbidden Agent Behaviors
- Skipping a task silently
- Marking partial work as "done"
- Combining Phase 1 call sites and dropping one
- Replacing the helper with inline checks (violates DRY rule)
- Implementing the guard but not wiring all three call sites
- Writing tests that only cover Active (happy path)
- Removing or weakening the TIN threshold check at line 1491

### Phase Completion Checklist Format

After each phase, the agent writes to `output/s193/phase_N_checklist.md`:
```
| Task | Status | Evidence | Skipped? | If skipped, why? |
```

### Machine-Verifiable Phase Gates

After Phase 0+1 (backend):
```bash
cd F:/Dropbox/Projects/BEI-ERP
git diff --name-only origin/production...HEAD | grep "hrms/api/procurement.py"
grep -c "def _assert_supplier_active" hrms/api/procurement.py          # expect 1
grep -c "_assert_supplier_active(" hrms/api/procurement.py             # expect >= 4
grep -c "_assert_supplier_active.*\"purchase_order\"" hrms/api/procurement.py    # expect 1
grep -c "_assert_supplier_active.*\"invoice\"" hrms/api/procurement.py           # expect 1
grep -c "_assert_supplier_active.*\"payment_request\"" hrms/api/procurement.py   # expect 1
grep -c "_SUPPLIER_BLOCK_ALL_STATUSES" hrms/api/procurement.py                   # expect >= 2
```

After Phase 2 (tests):
```bash
grep -c "def test_assert_supplier_active" hrms/api/tests/test_procurement_supplier_guard.py   # expect 4
python -c "import ast; ast.parse(open('hrms/api/tests/test_procurement_supplier_guard.py').read())"   # must not raise
```

After Phase 3 (closeout):
```bash
grep -c "^- status: PR_CREATED$" docs/plans/2026-04-14-sprint-193-supplier-status-guard.md   # expect 1
grep "S193.*PR_CREATED" docs/plans/SPRINT_REGISTRY.md    # must show PR number
```

---

## L3 Workflow Scenarios

> **Note:** L3 runs post-deploy against production. No frontend change in this sprint — scenarios exercise the backend guard via the existing procurement pages (which will show the Frappe error toast when the guard fires).

### L3 Prerequisites (AUDIT AMENDMENT — Blocker 5)

**Why this section exists:** The BEI Supplier `status` field is in `_SUPPLIER_APPROVAL_FIELDS` (see `hrms/api/procurement.py:563`) — normal edits to `status` go through the CPO approval workflow. L3 cannot spin up Blacklisted / Pending Verification / Inactive suppliers on demand.

**Before L3 runs, Sam (or an operator with `System Manager` role) stages four stable test suppliers via direct db writes (bypassing the approval workflow). These are fixtures, not real suppliers.**

| Test Supplier Code | Status to set | Purpose |
|--------------------|---------------|---------|
| `TEST-S193-ACTIVE` | `Active` | Baseline — all creates must succeed |
| `TEST-S193-INACTIVE` | `Inactive` | PO blocked; Invoice + RFP allowed |
| `TEST-S193-BLACKLIST` | `Blacklisted` | All three blocked |
| `TEST-S193-PENDING` | `Pending Verification` | All three blocked |

**Setup script (Sam runs via SSM frappe bench console, before L3):**
```python
# bench --site hq.bebang.ph console
import frappe
fixtures = [
    ("TEST-S193-ACTIVE", "Active"),
    ("TEST-S193-INACTIVE", "Inactive"),
    ("TEST-S193-BLACKLIST", "Blacklisted"),
    ("TEST-S193-PENDING", "Pending Verification"),
]
for code, status in fixtures:
    if not frappe.db.exists("BEI Supplier", code):
        frappe.get_doc({
            "doctype": "BEI Supplier",
            "supplier_code": code,
            "supplier_name": f"S193 Test Supplier — {status}",
            "status": "Active",  # create as Active
            "tin": "000-000-000-000",
        }).insert(ignore_permissions=True)
    # Bypass approval workflow for the target status
    frappe.db.set_value("BEI Supplier", code, "status", status, update_modified=False)
frappe.db.commit()
```

Scenarios below reference these exact codes (not "any Blacklisted supplier").

### Scenarios

| # | User | Action | Expected Outcome | Failure Means |
|---|------|--------|-------------------|---------------|
| L3-1 | test.procurement@bebang.ph | Supplier Hub → pick any Blacklisted supplier (or temporarily blacklist one via Supplier Edit) → click "Create PO" from supplier detail actions | Frappe error toast appears with text `Cannot create Purchase Order: Supplier {name} is Blacklisted. Contact Procurement Manager...` | Blacklist guard not wired to create_purchase_order |
| L3-2 | test.procurement@bebang.ph | Attempt to create a PO for a Pending Verification supplier | Error toast: `Cannot create Purchase Order: Supplier {name} is Pending Verification. Complete supplier verification...` | Pending Verification guard not wired |
| L3-3 | test.procurement@bebang.ph | Attempt to create a PO for an Inactive supplier | Error toast: `Cannot create Purchase Order: Supplier {name} is Inactive. Re-activate the supplier...` | Inactive guard not active for PO |
| L3-4 | test.procurement@bebang.ph | Attempt to create an Invoice for an Inactive supplier | **Succeeds** (or fails for other validation reasons, but NOT the supplier-status guard) | Policy regression — Inactive should NOT block invoices |
| L3-5 | test.accounts@bebang.ph | Attempt to create a Payment Request for a Blacklisted supplier | Error toast: `Cannot create Payment Request: Supplier {name} is Blacklisted. Contact Procurement Manager...` | Blacklist guard not wired to create_payment_request |
| L3-6 | test.procurement@bebang.ph | Create PO for an **Active** supplier | Succeeds (normal PO creation flow) | Guard is over-blocking — regression on Active |
| L3-7 | test.procurement@bebang.ph | After creating an Active-supplier PO, change the supplier status to Blacklisted, then attempt a second PO for the same supplier | First PO still exists and is unaffected; second PO blocked with Blacklisted error | Guard leaking into historical/in-flight transactions |
| L3-8 | test.accounts@bebang.ph | For the PO created in L3-7 (before blacklist), attempt to create an Invoice against it | **Fails** with Blacklisted error (invoice create endpoint also blocks Blacklisted) | Invoice guard not wired OR wired against wrong status set |

**L3 evidence files required before closeout:**
```
output/l3/s193/form_submissions.json    # attempted form submits (with expected failures)
output/l3/s193/api_mutations.json       # API call traces — ValidationError expected for 5 of 8 scenarios
output/l3/s193/state_verification.json  # no new PO/Invoice/RFP created for blocked scenarios
```

---

## Phase Budget Contract

| Phase | Units | Files Modified |
|-------|-------|----------------|
| Phase 0a — Controller + frontend error surface check (AMENDMENT) | 1 | read-only: `bei_supplier.py`, `frappe-api.ts` + `output/s193/controller_check.md` |
| Phase 0 — Helper function | 3 | `hrms/api/procurement.py` |
| Phase 1 — Wire 3 call sites + Sentry for create_purchase_order | 4 | `hrms/api/procurement.py` |
| Phase 2 — Unit tests | 3 | `hrms/api/tests/test_procurement_supplier_guard.py` |
| Phase 3 — PR + closeout | 1 | plan, registry |
| **Total** | **~12** | |

- hard_limit: 15 per phase
- All phases within budget.

---

## Ground-Truth Lock

- **evidence_sources:**
  - `hrms/hr/doctype/bei_supplier/bei_supplier.json` → `status` Select field, 4 options
  - `hrms/api/procurement.py:111-135` → `_resolve_supplier_identity` pattern for helper placement
  - `hrms/api/procurement.py:1455-1500` → `create_purchase_order` insertion point
  - `hrms/api/procurement.py:2392-2420` → `create_invoice` insertion point
  - `hrms/api/procurement.py:2709-2750` → `create_payment_request` insertion point
  - `hrms/api/procurement.py:1491` → TIN threshold pattern to mirror
- **authoritative_sections:** Delivery Phases 0-3 and Requirements Regression Checklist. Design Rationale is traceability.
- **normalization_required:** if any amendment changes the helper signature, status set, or call-site count, update the Verification sections and Machine-Verifiable Gates in the same edit.

---

## Anti-Rewind / Concurrent-Run Protection

- **ownership_matrix:** This sprint owns:
  - `hrms/api/procurement.py` — edits are confined to: (a) new helper insertion around line 135, (b) three insertions at the top of `create_purchase_order`, `create_invoice`, `create_payment_request`. No other line in this file is modified.
  - `hrms/api/tests/test_procurement_supplier_guard.py` — net new file.
- **protected_surfaces:** Every other function in `hrms/api/procurement.py` — DO NOT MODIFY. Specifically:
  - `_resolve_supplier_identity` (line 111) — untouched
  - TIN threshold check (line 1491 inside create_purchase_order) — untouched
  - All supplier getter endpoints (get_suppliers, get_supplier, get_supplier_grid, get_supplier_overview) — untouched
  - All approval/edit endpoints (submit_supplier_edit_for_approval, approve_supplier_edit) — untouched
- **remote_truth_baseline:** `origin/production` HEAD at time of branch creation. Record the SHA in Phase 3 closeout summary.
- **freshness_gate:** Before PR creation, run `GH_TOKEN="" gh api "repos/.../compare/s193-supplier-status-guard...production" --jq '.behind_by'`. If >0, rebase before pushing.

---

## Autonomous Execution Contract

- **completion_condition:**
  - `_assert_supplier_active` exists in `procurement.py` and matches the signature in Phase 0
  - All three create endpoints call it with the correct operation string
  - Unit test file exists with four test methods and is syntactically valid Python
  - PR created against `origin/production`
  - Plan YAML updated to `PR_CREATED`
  - `SPRINT_REGISTRY.md` row updated with PR number
  - Phase checklist files written to `output/s193/`
- **stop_only_for:**
  - Missing credentials for GitHub or Frappe repo
  - BEI Supplier DocType status Select options differ from `Active\nInactive\nBlacklisted\nPending Verification` (Design Rationale premise broken)
  - Merge conflict on `procurement.py` from concurrent work — rebase fails and needs manual resolution
  - Business-policy question: Sam wants to change which statuses block which endpoints
- **continue_without_pause_through:** code → test scaffolding → PR creation → closeout
- **blocker_policy:**
  - programmatic → fix and continue
  - test fixture conflict with existing test DB → mark failing test xfail with TODO, continue
  - repeated technical failure x3 → stop and present options
  - business-policy question → pause and ask Sam
- **signoff_authority:** single-owner (Sam)
- **canonical_closeout_artifacts:**
  - `docs/plans/2026-04-14-sprint-193-supplier-status-guard.md` (status updated to `PR_CREATED`)
  - `docs/plans/SPRINT_REGISTRY.md` (row updated)
  - `output/s193/phase_N_checklist.md` (per-phase)
  - `output/l3/s193/` (L3 evidence — deferred to post-deploy session)

---

## Execution Workflow

- Test Python changes: `/local-frappe`
- Deploy changes: PR-handoff (agent creates PR, Sam merges + deploys)
- Deploy requires `skip_build=false, no_cache=true` (new Python code — not just a config change)
- E2E testing: `/e2e-test` or fresh L3 session post-deploy

---

## Verification Checklist (Final)

- [ ] Helper `_assert_supplier_active(supplier, operation)` exists in `procurement.py`
- [ ] Helper raises `frappe.ValidationError` for Blacklisted + Pending Verification (all operations)
- [ ] Helper additionally raises for Inactive when operation is `purchase_order`
- [ ] Helper is called at top of `create_purchase_order` with `"purchase_order"` operation
- [ ] Helper is called at top of `create_invoice` with `"invoice"` operation
- [ ] Helper is called at top of `create_payment_request` with `"payment_request"` operation
- [ ] Error message includes: operation label, supplier display name, status, next step
- [ ] Sentry breadcrumb fires on denial (wrapped in try/except)
- [ ] TIN threshold check at line 1491 unchanged
- [ ] Four unit tests exist and import cleanly
- [ ] Machine-verifiable phase gate scripts pass
- [ ] PR created, plan YAML updated, registry updated

## Branch Lifecycle

| Branch | Repo | Merge Target | Cleanup |
|--------|------|--------------|---------|
| `s193-supplier-status-guard` | hrms | production | Delete after PR merge |

Created from latest `origin/production`. PR handoff — Sam merges, deploy requires full rebuild.
