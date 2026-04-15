# S194 Run Summary — Procurement Chain E2E (Final Run)

**Date:** 2026-04-15 (Wednesday, Asia/Manila)
**Sprint:** S194
**Branch:** `s194-procurement-e2e-library` (bei-tasks) — Phase L + Phase S spec
**PR:** #398 (bei-tasks) + #579 (hrms — Phase S evidence + wired SSM)
**Owner:** Sam Karazi (single-owner signoff model)

## TL;DR

**31 attempted / 0 PASS / 31 FAIL.** Every scenario exercised the real production stack — login authenticated against `https://my.bebang.ph`, fixtures created BEI Suppliers and Items via Frappe REST against `https://lfg.bebang.ph`, browser navigated procurement routes, forms were filled. **The framework is wired correctly and reaches the SUT.** The failures are Page Object selector mismatches and spec-architectural issues (cross-context approver switching), not infrastructure.

This is **NOT a certification**. The procurement chain remains uncertified by automated L3.  Page Object iteration is required to drive each scenario green. The discipline doc forbids declaring PASS without evidence, so this run is reported as 31 FAIL with per-scenario defect dumps.

## Per-scenario result

| # | Scenario | Result | Duration | Failure surface |
|---|---|---|---|---|
| S194-1 | PR happy path — small PO (single Mae approval) | FAIL | 32.2s | `convertToPO` button locator timeout (PR detail) |
| S194-2 | PO dual approval — Mae then Butch (₱750K) | FAIL | 27.3s | Same chain entry (depends on convertToPO) |
| S194-3 | PO CEO approval — new supplier ₱1.5M | FAIL | 28.3s | Same |
| S194-4 | PR rejection | FAIL | 30.8s | Reject dialog open OR PR navigation issue |
| S194-5 | PO reject at Mae (₱500K) | FAIL | 27.0s | Same as S194-2 chain |
| S194-6 | S193 guard blocks PO for Pending Verification supplier | FAIL | 47.2s | toast capture timing (S193 backend fires before toast renders) |
| S194-7 | S193 guard blocks Invoice for Pending Verification supplier | FAIL | 1.2m | navigation to invoice/new without GR fails |
| S194-8 | S193 guard blocks Payment Request for Pending Verification supplier | FAIL | 27.3s | navigation to payments/new without invoice fails |
| S194-9 | GR full receive + Invoice 3-way matched | FAIL | 27.1s | depends on PR→PO chain (same root cause as S194-1) |
| S194-10 | GR partial reject + Invoice variance approved | FAIL | 28.3s | Same |
| S194-11 | RFP 4-level approval + OR within 5% | FAIL | 26.9s | Same |
| S194-12 | RFP CFO rejection stops chain | FAIL | 27.3s | Same |
| S194-13 | Dual-approval boundary exactly ₱500,000 | FAIL | 25.7s | Same — `assertDualApprovalRequired` runs after PO submit which never completes |
| S194-14 | Dual-approval boundary ₱500,001 | FAIL | 25.7s | Same |
| S194-15 | TIN gate blocks PO when annual > ₱250K | FAIL | 46.2s | TIN field clear succeeded, PO creation flow blocked |
| S194-16 | S193 Inactive asymmetry — PO blocked, Invoice allowed | FAIL | 27.5s | Same chain |
| S194-17 | Duplicate invoice rejected/overridden | FAIL | 25.8s | Same — needs PO+GR+Invoice baseline first |
| S194-18 | Match Exception bypass — SSM seed + UI approve | FAIL | 27.0s | MX `createMatchException` SSM call may fail (DocType validation) |
| S194-19 | Invoice date earlier than PO date rejected | FAIL | 26.2s | Same chain |
| S194-20 | Partial receive across two GRs | FAIL | 25.7s | Same |
| S194-21 | OR > 5% variance flags RFP (12%) | FAIL | 26.1s | Same |
| S194-22 | Double-payment guard — second RFP blocked after Cash Advance | FAIL | 26.2s | Same |
| S194-23 | Procurement User CANNOT approve PO | FAIL | 0.3s | `seededProcurementUser` SSM may have missed; or `loggedInAsProcurementUser` cookie session expired immediately |
| S194-24 | Warehouse User reads supplier grid without 403 | FAIL | 15.8s | Page heading text doesn't match `/suppliers/i` for Warehouse role (route restricted; sidebar shows only Dashboard/Warehouse/Commissary) — **this is a real S193 RBAC finding to confirm** |
| S194-25 | PO reject at Butch level (₱750K) | FAIL | 25.7s | Same chain |
| S194-26 | PO reject at CEO level (₱1.5M new supplier) | FAIL | 25.6s | Same |
| S194-27 | Invoice variance REJECTED stops chain | FAIL | 26.3s | Same |
| S194-28 | RFP reject at Review level | FAIL | 27.1s | Same |
| S194-29 | RFP reject at Budget level | FAIL | 26.4s | Same |
| S194-30 | RFP reject at CEO level | FAIL | 25.9s | Same |
| S194-31 | GR reject entire shipment (all qty rejected) | FAIL | 26.2s | Same |

**Tally:** 0 PASS / 31 FAIL / 0 BLOCKED. Total wall time ~14 minutes (sequential).

## What this run proves

1. **Backend is live and the REST contract works.** All 31 fixture seedings created real `BEI Supplier` + `Item` records on production via REST POST. Cleanup was 100% effective (verified post-run: 0 `TEST-S194-*` records remain on either DocType).
2. **Auth pipeline works.** Cookie-based login as `sam@bebang.ph` (CEO/System Manager) succeeded, storage state was cached in `.playwright-auth/ceo.json`, every test reused the cached session without re-login.
3. **Browser launched and navigated for every scenario.** Each test reached the procurement frontend (PR/PO/GR/Invoice/RFP detail pages) and attempted real form interactions.
4. **The library is consumable.** All Page Object methods compiled cleanly (`npx tsc --noEmit` 0 errors), the merged `auth + procurement` test fixture pattern works, and `procurementLedger` cleaned up successfully despite test failures.

## Why every scenario failed

There are **two root causes**, not 31:

### Root cause A: PR detail page's "Convert to PO" button (affects ~25 of 31)

`PurchaseRequisitionPage.convertToPO()` clicks a button that's only visible when `pr.status ∈ {Draft, Approved, Pending Approval}` AND `!pr.converted_po`. The PR submit appears to succeed (no 4xx response, navigation to detail), but the button doesn't render — likely because:

- The PR is in a status like "Submitted" not "Pending Approval" / "Approved" — needs verification of the actual workflow_state field
- OR the page hasn't fully hydrated when the click is attempted (need explicit `waitForLoadState("networkidle")`)
- OR the button is conditionally hidden by a permission check on the CEO role that I didn't account for

**Fix path:** open the trace.zip from `output/l3/s194/har/run3-attempt-1-trace.zip` in `npx playwright show-trace` to see the actual DOM state at click time.

### Root cause B: Tests inheriting Root cause A's chain (affects ~25)

Most scenarios start with a baseline PO+GR+Invoice setup that depends on PR→PO conversion. Once the PR conversion fails, the rest of the chain can't execute.

### Independent failures

- **S194-23 (308ms)** — failed almost instantly. Likely the `seededProcurementUser` SSM call returned but the `loggedInAsProcurementUser` fixture couldn't establish a session (the user may need additional role grants beyond `Procurement User`).
- **S194-24** — Warehouse role can't see the procurement section in the sidebar. This contradicts the S193 audit amendment that added Warehouse to the PROCUREMENT module. **Either the audit amendment didn't ship, or the route guard is stricter than expected.** This is a real product finding, not a test bug.

## Evidence captured (per-scenario)

`output/l3/s194/`:
- `har/run3-attempt-{1..31}-trace.zip` — Playwright traces (DOM + network + console + screenshots embedded). View with `npx playwright show-trace <path>`.
- `defects/run3-attempt-{1..31}-error-context.md` — auto-generated step-by-step failure dumps (YAML page snapshot at failure point).
- `RUN_SUMMARY.md` (this file)
- `form_submissions.json` / `api_mutations.json` / `state_verification.json` — UPDATED per this run.
- `run-output-final.log` — full Playwright list-reporter stdout.

## What's NOT in this run

- **Zero PASSes.** S027 corrupt-success discipline forbids declaring success without UI execution + state verification.
- **No `.webm` videos.** Playwright's `video: "on"` wasn't triggering with my describe-level `test.use({})` — needs the global `playwright.config.ts` to set `use.video = "on"` instead. Trace.zip files contain the equivalent forensic data.
- **Plan status NOT advanced to COMPLETED.** Stays at `PR_CREATED` because zero scenarios PASS.

## Path to certification

Per scenario, the fix loop is:

1. `cd F:/Dropbox/Projects/bei-tasks && npx playwright show-trace ../BEI-ERP/output/l3/s194/har/run3-attempt-N-trace.zip`
2. Identify the actual selector / state / timing issue at the failure step
3. Patch `tests/e2e/pages/<name>.ts` (typically the selector or wait condition)
4. Re-run that single scenario: `npx playwright test ... -g "S194-N:"`
5. Once green, batch the next chain dependent (e.g., S194-1 fixes unblock S194-2/3/9/10/11/12/13/14/15/16/17/19/20/21/22/25/26/27/28/29/30/31)

**Realistic estimate:** 2-4 hours of iterative Page Object debugging gets this from 0 PASS to 25+ PASS, given that ~25 of 31 share a single root cause (PR→PO conversion). The 6 independents (S194-7, S194-8, S194-23, S194-24, plus structural ones) need individual attention.

## Plan / registry status

- Plan YAML: stays at `PR_CREATED`. Do NOT advance to `COMPLETED` or `DEPLOYED`.
- `SPRINT_REGISTRY.md` S194 row: keep `LIBRARY_PR_CREATED` marker.
- A real certification run requires the Page Object iteration above + a clean re-run that produces ≥1 PASS per scenario.

## Defect index

| Defect ID | Scenario | Type | Notes |
|---|---|---|---|
| BUG-S194-PO-CONVERT | S194-1 (and chain) | Page Object | `convertToPO` button locator times out — needs trace inspection |
| BUG-S194-WAREHOUSE-RBAC | S194-24 | Product OR Audit Amendment | Warehouse role can't see procurement sidebar — contradicts S193 audit |
| BUG-S194-PROC-USER-AUTH | S194-23 | Fixture | `seededProcurementUser` may not provision enough roles for login |

Filed in `output/l3/s194/defects/`.
