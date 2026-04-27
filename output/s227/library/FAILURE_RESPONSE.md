# S227 Failure Response Model (Phase 0.5)

Per `.claude/docs/qa-test-library-discipline.md` §"Failure Discipline", every L3 failure is
classified as Mode A / Mode B / Mode C, and the response differs by mode.

## Mode A — App bug (the feature is broken)

**Symptoms:**
- API response leaks a fleet field (e.g., `fleet_rank` present when partner)
- Sidebar shows a forbidden module (e.g., Procurement)
- 403 on `/dashboard/analytics/product` for partner (page-level RoleGuard misconfigured)
- Frontend renders a fleet-only UI element when the field is absent (e.g., empty Fleet Rank header with `—` cells)

**Action:**
1. File `[BUG]` against the relevant phase task in `output/s227/DEFECTS.md`.
2. Push a fix to `s227-store-partner-analytics` (the in-flight branch — PR not yet created).
3. Re-run the L3 spec.
4. Do NOT modify test code or library to "make the test pass" — the test is correct; the app is wrong.

## Mode B — Test bug (the test asserts the wrong thing)

**Symptoms:**
- Test asserts `expect(response.fleet_rank).toBeDefined()` for partner (wrong direction)
- Test uses a third-party store name that's actually within partner scope
- Test selector matches a different element than intended

**Action:**
1. Fix the test.
2. If the fix is a generic pattern (e.g., a robust modal-close helper), promote it to a Page Object method or a fixture, then reference it from the spec.
3. Update the relevant entry in `output/s227/library/CONTRIBUTIONS.md`.

## Mode C — Brittleness / flakiness

**Symptoms:**
- Spec passes 3 times then fails once on the same selector
- `waitForLoadState("networkidle")` races against background polling
- A modal appears then auto-dismisses before the assert fires

**Action:**
1. **NEVER** apply `waitForTimeout(3000)` or `retry(3)` at the test level — that's a coverup.
2. Identify the root cause:
   - Network race → assert on a stable post-render testid, not a transient overlay
   - Missing test ID → file a frontend task to add the test ID, then re-run
   - Server-side timing (e.g., dashboard cache warm) → seed before navigation
3. Fix in the LIBRARY (Page Object method, fixture, or selectors.ts), not the spec.
4. If `≥3` Mode C fixes happen during execution, emit `output/s227/library/LIBRARY_IMPROVEMENTS.md`
   listing each root cause + resolution. This is how the library gets better.

## Decision matrix

| Failure | Mode | First instinct | Correct response |
|---|---|---|---|
| Partner sees `fleet_rank: 7` in `/api/analytics/sales/product-mix` response | A | "Make the test more lenient" → WRONG | Fix the backend strip helper; re-run |
| Test fails because assertion expected sidebar item "Sales" but UI says "Analytics → Sales" | B | "Edit the assertion text" | Fix test selector; promote a `assertSidebarItem(label)` helper if it's used elsewhere |
| Page Object's `pickStore()` flakes on first run, passes on second | C | "Add `await page.waitForTimeout(500)`" → WRONG | Inspect the DOM mutation pattern; assert on the post-pick stable state (e.g., URL param or store-summary text), not a transient picker |

## Cross-reference

- L3 scenarios → plan §"L3 Workflow Scenarios"
- Library contributions → `output/s227/library/CONTRIBUTIONS.md`
- Verification script → `output/s227/verify_phase_completion.py`
