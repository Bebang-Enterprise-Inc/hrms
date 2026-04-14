# S194 Run Summary — Procurement Chain E2E

**Date:** 2026-04-14 (Tuesday, Asia/Manila)
**Sprint:** S194
**Branch:** `s194-procurement-e2e-library` (bei-tasks)
**PR:** #398
**Owner:** Sam Karazi (single-owner signoff model)

## TL;DR

Phase L (library) — **SHIPPED + COMPILES CLEAN.**
Phase S (spec) — **WRITTEN, ALL 31 SCENARIOS DECLARED.**
Phase S run — **BLOCKED at login step.** Backend `hq.bebang.ph` / `lfg.bebang.ph` returns HTTP 502. No scenarios produced full-path evidence; framework wiring is proven by the single attempted scenario (S194-24) which reached Playwright browser launch + login attempt before failing at cookie establishment.

**This is NOT a PASS run.** Per S027 corrupt-success guidance, reporting scenarios as PASS without evidence is forbidden. Sam must re-run Phase S after the backend is healthy.

## Per-scenario status

| # | Scenario | Result | Notes |
|---|---|---|---|
| S194-1 | PR happy path (single Mae approval, ₱250K) | NOT_RUN | Depends on seededSupplier/seededItemCatalog SSM |
| S194-2 | PO dual approval ₱750K | NOT_RUN | Same |
| S194-3 | PO CEO approval, new supplier ₱1.5M | NOT_RUN | Same |
| S194-4 | PR rejection | NOT_RUN | Same |
| S194-5 | PO reject at Mae | NOT_RUN | Same |
| S194-6 | S193 guard: PO block for Pending Verification | NOT_RUN | Same |
| S194-7 | S193 guard: Invoice block for Pending Verification | NOT_RUN | Same |
| S194-8 | S193 guard: RFP block for Pending Verification | NOT_RUN | Same |
| S194-9 | GR + Invoice 3-way matched | NOT_RUN | Same |
| S194-10 | GR partial + Invoice variance approved | NOT_RUN | Same |
| S194-11 | RFP 4-level + OR within 5% | NOT_RUN | Same |
| S194-12 | RFP rejection at CFO | NOT_RUN | Same |
| S194-13 | Dual-approval boundary exactly ₱500K | NOT_RUN | Same |
| S194-14 | Dual-approval boundary ₱500,001 | NOT_RUN | Same |
| S194-15 | TIN gate | NOT_RUN | Same |
| S194-16 | S193 Inactive asymmetry | NOT_RUN | Same |
| S194-17 | Duplicate invoice (both roles) | NOT_RUN | Same |
| S194-18 | Match Exception bypass | NOT_RUN | Same + createMatchException SSM |
| S194-19 | Invoice date < PO date | NOT_RUN | Same |
| S194-20 | Partial receive over 2 GRs | NOT_RUN | Same |
| S194-21 | OR 12% variance flagged | NOT_RUN | Same |
| S194-22 | Double-payment guard (Cash Advance) | NOT_RUN | Same |
| S194-23 | Procurement User cannot approve (negative RBAC) | NOT_RUN | Same + seededProcurementUser SSM |
| S194-24 | Warehouse User read-only supplier grid | **BLOCKED** | Playwright reached login, failed at session establishment |
| S194-25 | PO reject at Butch | NOT_RUN | Same as baseline |
| S194-26 | PO reject at CEO | NOT_RUN | Same |
| S194-27 | Invoice variance REJECTED | NOT_RUN | Same |
| S194-28 | RFP reject at Review | NOT_RUN | Same |
| S194-29 | RFP reject at Budget | NOT_RUN | Same |
| S194-30 | RFP reject at CEO | NOT_RUN | Same |
| S194-31 | GR reject entire shipment | NOT_RUN | Same |

**Tally:** 0 PASS / 0 FAIL / 1 BLOCKED / 30 NOT_RUN.

## Environmental blockers

**Backend 502.** Verified via `curl -sS -o /dev/null -w "%{http_code}\n"` against both `https://hq.bebang.ph/api/method/frappe.auth.get_logged_user` and `https://lfg.bebang.ph/api/method/frappe.auth.get_logged_user` — both returned 502. `https://my.bebang.ph/login` itself returned 200 (the Next.js frontend is up) but login POSTs proxy through to the Frappe backend which is unavailable.

**SSM preflight script is REST-based but also 502-blocked.** `scripts/s194_preflight_setup.py` uses the Frappe REST API (authenticated via `FRAPPE_API_KEY` / `FRAPPE_API_SECRET` from Doppler) instead of AWS SSM — cleaner for dev but fails identically when the backend is down. The script is wired correctly; it will succeed once the backend is healthy.

**Auth cookie never set.** S194-24 smoke test launched Chromium, loaded `/login`, filled the email and password fields, clicked Sign in — then the 60-second `expect.poll` for `bei_auth` + `sid` cookies timed out (session.ts:54). Trace archived at `output/l3/s194/har/S194-24-trace.zip` (contains DOM + network + console timeline). Error context at `output/l3/s194/defects/S194-24-error-context.md`.

## What this run proves

1. **Library compiles clean.** `npx tsc --noEmit` returns 0 errors for every file in `tests/e2e/{pages,builders,assertions,fixtures}/*` and for `tests/e2e/specs/s194-procurement-chain.spec.ts`.
2. **Playwright framework is wired correctly.** Browser launched, page navigated, form fills executed, selectors resolved. Failure mode = environmental, not test-code.
3. **Spec declares all 31 scenarios.** `grep -c "^  test(\"S194-" tests/e2e/specs/s194-procurement-chain.spec.ts` returns 31.
4. **Forbidden-pattern gates pass.** No `page.request`, no `fetch()`, no `curl`, no `page.route(...fulfill)`, no `page.locator("button ...")`, no `waitForTimeout`, no `axios`/`got`/`node-fetch` imports. Verified via the verify_phase.sh S grep block.

## What must happen before certification

1. **Backend health restored.** `hq.bebang.ph` Frappe API must answer 200 on `/api/method/frappe.auth.get_logged_user`.
2. **Re-run Phase S.** Fresh agent session invokes:
   ```
   doppler run --project bei-erp --config dev -- npx playwright test tests/e2e/specs/s194-procurement-chain.spec.ts --project=chromium
   ```
   Rationale: the `seededSupplier` / `seededItemCatalog` fixtures call `scripts/s194_preflight_setup.py` which reads `FRAPPE_URL` / `FRAPPE_API_KEY` / `FRAPPE_API_SECRET` from Doppler.
3. **Evidence capture.** The spec is already configured with `test.use({ video: "on", trace: "on" })` — running to completion will auto-produce `.webm` + `.zip` per scenario.
4. **Screenshot count gate.** The spec's Page Object methods call `screenshotStep` at every form-fill / click — running all 31 scenarios should produce ≥5 PNGs each. `verify_phase.sh S` will validate the count before closeout.
5. **State verification.** The `procurementAssertions` module uses `frappeReadback.readDoc` after each UI success; running against a live backend will populate `state_verification.json` automatically (via a closeout post-processor — next to write).

## Evidence artifacts produced this run

| Artifact | Path | Size |
|---|---|---|
| S194-24 trace | `output/l3/s194/har/S194-24-trace.zip` | Playwright trace (inspect via `npx playwright show-trace`) |
| S194-24 error context | `output/l3/s194/defects/S194-24-error-context.md` | Playwright-generated step-by-step failure report |
| form_submissions.json | `output/l3/s194/form_submissions.json` | 1 entry (S194-24, BLOCKED) |
| api_mutations.json | `output/l3/s194/api_mutations.json` | Empty array (no mutations reached backend) |
| state_verification.json | `output/l3/s194/state_verification.json` | Empty array |

## Corrupt-success prevention

Per S027 research (arXiv 2603.03116, LLM procedural shortcut rate 27–78%), this run **explicitly refuses to declare PASS on scenarios that never reached the procurement surface**. The library can compile, the spec can declare, and a single scenario can launch a browser without the run being a certification. A "1 scenario attempted, 0 executed" run is the honest answer.

## Plan status

- Plan YAML: stays at `PR_CREATED` — does NOT advance to `COMPLETED` or `DEPLOYED`.
- `SPRINT_REGISTRY.md` S194 row: keep LIBRARY_PR_CREATED marker + add this RUN_SUMMARY reference.
- Certification to a PASS state requires a second run by a fresh agent session once the backend is healthy.
