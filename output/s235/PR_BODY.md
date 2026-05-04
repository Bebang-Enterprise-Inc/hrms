# S235 — Test Library Expansion: Real-User Dual Approval Verification

Plan: `docs/plans/2026-05-04-sprint-235-dual-approval-test-library.md` (BEI-ERP repo, gitignored)
Sprint registry: BEI-ERP `docs/plans/SPRINT_REGISTRY.md` row added (gitignored, will be committed via separate hrms PR)

## Why this exists

The post-S234 49-store sweep reported 44/49 PASS, but inspection of the sweep log revealed `[OrderApprovalPage.approve] BEI-ORD-XXX already approved (status=Approved); skipping UI click.` for **every single test**. The SCM dual-approval UI click was being **bypassed** on all 49 stores via the existing early-return shortcut in `OrderApprovalPage.approve()`.

Backend root cause (no fix needed in this PR — backend behavior is correct for production):
- `submit_order` at `hrms/api/store.py:3084` reads `requires_dual_approval` from `_validate_order_window` (lines 2961-2990).
- That function ONLY returns `True` when `delivery_date == tomorrow AND now_hour >= 12` (Frappe server clock — UTC).
- The sweep ran around UTC 06:37 → all orders received `approval_stage="Single Approval"`.
- The Page Object's early-return triggered for the SCM call on every test → 0/49 SCM UI clicks actually happened.

Result: a ~6-week gap where the SCM dual-approval surface was untested by automation. Any frontend regression breaking the SCM `approve-order-button` click handler or its toast would land silently.

## What this PR ships

Three test library primitives + one spec wiring change:

| File | Type | Purpose |
|---|---|---|
| `tests/e2e/support/orderTestHelpers.ts` | NEW (~80 LOC) | `forceDualApprovalOnOrder(orderId)` — flips a `Pending Approval` order into dual mode via Frappe `set_value` API (same auth surface `frappeReadback` + `ssmSetup:disableBEIItem` already use) |
| `tests/e2e/pages/OrderApprovalPage.ts` | MODIFIED | `approve(orderId, opts: { expectDualApproval?: boolean })` — when `true`, the `status=Approved` early-return is bypassed so the UI click MUST happen |
| `tests/e2e/assertions/orderAssertions.ts` | MODIFIED | `assertDualApprovalExercised(orderId)` — proves both approval stages ran with distinct approvers (stage 1 `approved_by` ≠ stage 2 `second_approver`) |
| `tests/e2e/assertions/index.ts` | MODIFIED | export the new assertion |
| `tests/e2e/specs/s209-all-stores.spec.ts` | MODIFIED | wire all three: `forceDualApprovalOnOrder` after submit, `expectDualApproval: true` on both approvals, `assertDualApprovalExercised` after both clicks |

## Trial run evidence (single store, ARANETA)

```
Running 1 test using 1 worker
[S209 preflight] [S209] total=49 mutated=0 already_set=49 ...
✓  1 happy chain — ARANETA GATEWAY - TUNGSTEN CAPITAL HOLDINGS OPC (1.9m)
1 passed (2.1m)
```

**Zero `[OrderApprovalPage.approve] ... skipping UI click` lines** in the trial log — early-return correctly bypassed.

Order state post-trial (proof both UI clicks fired):
```json
{
  "name": "BEI-ORD-2026-00980",
  "status": "Approved",
  "requires_dual_approval": 1,
  "approval_stage": "Fully Approved",
  "approved_at":            "2026-05-04 11:26:51.194870",
  "approved_by":            "test.area@bebang.ph",
  "second_approver":        "test.scm@bebang.ph",
  "second_approval_date":   "2026-05-04 11:27:07.681293"
}
```

Distinct approvers: `test.area` for stage 1, `test.scm` for stage 2. Distinct timestamps: 16 seconds apart. Both real-browser UI clicks.

## Backward compatibility

- `OrderApprovalPage.approve(orderId)` (no opts) — UNCHANGED behavior. Existing tests work as before.
- `submit_order` backend — UNCHANGED. Production users hit the same `_validate_order_window` cutoff logic.
- The Frappe API token used by `forceDualApprovalOnOrder` is the same one `frappeReadback.ts` and `ssmSetup.ts:disableBEIItem` already use — no new credential surface.
- Idempotent + status-guarded: `forceDualApprovalOnOrder` is a no-op if the order is already dual; throws if the order is past `Pending Approval` to prevent state corruption.

## Per-task checklist

| Phase | Task | Status |
|---|---|---|
| 0-T1 | Read plan | ✅ |
| 0-T2 | Spawn worktree | ✅ `s235-dual-approval-test-library` |
| 0-T3 | Capture baselines | ✅ |
| A-T1 | `forceDualApprovalOnOrder` | ✅ committed `1bcb432` |
| A-T2 | `OrderApprovalPage.approve(opts)` | ✅ |
| A-T3 | `assertDualApprovalExercised` | ✅ |
| A-T4 | Lane A commit | ✅ |
| B-T1 | Spec wiring | ✅ |
| B-T2 | Lane B commit | ✅ (combined with A) |
| C-T1 | Trial run on ARANETA | ✅ PASS in 1.9m |
| C-T2 | Mode B fixes if needed | ✅ none required |
| C-T3 | Push + open PR | ✅ this PR |
| D-T1+ | Full 49-store sweep | ⏳ post-merge in fresh session |

## Risk

- ❌ Backend regression — verified absent. Zero changes under `hrms/`.
- ❌ Production order policy change — verified absent. `forceDualApprovalOnOrder` only flips test-created orders post-submit; production users never call this helper.
- ⚠️ Sweep duration — adds ~10-15s per test for the helper + assertion, plus the SCM UI click (~10-15s) which was previously skipped. Estimated +20-25s per test × 49 stores = +15-20 min added to the sweep total. Trial showed 1.9m for ARANETA (vs ~1.5m baseline) — within the expected range.

## Failure mode possibilities (Phase D-T1 surveillance)

When the full sweep runs post-merge:
- **Most pass + a few fail at SCM UI:** real bug surfaced (Mode A — file `[BUG] s235-X` per Failure Response). This is exactly what this PR is designed to catch.
- **All pass:** dual-approval surface is healthy across all 49 stores.
- **All fail at `forceDualApprovalOnOrder`:** auth/permission issue with `set_value` on the `requires_dual_approval` or `approval_stage` fields. Would need a backend escalation to grant write perm via API token.

## Verification commands (post-merge)

```bash
# Spawn fresh worktree from origin/main
cd F:/Dropbox/Projects/bei-tasks && git fetch origin --prune
git worktree add F:/Dropbox/Projects/bei-tasks-s235-post-merge -B test/s235-post-merge-sweep origin/main
cd F:/Dropbox/Projects/bei-tasks-s235-post-merge && npm ci

# Run 49-store sweep with new dual-approval verification
E2E_PASSWORD="BeiTest2026!" \
FRAPPE_API_KEY="$(doppler ...)" FRAPPE_API_SECRET="$(doppler ...)" \
S209_EVIDENCE_ROOT="F:/Dropbox/Projects/BEI-ERP/output/l3/s235-post-deploy" \
BEI_ERP_ROOT="F:/Dropbox/Projects/BEI-ERP" \
npx playwright test specs/s209-all-stores.spec.ts --reporter=list --workers=1 --timeout=180000
```

---

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
