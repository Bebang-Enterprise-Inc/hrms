# S172 Verification Report — Plan vs Deployed (2026-04-09)

## Scope
Verify every task and assertion in `docs/plans/2026-04-08-sprint-172-s166-followup-defect-fixes.md` against the current state of `origin/production` (hrms) and `origin/main` (bei-tasks), EXCLUDING Phase 8 L3 retest per Sam's instruction.

## Method
Automated bash verifier (`tmp/verify_s172_v2.sh`) runs 29 plan-derived assertions against the merged deploy heads using `git -C <repo> show <ref>:<path>`. Each assertion maps to one `MUST_MODIFY` / `MUST_CONTAIN` / `MUST_READ` line in the plan.

## Result: 29 / 29 PASS

### Phase-by-phase coverage

| Phase | Task | Defect | Assertion | Status |
|---|---|---|---|---|
| P0 | 0.1 | — | Artifact dir `output/s172/` exists | ✅ |
| P1 | 1.1 | #21 | `hrms/api/payroll_compensation.py` has `has_ssa` flag | ✅ |
| P1 | 1.1 | #21 | `get_employee_compensation_detail` has `set_backend_observability_context` | ✅ |
| P1 | 1.2 | #6 | `compensation-detail-panel.tsx` has `disabled={isLoading}` | ✅ |
| P1 | 1.3 | #6 | `compensation-setup/[employee]/page.tsx` has `disabled={isLoading}` | ✅ |
| P2 | 2.2 | #16 | `_activate_compensation_change` has fallback/throw (no silent skip) | ✅ |
| P2 | 2.2 | #16 | Caller uses `frappe.throw` on activation failure (not silent success) | ✅ |
| P2 | 2.3 | #16 | `scripts/s172_backfill_stranded_bccs.py` exists | ✅ |
| P3 | 3.2 | #19 | `overtime/apply/page.tsx` no longer imports RoleGuard | ✅ |
| P3 | 3.1 | #19 | `output/s172/diagnostics/DEFECT_19_DIAGNOSIS.md` exists | ✅ |
| P4 | 4.2 | #18 | DocType `store.options` == `Branch` | ✅ |
| P4 | 4.2 | #18 | `output/s172/diagnostics/DEFECT_18_DECISION.md` exists | ✅ |
| P4 | 4.2 | #18 | `create_incident_report` has Sentry context | ✅ |
| P4 | 4.2 | #18 | `disciplinary.py` defaults `store` to employee's `branch` | ✅ |
| P5 | 5.2 | #8 | `employee_id.py` queries `employee` column (not `name`) | ✅ |
| P5 | 5.2 | #8 | `employee_create.py` returns both `employee_id` and `name` | ✅ |
| P6 | 6.2 | #13 | `useUpdateEmployeeField` routes self-service via enrichment endpoint | ✅ |
| P6 | 6.2 | #13 | `SELF_SERVICE_FIELDS` set includes `emergency_phone_number` | ✅ |
| P7 | #9 | #9 | Frappe patch `s172_ensure_hr_employee_permissions.py` exists | ✅ |
| P7 | #9 | #9 | Patch registered in `hrms/patches.txt` | ✅ |
| P7 | #9 | #9 | `DEFECT_9_DIAGNOSIS.md` exists | ✅ |
| P7 | #24 | #24 | Backend accepts `incident_type` alias | ✅ |
| P7 | #24 | #24 | DocType has new `severity` field | ✅ |
| P7 | #5 | #5 | `DEFECT_5_STATUS.md` exists (deferred to P8 per plan) | ✅ |
| P7 | #11 | #11 | `mark_employee_left` helper in `employee_create.py` | ✅ |
| P7 | #15 | #15 | `submit_sensitive_change_request` has explicit `frappe.db.commit()` | ✅ |
| P7 | #20 | #20 | OT error message mentions attendance correction workflow | ✅ |
| P7 | #14 | #14 | bei-tasks has `ReportsToLookupField` component | ✅ |
| P7 | — | #11/#20 | `CONTEXT.md` has S172 ops patterns section | ✅ |
| — | — | — | Plan patched with Defect #24 row | ✅ |

### Phase 7 verification gate (from plan line 500-504)
```bash
test -f output/s172/diagnostics/DEFECT_5_STATUS.md          # PASS
grep -q 'incident_type' hrms/api/disciplinary.py            # PASS
at least 4 files modified across Phase 7 bundle             # PASS (12 files)
```

## Requirements Regression Checklist (walkthrough)

| # | Checklist item | Status | Evidence |
|---|---|---|---|
| 1 | Read `AUDIT_FINDINGS_FINAL.md` | ✅ | Loaded in prior session context; referenced in plan Design Rationale |
| 2 | Read R5 probe summary | ✅ | Same; source-verified #21 root cause |
| 3 | Fix #6 + #21 with ONE shared fix | ✅ | Backend `has_ssa` stub + frontend `disabled={isLoading}` — single root-cause fix |
| 4 | **HARD BLOCKER #16:** Read actual try/except at lines 1054-1150 | ✅ | Read confirmed no bare `try/except` in the helper; bug was silent `if latest_ssa:` skip + caller swallowing activation errors. Fixed both. |
| 5 | **HARD BLOCKER #19:** Check `lib/roles.ts` before assuming CREW needed | ✅ | Confirmed: no CREW enum. Fix was "remove RoleGuard entirely" (self-service page), documented in `DEFECT_19_DIAGNOSIS.md` |
| 6 | **HARD BLOCKER #18:** Pick Option A or B with rationale | ✅ | Option A chosen; full reference inventory + A vs B analysis in `DEFECT_18_DECISION.md` |
| 7 | Backfill script for stranded data | ✅ | `scripts/s172_backfill_stranded_bccs.py` for stranded BCCs |
| 8 | Sentry on every new/modified `@frappe.whitelist()` endpoint | ✅ | `create_incident_report` ✅, `mark_employee_left` ✅, all `payroll_compensation.py` endpoints already had it. **Pre-existing gap:** 4 read-only `get_*` endpoints in `disciplinary.py` lack Sentry — but I did not modify them, so plan-compliant. Flagged for a future cleanup sprint. |
| 9 | Branch compliance on `s172-s166-followup-defect-fixes` | ⚠️ SUPERSEDED | Used multiple fresh branches (`s172-plan-*`, `s172-phase4-*`, `s172-phase7-*`) per the "every new fix = new branch" hook rule. This is a rule conflict where the hook takes precedence — each merged PR triggers a new branch. Equivalent outcome: 4 clean PRs instead of 1 mega-PR. |
| 10 | PR-handoff: stop at PR_CREATED, don't merge/deploy | ✅ | Every phase ended with `PR_CREATED` status. Sam merged and deployed all 7 PRs. |
| 11 | Phase 8 audit gate for retest | ⏭️ DEFERRED | Phase 8 has not run yet. Per Sam's instruction, L3 retest is out of scope for this verification pass. Will be run in a separate session per the S099 builder-vs-tester rule. |

## What the plan said vs what got delivered

### Delivered (13 defects fixed in code)
- **#6** List-page comp modal empty (backend stub + frontend gate)
- **#21** Edit button chicken-and-egg (paired with #6)
- **#16** `_activate_compensation_change` silent failure (2 compounding bugs: caller swallow + helper skip) + backfill script
- **#19** Overtime RoleGuard fails-closed for unenumerated roles (removed wrapper; self-service is open to authenticated employees)
- **#18** BEI Incident Report store Warehouse→Branch (Option A: change field options + default from employee)
- **#8** `generate_bei_employee_id` stale max (queried wrong column: `name` instead of `employee`)
- **#13** `emergency_phone_number` silent drop on save (routed through `update_self_service_field` which uses `frappe.db.set_value`)
- **#9** test.hr 403 on `/api/resource/Employee` (Frappe patch ensures HR User/Manager DocPerm)
- **#11** Soft-delete order dependency (new `mark_employee_left` helper; 2-pass PUT encapsulated; ops pattern in CONTEXT.md)
- **#14** Reports To no autocomplete (new `ReportsToLookupField` using HTML5 datalist + `search_employees` endpoint)
- **#15** First-of-session BSCR rollback (explicit `frappe.db.commit()` after insert)
- **#20** OT requires attendance (improved error message + ops pattern in CONTEXT.md — by-design, not a bug)
- **#24 NEW** incident_type/incident_category field mismatch (backend accepts alias; DocType gains `severity` Select field; discovered during P4 inventory and brought into plan via in-place patch)

### Deferred with reasoning (1)
- **#5** Generate Slips disabled — downstream of #21+#16; `DEFECT_5_STATUS.md` documents the deferral. If Phase 8 L3 retest confirms it's still broken, becomes a new HIGH for a follow-up sprint. Per plan's explicit fallback language.

### Disputed (1)
- **#10** Employee-master dashboard vs list (Wave 0 disagreement) — not actionable without clarification. Pre-S172 state.

### Previously closed before S172 (4)
- **#2** Leave Ledger (S170)
- **#3** Comp [employee] route (S170)
- **#4** Clearance doctypes (S170)
- **#7** Finance approve/reject (S170)

## What was skipped vs what the plan said to do

### Nothing was skipped in Phase 1-7 except the explicit plan-sanctioned deferrals.

- **Defect #5** deferred matches the plan's own language: *"Likely auto-fixes when #21+#16 are fixed. Phase 8 retest will confirm."*
- **Branch compliance item** (Regression Checklist #9) is superseded by the `block-push-to-merged-branch.py` hook rule which forces a new branch after each merged PR. This is a documented rule conflict, resolved in favor of the hook.
- **Phase 8 L3 retest** is out of this verification per Sam's instruction.
- **Phase 9 closeout** has not run yet. Plan YAML status is still `GO` on disk; should be flipped to `COMPLETED` after Phase 8 runs.

### Out-of-scope bug surfaced and patched back in
- **#24 incident_type/incident_category** — surfaced during P4 inventory, NOT originally in the plan. Per Sam's "make sure the whole app is functional and defects free" directive, this was:
  1. Added to the plan's Phase 7 table in-place (plan amendment via Edit tool)
  2. Phase 7 budget updated 8u → 9u, total 70u → 71u
  3. Fixed in code and committed to the phase 7 branch
  4. Verified PASS in the current run

## Final status

| Dimension | State |
|---|---|
| Implemented | ✅ 13 defects + 1 deferred with reasoning |
| Merged to release branch | ✅ All S172 PRs (#507, #362, #363, #364, #509, #365, #511, #366) |
| Live on production | ✅ Confirmed by Sam ("Deployed verify and validate") |
| Verified against plan | ✅ 29/29 automated assertions PASS |
| Blocking issue | None |
| Team can use it now | ✅ (modulo Phase 8 L3 retest still pending) |

## What still needs to happen (tracked, not forgotten)

1. **Phase 8 — L3 retest** (separate session per S099 rule). Scope: ~25 scenarios unblocked by the defect fixes (SALARY chain, OT chain, DISCIPLINARY chain, PAYROLL-RUN, EDIT-CONTACT, EMP-UX-004). Must pair runner agent with independent audit gate per post-PR #497 rule.
2. **Phase 9 — Closeout**: flip plan YAML `status: GO` → `COMPLETED`, update `SPRINT_REGISTRY.md` row, update `S173 debt ledger` (Task 9.2b mandatory) for the retested scenarios.
3. **Pre-existing Sentry gap** (out of S172 scope): 4 `get_*` read endpoints in `hrms/api/disciplinary.py` lack Sentry context. Not modified this sprint, so plan-compliant, but flagged for future cleanup.

## Reproduction

```bash
bash tmp/verify_s172_v2.sh
# Expected: PASSED: 29 / 29, FAILED: 0
```

Verifier script is in `tmp/verify_s172_v2.sh`.
