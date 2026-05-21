# S253 DEFECTS Register

Defects discovered during execution, categorized by Mode (per S253 Failure Response section).

## DEFECT-1 (Mode D) — SM MEGAMALL dispatch UI fails to register

- **Discovered:** Phase 1 (S252 inheritance)
- **Symptom:** DispatchPage 30s timeout after dispatch click on `MAT-MR-2026-01142`. Error message: `dispatch did not register ... (status=Ordered, per_transferred=undefined)`.
- **Production state:** MR remains `status=Ordered, docstatus=1, per_ordered=100, per_received=0`. No Stock Entry created to `to_warehouse=SM MEGAMALL - BEBANG ENTERPRISE INC.` linking back to this MR.
- **Classification:** Mode D — skip from Phase 5 sweep, defer to follow-up sprint.
- **Mode A vs Mode C disambiguation needed:** Requires SSM Error Log access + live retry with frontend traces, both outside S253 scope.
- **Compounded by test bug:** DispatchPage polls non-existent `per_transferred` field on Material Issue MRs (`pages/DispatchPage.ts:172`). This poll branch always reads 0 and never satisfies the success condition; only the parallel `status promotion` check could have caught a working dispatch.
- **S253 impact:** SM MEGAMALL excluded from Phase 5 sweep (5a + 5b together cover 43 of 44 remaining stores; 44th is SM MEGAMALL).
- **Follow-up sprint candidate:** `S256` — "SM MEGAMALL dispatch UI completion investigation + DispatchPage per_transferred bug fix"
- **RCA artifact:** `output/l3/s253/verification/sm_megamall_dispatch_rca.md`

## DEFECT-2 (Mode B — test infrastructure note, no sprint needed inline)

- **Issue:** DispatchPage's `per_transferred` poll branch is structurally broken — that field doesn't exist on `Material Issue` MRs in Frappe v15.
- **Mitigation in S253:** Phase 5 sweep relies on the `status promotion` poll branch (line 178). Working dispatches DO promote status past "Ordered" → "Issued", so the existing test will still pass for healthy stores. Only failure mode (like SM MEGAMALL) trips the timeout.
- **Defer fix to:** S256 (same as DEFECT-1).
- **Action in S253:** No change to DispatchPage. Document in S253 SUMMARY.md as a known test-infra defect.
