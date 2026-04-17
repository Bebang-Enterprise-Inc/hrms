# S201 Audit — Verified Blocker Report

**Plan:** `docs/plans/2026-04-17-sprint-201-per-store-employee-billing-foundation.md`
**PR:** #603 MERGED (2026-04-16T23:22 UTC) + #604 follow-up (BGC fix)
**Audit date:** 2026-04-17
**Auditors:** 5 parallel domain agents + code verifier (read actual source).

## Raw counts (pre-verification)

| Domain | CRITICAL | WARNING | INFO |
|---|---|---|---|
| Frappe backend | 0 | 5 | 4 |
| PH Finance | 5 | 5 | 1 |
| Deployment QA | 4 | 6 | 3 |
| Cross-cutting | 5 | 17 | 7 |
| System architecture | 3 | 9 | 1 |
| **Total** | **17** | **42** | **16** |

## Verified counts (post code-verifier)

- CONFIRMED: 7 CRITICAL, 18 WARNING
- STALE (false positive): 0 CRITICAL, 2 WARNING
- NEW GAPS (code verifier): 0 CRITICAL, 5 WARNING

## Top 10 Verified Blockers

### GROUP A — Policy decisions Sam must make BEFORE running `S201_APPLY=1`

#### B1 [CRITICAL] SSS/PhilHealth/HDMF 49 employer registrations
**Status:** CONFIRMED (plan omission, not code bug)
**Evidence:** Plan has zero language on statutory employer registration per child Company. S188 created 49 child Companies each with its own `branch_tin` and `bir_rdo_code`. Backfill sets `Employee.company = <store-child>` but SSS/PhilHealth/HDMF employer IDs are typically ONE per legal entity.
**Decision needed:** Are 49 separate SSS/PhilHealth/HDMF employer accounts already registered? If not, backfill makes remittance filings ambiguous.

#### B2 [CRITICAL] BIR Form 2316 dual-employer mid-year handling
**Status:** CONFIRMED (plan omission)
**Evidence:** When Employee.company changes mid-year, BIR considers this "multiple employers" — affects 2316 issuance, potentially requires 1905.
**Decision needed:** Confirm with Finance that child Companies issue 2316 as "same employer group" under BEI HoldCo, or prepare 1905 batch filings.

#### B3 [CRITICAL] April 2026 Draft/Submitted Salary Slips stay on parent
**Status:** CONFIRMED
**Evidence:** Backfill patch UPDATEs tabEmployee.company but doesn't touch existing Salary Slip records. Any April 1-16 cutoff slip already posted sits on BEI parent forever.
**Decision needed:** Cancel + regenerate April 2026 cutoff slips after backfill? Or accept the discontinuity starting May 2026?

#### B4 [CRITICAL] April 1-16 split-month risk
**Status:** CONFIRMED (LD-6 says April 01 start but doesn't define behavior if backfill runs mid-period)
**Evidence:** If Sam runs `S201_APPLY=1` on April 18, half the April cutoff is pre-backfill (BEI parent) and half is post (store child). Labor cost per store P&L will have a 50% gap.
**Decision needed:** Wait for next payroll cutoff (April 30 → May 1) to apply, OR apply now and regenerate slips?

### GROUP B — Code bugs (follow-up PR)

#### B5 [CRITICAL → FIX REQUIRED] S201_APPLY env var doesn't propagate through docker exec
**Status:** CONFIRMED
**Evidence:** `.github/workflows/build-and-deploy.yml:388` runs `docker exec $BACKEND_CONTAINER bench ... migrate` with no `-e S201_APPLY=1`. The env var set in host shell never reaches the container.
**Fix:** Sam must run `docker exec -e S201_APPLY=1 $BACKEND_CONTAINER bench --site hq.bebang.ph execute hrms.patches.v16_0.s201_rename_branches.execute`. Update plan + PR body to show correct syntax. (Requires separate invocation — NOT part of normal `bench migrate` flow.)

#### B6 [WARNING → FIX REQUIRED] Company.on_update does NOT call company_lookup.clear_cache
**Status:** NEW GAP (not caught by domain agents; code verifier found)
**Evidence:** `hrms/hooks.py` registers `sales_location_mapping.clear_cache` on Company.on_update (S200) but NOT `company_lookup.clear_cache` (S201). Plan claims both Branch and Company invalidate the resolver.
**Fix:** Add `hrms.utils.company_lookup.clear_cache` to Company.on_update list.

#### B7 [WARNING → FIX REQUIRED] Backfill commits on partial errors
**Status:** CONFIRMED + NEW GAP
**Evidence:** Both `s201_rename_branches.py` and `s201_backfill_employee_company.py` call `frappe.db.commit()` after the loop unconditionally — even when `errors[]` is non-empty. Partial batch commits silently.
**Fix:** If errors exist, rollback savepoint or skip commit + log loudly.

#### B8 [WARNING → FIX REQUIRED] Patches use logger.error (no Sentry capture)
**Status:** NEW GAP
**Evidence:** Both patches call `frappe.logger().error(...)` on failure — server log only, NOT fed to Sentry. `frappe.log_error(title, message)` is the Sentry pathway (per DM-7).
**Fix:** Replace `frappe.logger().error()` with `frappe.log_error(title="S201 patch failure", message=...)`.

#### B9 [CRITICAL → AMENDMENT] Commissary classification split across two modules
**Status:** CONFIRMED (code works correctly, plan description is misleading)
**Evidence:** Plan Phase 4 task says "department == Commissary → BKI". Actual code: `is_non_store_billing` runs FIRST (no BKI logic), then `resolve_branch_to_company` handles commissary via branch suffix + dept. Result: dept=Commissary + branch=SHAW COMMISSARY - LOGISTICS → BEI parent (correct per Sam's SCM rule), but plan text suggests dept alone routes to BKI.
**Fix:** Update plan Phase 4 task to accurately describe the two-stage rule.

#### B10 [CRITICAL → DOCUMENT ONLY] HR Manager override is dead code
**Status:** CONFIRMED
**Evidence:** `company_manual_override` flag exists in exactly 2 lines of `employee_master.py` (read, never set). No Form JS, no Custom Field, no API sets it.
**Options:** (a) Leave as-is — override may not be needed in practice; (b) Remove dead code; (c) Wire a real override via Custom Field + Form JS.
**Recommendation:** Leave as-is for S201 (no employee needs it today); wire when a real override case arises.

### GROUP C — Plan-integrity amendments (not blocking apply, but add rigor)

#### B11 [WARNING] S154 Zero-Skip enforcement section missing
**Fix:** Add explicit "PHASE N DONE" gate requiring each phase's Verification step to pass before advancing.

#### B12 [WARNING] S154 no MUST_MODIFY / MUST_CONTAIN assertions
**Fix:** Add inline file-level assertions per phase task.

#### B13 [WARNING] S087 no protected surfaces list
**Fix:** Name `roving_employees.py`, existing `Employee.validate` BEI-EMP preservation, and Transfer DocType stock fields as DO-NOT-TOUCH.

#### B14 [WARNING] L3 Playwright script does not exist
**Fix:** Author `tests/playwright/s201/*.spec.ts` covering the 6 L3 scenarios OR document that L3 runs via manual Python scripts against Frappe API.

#### B15 [CRITICAL] S202 slippage = roving mis-allocation exposure
**Fix:** Set a maximum tolerable gap (e.g., "S202 must ship before May 15 payroll cutoff or Sam must accept April-May roving labor on home store"). Plan must cite a date.

## Action matrix

| Blocker | Action | Owner | Timing |
|---|---|---|---|
| B1-B4 (PH Finance) | Finance sign-off | Sam + Denise | Before `S201_APPLY=1` |
| B5 (docker exec syntax) | Plan amendment + PR body | Me | Now |
| B6 (Company.on_update) | Code fix follow-up PR | Me | Now |
| B7 (partial commit) | Code fix follow-up PR | Me | Now |
| B8 (Sentry pathway) | Code fix follow-up PR | Me | Now |
| B9 (Commissary plan description) | Plan amendment | Me | Now |
| B10 (HR Manager dead code) | Note in plan, defer fix | Me | Note now |
| B11-B14 (plan rigor) | Plan amendment (retroactive) | Me | Now |
| B15 (S202 deadline) | Plan amendment cite date | Me | Now |

## What the audit did NOT find

- No DM-1..6 violations (S201 doesn't post GL).
- No S091 cold-start gaps (Design Rationale is present).
- No S099 branch isolation issues (branch reserved, PR created).
- Closeout contract exists (S092 satisfied).
