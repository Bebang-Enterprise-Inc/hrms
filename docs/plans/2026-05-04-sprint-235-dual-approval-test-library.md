---
sprint_id: S235
sprint_title: Test Library Expansion — Real-User Dual Approval Verification
plan_branch: s235-dual-approval-test-library
status: COMPLETED
version: 2
created_date: 2026-05-04
revised_date: 2026-05-04
completed_date: 2026-05-04
backend_pr: 722
frontend_pr: 463
sweep_result: 45 PASS / 4 FAIL (same 4 stores as post-S234; all dispatch-step per-store stock issues, not S235 regressions)
sweep_skipping_ui_click_count: 0
execution_summary: |
  All phases complete. Library expanded with 3 new primitives.

  Phase A (library): forceDualApprovalOnOrder + OrderApprovalPage.approve(opts)
  + assertDualApprovalExercised. Zero backend changes (v2 audit-self-amendment
  dropped the originally-planned backend force_dual_approval param after
  realizing the existing Frappe API token already had write perms on the
  fields).

  Phase B (spec): s209-all-stores.spec.ts wires all three at the right
  call sites — forceDualApprovalOnOrder after submit, expectDualApproval=true
  on both OrderApprovalPage.approve calls, assertDualApprovalExercised after
  both clicks complete.

  Phase C (trial): single-store ARANETA trial pre-merge passed in 1.9m.
  BEI-ORD-2026-00980 verified dual approval with distinct approvers (test.area
  stage 1 at 11:26:51, test.scm stage 2 at 11:27:07).

  Phase D (post-deploy sweep): 45/49 PASS, 4 deterministic FAIL.
  Failed stores: AYALA VERMOSA, MEGAWORLD PASEO CENTER, ROBINSONS GENERAL
  TRIAS, ROBINSONS IMUS — same exact 4-store fail set as post-S234 sweep
  yesterday. All 4 fail at DispatchPage.dispatch's waitForToast (per-store
  stock at PCS-BKI source warehouse). Operational issue, not test infra.

  Outcome: SCM dual-approval surface healthy across 45 stores. The previous
  "44/49 effective" reporting in v15/v16/v17/post-S234 sweeps was technically
  accurate but masked the fact that 0 SCM UI clicks actually fired — all 49
  hit the early-return shortcut. From now on, sweeps that pass actually pass.
canonical_scope: none
canonical_scope_rationale: |
  Pure test infrastructure expansion in `bei-tasks/tests/e2e/`. No backend
  code changes. No Company/Warehouse/Customer/Supplier mutations. No
  SI/PO/MR/SE/JE/PE/GL Entry creation logic touched. The test helper flips
  `requires_dual_approval=1` on test-created orders only via the existing
  Frappe API token (used today by `frappeReadback.ts`) — same write surface
  any admin uses, no new exposure.
evidence_committed:
  - output/s235/SUMMARY.md
  - output/s235/verification/sweep_summary.md
  - output/s235/verification/dual_approval_sweep.log
  - output/s235/verification/state_after.json
  - output/s235/verification/trial_run.log
evidence_transient:
  - tmp/s235/probe_*.py
  - tmp/s235/probe_*.json
sprint_registry_row: |
  | `S235` | Sprint 235 | `s235-dual-approval-test-library` | TBD | PLANNED v2 2026-05-04 — Test Library Expansion: Real-User Dual Approval Verification | `docs/plans/2026-05-04-sprint-235-dual-approval-test-library.md` |
---

# S235 — Test Library Expansion: Real-User Dual Approval Verification (v2)

## v2 Summary

v1 proposed a backend change adding `force_dual_approval` param to `submit_order`. Audit/self-review concluded that approach is heavier than needed and adds a security-sensitive role gate. **v2 drops the backend change entirely.** Instead, the test library uses the existing Frappe API token (already used by `frappeReadback.ts`) to flip `requires_dual_approval=1` and `approval_stage="Pending Area Supervisor"` on test-created orders BETWEEN submission and area-approve. No backend code changes. Single bei-tasks PR.

## Why this exists (Design Rationale for Cold-Start Agents)

**The discovery (2026-05-04):** the post-S234 49-store sweep reported 44/49 PASS, but the SCM dual-approval UI click was being SKIPPED on every test. Investigation:

1. The spec calls `OrderApprovalPage.approve(orderId)` twice per test — once for area, once for SCM.
2. The method does a pre-click `readDoc` and **early-returns** if the order is `status="Approved"` AND (`scm_approved_at` set OR `approval_stage="Single Approval"`).
3. Inspection of post-S234 sweep orders (BEI-ORD-2026-00927+) shows ALL 49 orders had `approval_stage="Single Approval"`. The SCM call's early-return triggered for every test.
4. Backend reason: `submit_order` keys `requires_dual_approval` off `_validate_order_window` (`hrms/api/store.py:2961-2990`) which only returns `True` when `delivery_date == tomorrow AND now_hour >= 12` (Frappe server clock UTC). The sweep ran around UTC 06:37 → 07:50, so `now_hour < 12` → all orders were single-approval.
5. Test user roles probed via SSM:
   - `test.area@bebang.ph`: Area Manager + Area Supervisor + Employee + HR User (no SCM)
   - `test.scm@bebang.ph`: Regional Manager + Supply Chain Manager + Warehouse Manager (no Area)
   - So if dual approval IS forced, neither user can auto-complete the other's stage.

**The risk:** SCM dual-approval UI surface has never been exercised by automation. v15/v16/v17 sweeps reported 49/49 effective PASS while never actually clicking the SCM approve button on the post-area-approval state. A frontend regression breaking the SCM `approve-order-button` click handler — or the toast — would land silently.

**This sprint fixes it via test-library-only changes:**

- **Phase A (test library, ~12 units):** modify `OrderApprovalPage.approve()` to accept `expectDualApproval` option that disables the early-return + asserts the UI click was performed. Add `forceDualApprovalOnOrder(orderId)` helper in `tests/e2e/support/orderTestHelpers.ts` that uses the Frappe API token to flip `requires_dual_approval=1` and `approval_stage="Pending Area Supervisor"` on the order doc. Add `assertDualApprovalExercised(orderId)` assertion to `tests/e2e/assertions/orderAssertions.ts`.
- **Phase B (spec wiring, ~6 units):** modify `s209-all-stores.spec.ts` to call `forceDualApprovalOnOrder(orderId)` after submit, pass `expectDualApproval: true` to both approval calls, and call `assertDualApprovalExercised(orderId)` after the SCM step.
- **Phase C (trial + PR, ~5 units):** trial run on ARANETA only. If green, push branch + open PR.
- **Phase D (post-merge full sweep, ~5 units):** runs in a separate session after Sam merges. Verify all 49 stores exercise dual approval.

**What this is NOT:**
- NOT a backend change. The Frappe API token already has admin privileges; using it to set fields on a test-owned order is exactly what `frappeReadback.ts` does.
- NOT a fix for dispatch-step failures (VERMOSA / PASEO / GENERAL TRIAS / IMUS — pre-existing per-store stock issues).
- NOT a change to production approval policy. Real users still hit `_validate_order_window` cutoff logic.

## Test Library Discipline (mandatory)

All five non-negotiables apply:

1. **Library-first.** Modifying existing Page Objects + adding 1 new helper + 1 new assertion. No spec-level inline logic.
2. **Real-browser only for workflow ops.** Approval clicks happen in browser (no `page.request` shortcut). The `forceDualApprovalOnOrder` helper is environmental setup (flipping a DB flag), not a workflow shortcut — same category as `s209_grant_test_area_access.py`.
3. **Cleanup via cleanupLedger fixture.** All orders touched still go through normal cleanup ledger.
4. **Three-uses rule.** `assertDualApprovalExercised` will be called 49 times in this sweep alone. Compliant.
5. **`data-testid` everywhere.** Existing `[data-testid="approve-order-button"]` reused. No new IDs needed.

### Library audit (Phase 0)

Existing components reused:
- `bei-tasks/tests/e2e/pages/OrderApprovalPage.ts` (modify `approve()`)
- `bei-tasks/tests/e2e/support/frappeReadback.ts` (read+write API helpers — `forceDualApprovalOnOrder` extends this pattern)
- `bei-tasks/tests/e2e/assertions/orderAssertions.ts` (add new assertion)
- `bei-tasks/tests/e2e/specs/s209-all-stores.spec.ts` (modify call sites)
- `bei-tasks/tests/e2e/fixtures/cleanupLedger.ts` (no changes — orders still tracked)

### Library contributions (committed)

| File | Type | LOC delta | Purpose |
|---|---|---|---|
| `pages/OrderApprovalPage.ts` | modify | ~20 | `approve(orderId, opts: { expectDualApproval?: boolean })` |
| `support/orderTestHelpers.ts` | NEW | ~25 | `forceDualApprovalOnOrder(orderId)` |
| `assertions/orderAssertions.ts` | modify | ~25 | new fn `assertDualApprovalExercised(orderId)` |
| `specs/s209-all-stores.spec.ts` | modify | ~5 | wire new opts at 3 call sites |

Owned by S235; future sprints are consumers + extenders.

## Failure Response

- **Mode A (app bug):** SCM approve UI click fires but no toast / `approval_stage` doesn't transition. File `[BUG] s235 — SCM approve regression`. Halt sweep. Do NOT modify the test or library.
- **Mode B (test bug):** assertion logic wrong / Page Object selector miss. Fix the test/library directly. If fix generalizes, promote to library.
- **Mode C (brittleness/flakiness):** intermittent toast timing. Fix LIBRARY's wait helpers. No `waitForTimeout`, no `retry(3)` masking.

If ≥3 library fixes during execution, emit `output/l3/s235/LIBRARY_IMPROVEMENTS.md` as closeout artifact.

## Phases

### Phase 0 — Boot & Worktree Spawn (3 units)

**0-T1** Read this plan fully.

**0-T2** Spawn bei-tasks worktree (no hrms changes — single-repo sprint):
```bash
BR=s235-dual-approval-test-library
WT=F:/Dropbox/Projects/bei-tasks-${BR##*/}
cd F:/Dropbox/Projects/bei-tasks && git fetch origin --prune
git worktree add "$WT" -B "$BR" origin/main
cd "$WT" && npm ci --no-audit --no-fund
```

**0-T3** Capture baseline + verify file targets:
```bash
mkdir -p tmp/s235
cd F:/Dropbox/Projects/BEI-ERP && git rev-parse origin/production > tmp/s235/remote_truth_baseline_hrms.sha
git -C F:/Dropbox/Projects/bei-tasks rev-parse origin/main > tmp/s235/remote_truth_baseline_bei_tasks.sha
test -f F:/Dropbox/Projects/bei-tasks-s235-dual-approval-test-library/tests/e2e/pages/OrderApprovalPage.ts
test -f F:/Dropbox/Projects/bei-tasks-s235-dual-approval-test-library/tests/e2e/support/frappeReadback.ts
test -f F:/Dropbox/Projects/bei-tasks-s235-dual-approval-test-library/tests/e2e/assertions/orderAssertions.ts
test -f F:/Dropbox/Projects/bei-tasks-s235-dual-approval-test-library/tests/e2e/specs/s209-all-stores.spec.ts
```

### Phase A — Test Library Helpers (12 units)

**A-T1** Create `tests/e2e/support/orderTestHelpers.ts` with `forceDualApprovalOnOrder`:

```typescript
// MUST_MODIFY: tests/e2e/support/orderTestHelpers.ts (NEW)
// MUST_CONTAIN: "forceDualApprovalOnOrder"
// MUST_CONTAIN: "requires_dual_approval"
// MUST_CONTAIN: "Pending Area Supervisor"

import { setValue, readDoc } from "./frappeReadback";

/**
 * S235: flip a freshly-created BEI Store Order into dual-approval mode so the
 * test exercises the real-user SCM approval click. Default `submit_order`
 * gates dual approval on a clock-time check (cutoff at 12:00 server-time);
 * automation runs anytime so we force it post-submit via the same Frappe API
 * token that frappeReadback uses for readback.
 *
 * Idempotent: if the order is already dual, this is a no-op. Throws if the
 * order has already passed the area-approval stage (would corrupt state).
 */
export async function forceDualApprovalOnOrder(orderId: string): Promise<void> {
  const doc = await readDoc<{
    requires_dual_approval?: number;
    approval_stage?: string;
    status?: string;
  }>("BEI Store Order", orderId);

  if (doc.status !== "Pending Approval") {
    throw new Error(
      `forceDualApprovalOnOrder: ${orderId} is in status='${doc.status}' (expected 'Pending Approval'). ` +
      `Cannot retro-flip after approval flow has begun.`
    );
  }

  if (doc.requires_dual_approval === 1 && doc.approval_stage === "Pending Area Supervisor") {
    return;  // already dual
  }

  // Flip both fields. set_value calls hit the same DocType-level perms as any
  // admin would. With Test Automation API token, we have write access.
  await setValue("BEI Store Order", orderId, "requires_dual_approval", 1);
  await setValue("BEI Store Order", orderId, "approval_stage", "Pending Area Supervisor");
}
```

If `setValue` doesn't exist in `frappeReadback.ts`, add a minimal implementation:
```typescript
// in frappeReadback.ts (if not present):
export async function setValue(doctype: string, name: string, fieldname: string, value: unknown): Promise<void> {
  await getWithRetry(`${BASE}/api/method/frappe.client.set_value`, {
    method: "POST",
    headers: authHeaders(),
    body: new URLSearchParams({ doctype, name, fieldname, value: String(value) }),
  });
}
```

**A-T2** Modify `tests/e2e/pages/OrderApprovalPage.ts` to accept `expectDualApproval`:

```typescript
// MUST_MODIFY: tests/e2e/pages/OrderApprovalPage.ts
// MUST_CONTAIN: "expectDualApproval"

interface ApproveOpts {
  expectDualApproval?: boolean;
}

async approve(orderId: string, opts: ApproveOpts = {}) {
  if (!opts.expectDualApproval) {
    // existing early-return logic preserved for backward compat
    try {
      const doc = await readDoc<{
        status?: string;
        approved_at?: string | null;
        scm_approved_at?: string | null;
        approval_stage?: string;
      }>("BEI Store Order", orderId);
      if (
        doc.status === "Approved" &&
        doc.approved_at &&
        (doc.scm_approved_at || doc.approval_stage === "Single Approval")
      ) {
        console.log(`[OrderApprovalPage.approve] ${orderId} already approved; skipping UI click.`);
        return;
      }
    } catch {
      /* fall through */
    }
  }

  // Always run UI flow when expectDualApproval=true OR when not already approved.
  await this.go();
  // ... existing UI flow (navigate, openOrder, click approve, wait for toast)
  // unchanged from current code
}
```

**A-T3** Add `assertDualApprovalExercised` to `tests/e2e/assertions/orderAssertions.ts`:

```typescript
// MUST_MODIFY: tests/e2e/assertions/orderAssertions.ts
// MUST_CONTAIN: "assertDualApprovalExercised"

import { expect } from "@playwright/test";
import { readDoc } from "../support/frappeReadback";

/**
 * S235: assert a BEI Store Order went through both approval stages
 * (area-supervisor stage 1 + warehouse-manager stage 2) with distinct
 * approvers. Use this after both `OrderApprovalPage.approve` calls in
 * dual-approval test paths to prove the SCM UI click actually ran.
 */
export async function assertDualApprovalExercised(orderId: string): Promise<void> {
  const doc = await readDoc<{
    status?: string;
    approval_stage?: string;
    requires_dual_approval?: number;
    approved_at?: string | null;
    approved_by?: string | null;
    scm_approved_at?: string | null;
    second_approver?: string | null;
    second_approval_date?: string | null;
  }>("BEI Store Order", orderId);

  expect(doc.requires_dual_approval, `${orderId}: requires_dual_approval`).toBe(1);
  expect(doc.status, `${orderId}: status`).toBe("Approved");
  expect(doc.approval_stage, `${orderId}: approval_stage`).toBe("Fully Approved");
  expect(doc.approved_at, `${orderId}: approved_at (stage 1 timestamp)`).toBeTruthy();
  expect(doc.approved_by, `${orderId}: approved_by (stage 1 user)`).toBeTruthy();
  expect(doc.second_approver, `${orderId}: second_approver (stage 2 user)`).toBeTruthy();
  expect(doc.second_approval_date, `${orderId}: second_approval_date (stage 2 timestamp)`).toBeTruthy();
  expect(doc.approved_by, `${orderId}: distinct approvers`).not.toBe(doc.second_approver);
}
```

**A-T4** Commit Lane A on bei-tasks branch:
```bash
git add tests/e2e/support/orderTestHelpers.ts tests/e2e/support/frappeReadback.ts tests/e2e/pages/OrderApprovalPage.ts tests/e2e/assertions/orderAssertions.ts
git commit -m "test(S235-A): library — forceDualApprovalOnOrder + expectDualApproval + assertDualApprovalExercised"
```

**Phase A verify:**
```python
import sys, os
WT = "F:/Dropbox/Projects/bei-tasks-s235-dual-approval-test-library"
errs = []
expectations = {
    f"{WT}/tests/e2e/support/orderTestHelpers.ts": ["forceDualApprovalOnOrder", "requires_dual_approval", "Pending Area Supervisor"],
    f"{WT}/tests/e2e/pages/OrderApprovalPage.ts": ["expectDualApproval"],
    f"{WT}/tests/e2e/assertions/orderAssertions.ts": ["assertDualApprovalExercised", "second_approver"],
}
for path, musts in expectations.items():
    if not os.path.exists(path):
        errs.append(f"MISSING: {path}")
        continue
    content = open(path, encoding="utf-8").read()
    for m in musts:
        if m not in content:
            errs.append(f"MUST_CONTAIN '{m}' in {path}")
print("PASS" if not errs else "\n".join(errs))
sys.exit(0 if not errs else 1)
```

### Phase B — Spec Wiring (6 units)

**B-T1** Modify `tests/e2e/specs/s209-all-stores.spec.ts`:

```typescript
// MUST_MODIFY: tests/e2e/specs/s209-all-stores.spec.ts
// MUST_CONTAIN: "forceDualApprovalOnOrder"
// MUST_CONTAIN: "expectDualApproval: true"
// MUST_CONTAIN: "assertDualApprovalExercised"

// Add imports near other imports:
import { forceDualApprovalOnOrder } from "../support/orderTestHelpers";
import { assertDualApprovalExercised } from "../assertions/orderAssertions";

// In the per-store test body, after submit and before area approval:
const ordering = new StoreOrderingPage(loggedInAreaSupervisor);
const { orderId, itemsFilled } = await ordering.submitOrderAtSuggested(
  entry.store, "DRY",
  { itemCount: 3, orderStoreOverride: entry.warehouse_docname }
);
rec.orderId = orderId;
await ledger.record("order-create", { name: orderId, store: entry.store });

// S235: flip into dual-approval mode (production cutoff is clock-dependent;
// automation needs deterministic dual flow regardless of run time)
await forceDualApprovalOnOrder(orderId);

await snapshot(loggedInAreaSupervisor, slug, "01_order_submitted");
await assertOrderCompany(orderId, entry.company);

// Approvals — both must exercise UI clicks
const areaApproval = new OrderApprovalPage(loggedInAreaSupervisor);
await areaApproval.approve(orderId, { expectDualApproval: true });  // S235
await snapshot(loggedInAreaSupervisor, slug, "02a_area_approved");

const scmApproval = new OrderApprovalPage(loggedInSCM);
await scmApproval.approve(orderId, { expectDualApproval: true });  // S235
await snapshot(loggedInSCM, slug, "02b_scm_approved");

// S235: assert both stages actually ran in the browser
await assertDualApprovalExercised(orderId);

// existing dispatch / receive / SI assertions follow unchanged
```

**B-T2** Commit Lane B on bei-tasks branch:
```bash
git add tests/e2e/specs/s209-all-stores.spec.ts
git commit -m "test(S235-B): wire dual-approval helpers into 49-store sweep"
```

**Phase B verify:**
```python
import sys, os
spec = "F:/Dropbox/Projects/bei-tasks-s235-dual-approval-test-library/tests/e2e/specs/s209-all-stores.spec.ts"
content = open(spec, encoding="utf-8").read()
errs = []
for m in ["forceDualApprovalOnOrder", "expectDualApproval: true", "assertDualApprovalExercised"]:
    if m not in content: errs.append(f"spec MUST_CONTAIN: {m}")
# also count expectDualApproval: true occurrences (should be 2 — area + SCM)
if content.count("expectDualApproval: true") < 2:
    errs.append(f"spec needs 2x expectDualApproval: true (got {content.count('expectDualApproval: true')})")
print("PASS" if not errs else "\n".join(errs))
sys.exit(0 if not errs else 1)
```

### Phase C — Trial Run + PR (5 units)

**C-T1** Run a single-store trial to validate the helpers end-to-end before opening the PR. Pre-condition: hrms backend hasn't changed; this works against current production.

```bash
cd F:/Dropbox/Projects/bei-tasks-s235-dual-approval-test-library
S209_STORES_FILTER="ARANETA GATEWAY - TUNGSTEN CAPITAL HOLDINGS OPC" \
  E2E_PASSWORD="BeiTest2026!" \
  FRAPPE_API_KEY="$(C:/Users/Sam/bin/doppler.exe secrets get FRAPPE_API_KEY --plain --project bei-erp --config dev)" \
  FRAPPE_API_SECRET="$(C:/Users/Sam/bin/doppler.exe secrets get FRAPPE_API_SECRET --plain --project bei-erp --config dev)" \
  S209_EVIDENCE_ROOT="F:/Dropbox/Projects/BEI-ERP/output/l3/s235-trial" \
  BEI_ERP_ROOT="F:/Dropbox/Projects/BEI-ERP" \
  npx playwright test specs/s209-all-stores.spec.ts --reporter=list --workers=1 --timeout=180000 \
  2>&1 | tee output/s235/verification/trial_run.log
```

**Pass conditions:**
- ARANETA test PASSES (1 passed, 0 failed)
- Log shows `[OrderApprovalPage.approve]` does NOT skip UI click (no "already approved" line for ARANETA's order)
- `assertDualApprovalExercised` passes (no expect failures)
- The order shows `approved_at != second_approval_date` and `approved_by != second_approver`

**Fail diagnosis:**
- If `forceDualApprovalOnOrder` throws: check API token has write perm on `BEI Store Order`. Mode B fix.
- If area approval times out at toast: SCM stage 1 click broken. Mode A — file bug, halt.
- If SCM approval times out at toast: SCM stage 2 click broken. Mode A — file bug, halt. **This is exactly what we suspect; surfacing it is the point of this sprint.**
- If `assertDualApprovalExercised` fails on `approved_by != second_approver`: same user is both approvers (test.area auto-completed both). Mode A — investigate role grants.

**C-T2** Commit any trial-driven library fixes (Mode B) and re-run trial. Loop until green or escalate.

**C-T3** Push branch + open PR:
```bash
cd F:/Dropbox/Projects/bei-tasks-s235-dual-approval-test-library
git push -u origin s235-dual-approval-test-library
GH_TOKEN="" gh pr create --repo Bebang-Enterprise-Inc/BEI-Tasks --base main --head s235-dual-approval-test-library \
  --title "test(S235): real-user dual approval verification — library + sweep wiring" \
  --body-file output/s235/PR_BODY.md
```

**Phase C verify:**
```python
import sys, os, re
errs = []
trial_log = "output/s235/verification/trial_run.log"
if not os.path.exists(trial_log):
    errs.append(f"MISSING: {trial_log} (trial did not run)")
else:
    log = open(trial_log, encoding="utf-8", errors="replace").read()
    if "1 passed" not in log: errs.append(f"trial did not pass (looking for '1 passed' in log)")
    # Verify NO skip line for the ARANETA test
    if re.search(r"\[OrderApprovalPage\.approve\] BEI-ORD-\S+ already approved", log):
        errs.append("trial skipped UI click (expectDualApproval not honored)")
print("PASS" if not errs else "\n".join(errs))
sys.exit(0 if not errs else 1)
```

### Phase D — Closeout (5 units, runs in fresh session POST-MERGE)

**D-T1** After PR merges and Vercel deploys (frontend test code only — no backend deploy needed), run the FULL 49-store sweep with the new dual-approval verification:

```bash
# fresh worktree from origin/main (post-merge)
BR=test/s235-post-deploy-sweep
WT=F:/Dropbox/Projects/bei-tasks-${BR##*/}
cd F:/Dropbox/Projects/bei-tasks && git fetch origin --prune
git worktree add "$WT" -B "$BR" origin/main
cd "$WT" && npm ci

E2E_PASSWORD="BeiTest2026!" \
FRAPPE_API_KEY="..." FRAPPE_API_SECRET="..." \
S209_EVIDENCE_ROOT="F:/Dropbox/Projects/BEI-ERP/output/l3/s235-post-deploy" \
BEI_ERP_ROOT="F:/Dropbox/Projects/BEI-ERP" \
npx playwright test specs/s209-all-stores.spec.ts --reporter=list --workers=1 --timeout=180000 \
2>&1 | tee output/l3/s235-post-deploy/sweep.log
```

**D-T2** Write `output/s235/verification/sweep_summary.md` with per-store dual-approval verification results. Categorize:
- **PASS (dual approval exercised):** order has `requires_dual_approval=1`, `approved_by != second_approver`
- **FAIL at SCM UI:** SCM browser click didn't produce toast (Mode A — file bug)
- **FAIL at dispatch:** pre-existing per-store stock issue (S234 follow-up, not S235)

**D-T3** Update plan YAML: `status: COMPLETED`, populate `frontend_pr`, `sweep_result`, `dual_approval_pass_count`.

**D-T4** Update SPRINT_REGISTRY.md S235 row → COMPLETED with PR# + sweep counts.

**D-T5** Write `output/s235/SUMMARY.md`. Worktree closeout:
```bash
cd F:/Dropbox/Projects/bei-tasks-s235-dual-approval-test-library && git status --short
cd F:/Dropbox/Projects/bei-tasks && git worktree remove F:/Dropbox/Projects/bei-tasks-s235-dual-approval-test-library
git worktree remove F:/Dropbox/Projects/bei-tasks-s235-post-deploy-sweep
cd F:/Dropbox/Projects/BEI-ERP && git worktree remove F:/Dropbox/Projects/BEI-ERP-s235-dual-approval-test-library
```

## Autonomous Execution Contract

- completion_condition:
  - Phase A: 4 library files compile + verify_phase_a passes
  - Phase B: spec wired with all 3 hooks
  - Phase C: trial run on ARANETA passes — order goes through dual flow with distinct approvers
  - Phase C: PR created and shared with Sam
  - (D runs in fresh post-merge session) Phase D: full sweep verifies all 49 stores exercise dual approval
- stop_only_for:
  - Trial reveals SCM dual-approval UI is genuinely broken in production (Mode A) — file bug, halt, do not push spec changes that would mask the regression
  - Frappe API token does NOT have write permission on BEI Store Order (no fallback besides backend change — kick back to v3 plan with backend lane)
  - 3 consecutive Mode B test fixes during trial — stop and reassess library design
- continue_without_pause_through:
  - Library writes → spec wiring → trial → PR creation
- blocker_policy:
  - readback API write rejected → revisit auth (use Administrator-token over service-account-token if needed)
  - Trial passes but full sweep at D-T1 reveals systemic SCM regression → back out spec change pending bug fix
- signoff_authority: `single-owner` (Sam)
- canonical_closeout_artifacts:
  - `output/s235/SUMMARY.md`
  - `output/s235/verification/sweep_summary.md`
  - `output/s235/verification/dual_approval_sweep.log`
  - `output/s235/verification/trial_run.log`
  - `docs/plans/2026-05-04-sprint-235-dual-approval-test-library.md` (status COMPLETED)
  - `docs/plans/SPRINT_REGISTRY.md` (S235 row → COMPLETED)

## Phase Budget Contract

- Phase 0: 3 units
- Phase A: 12 units (library — biggest)
- Phase B: 6 units
- Phase C: 5 units (trial + PR)
- Phase D: 5 units (post-merge sweep, runs separately)
- **Total: 31 units** (well under 80-unit S089 ceiling)

## Surface Ownership Matrix (S087)

| Surface | Owner | Allowed |
|---|---|---|
| `bei-tasks/tests/e2e/support/orderTestHelpers.ts` | S235 | NEW file |
| `bei-tasks/tests/e2e/support/frappeReadback.ts` | S235 | extend with `setValue` if missing |
| `bei-tasks/tests/e2e/pages/OrderApprovalPage.ts` | S235 | extend `approve()` only |
| `bei-tasks/tests/e2e/assertions/orderAssertions.ts` | S235 | add new fn only |
| `bei-tasks/tests/e2e/specs/s209-all-stores.spec.ts` | S235 | wire opts at 3 call sites |
| `hrms/api/store.py` and ALL backend code | NOT S235 | NO MODIFICATIONS |
| Production order workflow semantics | NOT S235 | UNCHANGED |

## Anti-Rewind / Concurrent-Run Protection

- protected_surfaces:
  - `_validate_order_window` — UNCHANGED
  - `submit_order` backend — UNCHANGED
  - All hrms files — UNCHANGED
- remote_truth_baseline: TBD in Phase 0
- pretouch_backup: not applicable (test files only)
- supersession_map: replaces nothing in production. Pure additive test infra.

## Requirements Regression Checklist

- [ ] No backend code modified (zero changes under `hrms/`)
- [ ] `OrderApprovalPage.approve()` preserves existing behavior when `expectDualApproval` is false/omitted (backward compat)
- [ ] `forceDualApprovalOnOrder` is a no-op if order is already dual (idempotent)
- [ ] `forceDualApprovalOnOrder` THROWS if order is past `Pending Approval` status (no state corruption)
- [ ] `assertDualApprovalExercised` checks `approved_by != second_approver` (proves distinct browser sessions clicked)
- [ ] Spec passes `expectDualApproval: true` to BOTH approvals (count == 2)
- [ ] Spec calls `assertDualApprovalExercised(orderId)` after both approvals
- [ ] Trial run on ARANETA PASSES end-to-end before opening PR
- [ ] No production canonical data touched (canonical_scope=none verified)

## Sprint Registry Row (Evidence of Lock)

```
| `S235` | Sprint 235 | `s235-dual-approval-test-library` | TBD | PLANNED v2 2026-05-04 — Test Library Expansion: Real-User Dual Approval Verification | `docs/plans/2026-05-04-sprint-235-dual-approval-test-library.md` |
```

Cross-checked: `git branch -a | grep s235` returned no matches on hrms or bei-tasks before reservation; `ls docs/plans/ | grep sprint-235` empty.

## Execution Authority

Single agent, single session through Phase A + B + C trial + PR. Phase D-T1 (full 49-store sweep with dual approval) runs in a fresh session AFTER the PR merges + Vercel deploys.

Stop only for items in `stop_only_for`. Treat trial-run failure as Mode A/B/C debugging, not a stop.
