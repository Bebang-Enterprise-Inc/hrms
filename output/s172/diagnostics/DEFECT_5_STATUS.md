# Defect #5 — Generate Slips button disabled on payroll processing

## Plan hypothesis
"Likely auto-fixes when #21+#16 are fixed (button gates on having salary structures in place). Phase 8 retest will confirm."

## Analysis

Defects #21 and #16 were fixed in PR #507 (S172 Phase 1+2) and deployed. Both addressed the root cause: employees without a prior Salary Structure Assignment couldn't have salary activated through the compensation workflow, so the Generate Slips button's gate ("has at least one employee with an SSA") failed for any payroll period that included new hires.

With #21 (stub returned for no-SSA case + Edit button enabled) and #16 (activation no longer silently fails, fallback to default structure for new hires), new hires can now get a real SSA via the HR compensation workflow. Once HR completes the compensation approval flow for even one employee per period, the Generate Slips gate should clear.

## Phase 8 retest owns the verification

This defect cannot be independently verified without running the full payroll-processing L3 scenario against the post-deploy backend. The retest scenario is:

1. Fresh test employee with no SSA
2. HR approves a Salary compensation change (goes through the fixed activation path)
3. Navigate to `/dashboard/hr/payroll/processing`
4. Select the current cutoff period
5. Generate Slips button should be enabled; clicking should produce a slip for the new employee

If the button is still disabled after this sequence, the gate condition is in `../bei-tasks/app/dashboard/hr/payroll/processing/page.tsx` and needs a separate investigation. Flagging as "likely fixed, Phase 8 retest will confirm" rather than re-implementing a gate fix that may not be necessary.

## Status
**DEFERRED TO PHASE 8 RETEST** — no code change in Phase 7. If the L3 retest shows the button is still disabled, this becomes a new HIGH defect for a follow-up sprint.
