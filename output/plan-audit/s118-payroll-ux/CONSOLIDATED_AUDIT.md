# S118 Audit: Payroll Processing & Remittances UX Hardening
**Date:** 2026-03-25
**Auditor:** Claude Opus 4.6 (direct audit + code verification)

---

## VERDICT: GO with 4 amendments

The plan is well-scoped (18 units), correctly focused, and addresses real operator pain at 500+ employee scale. 4 issues must be fixed before execution.

---

## Findings

### BLOCKER 1: FALSE CLAIM — "Full" column does not exist
**Severity:** WARNING (remove from plan, not a code blocker)
**Issue:** UX-7 says rename "Full" column to "Issues". The actual code at `processing/page.tsx:360` already says `<th>Issue</th>`. There is no "Full" column.
**Fix:** Remove UX-7 from the Requirements Regression Checklist and remove the corresponding Phase 1 task (saves 1 unit).

### BLOCKER 2: Missing `hr-payroll.ts` type update task
**Severity:** CRITICAL
**Issue:** Phase 1 adds `grouped_summary` to the backend `get_processing_blockers` response, but there is NO task to update the `ProcessingBlockers` TypeScript interface in `hr-payroll.ts`. The plan says "extend types only if needed" under Files This Sprint Owns — but it IS needed. Without the type update, the frontend will get `grouped_summary` as `any`, defeating type safety and risking runtime bugs.
**Fix:** Add a task to Phase 1: "Update `ProcessingBlockers` interface in `hr-payroll.ts` to include `grouped_summary: Array<{issue_type: string, message: string, severity: string, count: number}>`." Also add `hr-payroll.ts` to the Files This Sprint Owns list.

### BLOCKER 3: Missing L3 evidence file contract
**Severity:** WARNING (closeout integrity)
**Issue:** The Autonomous Execution Contract says "all L3 scenarios pass with real browser interactions" but does NOT name the required evidence files (`output/l3/S118/form_submissions.json`, `api_mutations.json`, `state_verification.json`). Without explicit file paths, the agent can declare PASS without producing evidence. Also missing: `git add -f output/l3/S118/` step for release manager gate.
**Fix:** Add evidence file paths to completion_condition. Add `git add -f` to Phase 3 closeout task.

### BLOCKER 4: Missing governor feedback loop
**Severity:** WARNING (execution governance)
**Issue:** The execution contract doesn't specify how the builder handles REJECT, NEEDS_FIX, Merge Conflict, or Deploy Failure from the governor. For a small UX sprint this is low risk, but the execution skill requires it.
**Fix:** Add standard governor decision table to Autonomous Execution Contract or reference "standard governor protocol per `/execute-plan-bei-erp`".

---

## Non-Blocking Findings

### INFO 1: Loading state for grouped view
The current page uses `<Skeleton>` for the entire readiness card. After replacing with grouped cards + expandable lists, the loading state should show skeleton group cards (not one big block). This is cosmetic — not a blocker.

### INFO 2: S117 overlap is low risk
S117 touches command center files (`payroll/page.tsx`, `current-cutoff/page.tsx`). S118 touches processing + remittances. No file overlap. The plan correctly identifies this and says "rebase and continue."

### INFO 3: Phase 1 is at 8 units — budget OK
Even after removing UX-7 (1 unit), Phase 1 stays at 7 units. Adding the hr-payroll.ts type task brings it back to 8. Within budget.

---

## Required Plan Amendments

```
1. Remove UX-7 from Requirements Regression Checklist (column is already "Issue")
2. Remove Phase 1 task "Fix the 'Full' column header" (false premise)
3. Add Phase 1 task: "Update ProcessingBlockers interface in hr-payroll.ts
   with grouped_summary field" (1u)
4. Add to Files This Sprint Owns: hr-payroll.ts (extend types)
5. Add to completion_condition:
   - output/l3/S118/form_submissions.json exists
   - output/l3/S118/api_mutations.json exists
   - output/l3/S118/state_verification.json exists
   - git add -f output/l3/S118/ && git push
6. Add governor feedback loop reference to Autonomous Execution Contract
```

---

## GO/NO-GO: **GO** after amendments applied
