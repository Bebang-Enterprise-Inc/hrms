# S194 Post-Cert Deferred Defects

Defects discovered during S194 Phase S iteration that are out-of-scope for the procurement chain certification itself. Address in the post-cert cleanup PR after 31/31 PASS.

## ARCH-S194-01 — Tasks app auto-modal in CEO Playwright session (BLOCKER, deferred)

**Severity:** BLOCKING for tests using `sam@bebang.ph` storage state.

**Symptom:** When a Playwright context loads with sam@bebang.ph cookies and navigates to `/dashboard/procurement/purchase-requisitions/new`, the bei-tasks app's "Create New Task" Radix Dialog auto-opens and intercepts every click. Modal cannot be dismissed via Escape, Cancel, Close button, or DOM removal — React re-renders it.

**Reproduction:**
```ts
const ctx = await browser.newContext();
const page = await ctx.newPage();
await new LoginPage(page).loginAs("sam@bebang.ph", "2289454");
await page.goto("https://my.bebang.ph/dashboard/procurement/purchase-requisitions/new");
// Snapshot shows "Create New Task" dialog overlaying the PR form
```

**Workaround tried:** Switched `procurementPages` default to `mae@bebang.ph` (CPO/Procurement Manager). Mae logs in cleanly (no auto-modal) but **routes silently land on `/my-tasks` regardless of the goto target URL** — see ARCH-S194-02.

**Root cause hypothesis:** Some onboarding hook or storage-state replay opens the Tasks dialog for users with the System Manager role on session restore.

**Fix path (out of S194 scope):** Investigate `app/(auth)/login` or `app/dashboard/layout.tsx` for any `useEffect` that opens the Tasks dialog based on user role / session state.

## ARCH-S194-02 — Procurement deep-links redirect to /my-tasks for non-CEO users (BLOCKER, deferred)

**Severity:** BLOCKING for any Playwright test that navigates to `/dashboard/procurement/*` as a non-CEO user.

**Symptom:** With mae@bebang.ph (CPO/Procurement Manager) successfully logged in, calling `page.goto("https://my.bebang.ph/dashboard/procurement/purchase-requisitions/new")` does NOT load the PR form. The page remains/lands on `/my-tasks` showing "Failed to load tasks: User mae@bebang.ph does not have doctype access via role permission for document Task".

**Reproduction:** Same as ARCH-S194-01 but with mae credentials.

**Root cause hypothesis:** The bei-tasks app shell has a default landing redirect that fires when the route's preconditions aren't satisfied. mae has Procurement Manager role per `lib/roles.ts:39`, but the route guard may check for a different role (e.g., Procurement User explicitly), OR the redirect happens before the procurement page's RoleGuard evaluates.

**Fix path (out of S194 scope):** Trace the layout or middleware that redirects authenticated users away from `/dashboard/procurement/*` deep links. Check `MODULES.PROCUREMENT` membership for both PROCUREMENT_USER and PROCUREMENT_MANAGER roles consistently across all guards.

## RBAC-S194-24 — Warehouse User cannot access supplier grid (deferred from earlier sweep)

**Severity:** Real product finding — contradicts S193 audit amendment claim.

**Symptom:** Logged in as test.warehouse@bebang.ph, navigating to `/dashboard/procurement/suppliers` shows only Dashboard / Warehouse / Commissary in the sidebar — no procurement section. The S193 audit amendment claimed Warehouse was added to PROCUREMENT module for read-only supplier visibility.

**Fix path (out of S194 scope):** Reconcile S193 audit amendment with `lib/roles.ts` — either the amendment didn't ship, or Warehouse Staff was added at a finer-grained level than the route guard accepts.

## AUTH-S194-23 — seededProcurementUser doesn't establish working session (deferred)

**Severity:** BLOCKING for S194-23 (Procurement User negative RBAC test).

**Symptom:** `seededProcurementUser()` SSM call returns success (User doc created on Frappe), but `loggedInAsProcurementUser` fixture's loginAs fails almost instantly (308ms), suggesting cookie issues or insufficient roles for actual login.

**Fix path:** Add additional baseline roles (e.g., `Employee Self Service`, `Frappe User`) to the seeded user beyond `Procurement User` so login succeeds.

---

## Iteration progress recorded

- Phase iteration cycle 1 (2026-04-15) attempted on S194-1 only.
- Fixes shipped in PR #398 commit `e5538d8` then iterated further locally:
  - `PurchaseRequisitionPage.fillItems`: rewritten to drive ItemSearchCombobox properly (Popover trigger → CommandInput type → option click).
  - `PurchaseRequisitionPage.setDepartment`: waits for "Loading departments" hidden + types into Radix Select for filtering.
  - `openNew` adds modal dismissal sequence.
  - `procurementPages` switched from CEO to Mae default user.
- Blocked at ARCH-S194-01 / ARCH-S194-02. Cannot iterate further until app-shell auth-routing behavior is understood.

## Recommendation

Mark S194 Phase S as **NOT_CERTIFIED** with two architectural blockers (ARCH-01, ARCH-02) requiring app-shell investigation before the certification cycle can proceed. Both blockers are in code outside the S194 plan scope (auth + Next.js routing in bei-tasks layout).

The cleanest path is a separate sprint or Sam-direct intervention to:
1. Disable the Tasks auto-modal in Playwright sessions (e.g., via a `?test=1` query param hook OR removing the auto-open useEffect).
2. Audit the procurement deep-link redirect logic so `mae@bebang.ph` lands on the requested URL, not /my-tasks.

Once those two are resolved, the Iterate-Until-Green loop can resume from this state and likely cascade S194-1 → 25+ scenarios green within 1-2 hours.
