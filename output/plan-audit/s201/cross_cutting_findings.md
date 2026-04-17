---
audit_target: S201 Per-Store Employee Billing Foundation
plan_file: docs/plans/2026-04-17-sprint-201-per-store-employee-billing-foundation.md
audited_by: Cross-Cutting Auditor Agent
audit_date: 2026-04-17
rules_checked: [S091, S154-ZeroSkip, S154-PhaseGate, S089, S092-Closeout, S092-CorruptSuccess, S087, S099, S026]
branch_verified: s201-per-store-employee-billing (5 commits ahead of production, 0 behind)
---

# S201 Cross-Cutting Audit Findings

## S091 Cold-Start Self-Containment

- [OK] "Design Rationale (For Cold-Start Agents)" section present at line 87.
- [OK] Option C rejection is explained with specific statutory reason: "PH payroll law (SSS, PhilHealth, Pag-IBIG, BIR 2316) requires one legal employer per period." Sufficient for a cold-start agent to understand without needing external context.
- [OK] Option A vs Option B vs Option C comparison is documented inline. Option A limitation is explicit ("3 days at SM MOA by a Tanza employee still bill to Tanza — insufficient per Sam's ask"). Option B benefit is explicit ("fair per-store P&L without breaking statutory"). Option C rejection is explicit.
- [OK] S201 + S202 split rationale is citable: "Splitting S201 (foundation) + S202 (allocation) avoids the 80-unit single-session ceiling (S089 rule)."
- [OK] Branch rename rationale is citable: "Analytics + Store Ordering + Delivery Schedule all use Company prefix. Keeping a separate branch naming convention creates permanent alias debt."
- [OK] "Why not blank Employee.branch" rationale cites specific downstream consumers: "Branch drives geofence, attendance device selection, and scheduling."
- [WARNING] The rationale section does not cite a specific source file for the statutory single-employer rule. It says "PH payroll law" but does not point to a PH-finance rules file or regulatory reference. A cold-start agent cannot verify this claim without external knowledge. Suggested fix: add `(See: memory/ph-finance-accounting.md or BIR RR 2-98 reference in .claude/rules/frappe-development.md DM-3)`.
- [WARNING] Known limitation: the plan assumes EMPLOYEE_MASTER.csv counts (~80 non-store, ~44 commissary, ~510 store) are approximately correct and uses Phase 0 pre-counts as authoritative baseline. This assumption is stated (line 279) but the consequences of drift are not documented. If the actual Frappe tabEmployee counts diverge significantly from EMPLOYEE_MASTER.csv, the Phase 7 verification thresholds ("expect ~45 on BEI parent") will be wrong and the agent may declare success prematurely.
- [INFO] Locked Decisions table is comprehensive and directly citable. All 7 LDs are present with source attribution (Sam Q1-Q5, Scoping).

## S154 Zero-Skip Enforcement

- [CRITICAL] No explicit "Zero-Skip Enforcement" section in the plan. The plan has a Requirements Regression Checklist (line 72-85) but it is framed as a declaration checklist, not an enforcement mechanism. There is no statement prohibiting the executing agent from skipping any phase or marking a task complete without evidence. The plan does not say: "An agent MUST NOT mark any phase complete without running its Verification step."
- [CRITICAL] Phase completion checklist format is prose checkboxes only. Phases 0-7 each have a bullet list of tasks but there is no standardized "Phase N DONE" gate that an agent must explicitly pass before proceeding to Phase N+1. The Verification sub-sections exist but are not formally gated — they read as advisory rather than mandatory.
- [WARNING] No explicit prohibition of skipping behaviors. Contrast with best-practice plans that include language such as: "NEVER proceed to the next phase if any verification in this phase fails. STOP and report the failure." S201 lacks this language entirely.
- [WARNING] The Phase 7 Verification section lists expected before/after counts ("Before: 541 on BEI parent, 0 on per-store Companies") but does not specify a tolerance or explicit PASS/FAIL criterion. An agent with slightly wrong pre-counts could rationalize a different distribution as correct.
- [INFO] The completion_condition YAML block (lines 16-25) is the closest thing to enforcement — it is machine-readable and enumerates 9 required conditions. However, it is only checked at the very end, not per phase.

## S154 Machine-Verifiable Phase Gate

- [CRITICAL] Tasks do not contain inline MUST_MODIFY assertions naming exact file paths. The plan has a "Files To Be Modified/Created" table (lines 246-262) as a summary, but individual phase tasks do not say "MUST_MODIFY: hrms/api/transfers.py" inline. For a 13-file change plan, an executing agent could modify the wrong file version or miss a file entirely without a per-task MUST_MODIFY contract.
- [CRITICAL] No MUST_CONTAIN assertions for features. For example, Phase 4 requires `derive_company_from_branch` to call `is_non_store_billing()` with a specific rule hierarchy. There is no assertion like: `MUST_CONTAIN: hrms/overrides/employee_master.py::derive_company_from_branch calls is_non_store_billing(doc)`. Verification is "create a test employee and observe" which requires a live bench, not a file-level check.
- [WARNING] Phase 5 Verification is "git diff hrms/api/transfers.py shows new_company computed dynamically" — this is the best verification in the plan (file-level), but it relies on the agent interpreting diff output rather than a script-verified assertion.
- [WARNING] Phase 6 (branch rename patch) and Phase 7 (backfill patch) are bulk-mutation phases with the highest risk of silent partial completion. Neither phase has a script-based verification requirement that runs the patch with --dry-run and asserts specific output (e.g., "dry-run must emit exactly 54 branch rename rows"). The Phase 6 verification is prose: "SELECT DISTINCT branch FROM tabEmployee returns branch names that all match Company prefixes."
- [OK] Phase 0 Verification is partially machine-verifiable: `jq '.[] | select(.company=="Bebang Enterprise Inc.") | .COUNT' output/s201/diagnostics/pre_counts.json` — this is a concrete command with expected output format. Good model for other phases.
- [INFO] The plan is backend-only (no UI). S154 was originally frontend-focused but the MUST_MODIFY/MUST_CONTAIN principle applies equally to backend: Python functions, patch scripts, and unit tests can be verified by file existence and content grep before execution.

## S089 Requirements Drift

- [OK] Requirements Regression Checklist present at lines 72-85 with 9 explicit YES/NO questions.
- [OK] Scope is right-sized: 38u estimated, well within the 80u single-session ceiling.
- [OK] S202 deferral is explicit and justified (reliever allocation JE engine deferred, sprint split rationale citable).
- [WARNING] Only ONE Hard Blocker is marked inline in tasks (Phase 7: "HARD BLOCKER: patch must be --dry-run first. No direct execution without Sam approval"). The other key Sam-approval gates are in the Locked Decisions table (LD-1 through LD-7) but are NOT inlined as HARD BLOCKER annotations in the relevant phases. Specifically:
  - Phase 6 (branch rename) modifies 54+ Branch doctype records and all Employee.branch values. This is a destructive bulk rename but has no inline HARD BLOCKER requiring Sam approval before live execution.
  - Phase 4 (Employee.validate() hook) is a permanent schema behavior change on every employee save — no inline HARD BLOCKER.
- [WARNING] stop_only_for list (YAML lines 26-30) includes "Destructive bulk mutation requires Sam approval" but this is in the YAML header, not inline in Phase 6 tasks where the agent needs the reminder at execution time.
- [INFO] The plan correctly defers the monthly JE reclassification engine to S202 and explicitly labels it as "Out of Scope."
- [INFO] 9 phases (0-7 + 9) in 38u is reasonable; average 4u/phase. Single-session executable.

## S092 Closeout

- [OK] Phase 9 (Closeout) is present at line 228.
- [OK] Plan YAML has `status: GO` field; closeout requires changing it to `COMPLETED`.
- [OK] completion_condition YAML block includes "Plan YAML status=COMPLETED and SPRINT_REGISTRY.md updated."
- [OK] `git add -f` instruction present at line 233 with explicit file paths.
- [OK] Phase 9 includes: S202 row reservation, PR creation, registry update. Closeout sequence is complete.
- [WARNING] Plan YAML has no `completed_date:` field. When status changes to COMPLETED, the date would need to be added manually. Other sprint plans (e.g., S200) include `completed_date` in the YAML. This is a minor inconsistency but could cause registry update confusion.
- [WARNING] Phase 9 `git add -f` line (233) does not include `output/s201/diagnostics/pre_counts.json`, `output/s201/diagnostics/pre_branches.txt`, `output/s201/diagnostics/pre_companies.json`, or `output/s201/diagnostics/classifier_results.csv` — all required diagnostic outputs from Phases 0 and 3. The git add line only covers `docs/plans/*.md output/s201/ output/l3/s201/ hrms/data_seed/branch_*.csv`. The `output/s201/` glob should cover diagnostics, but no explicit listing means these can be silently omitted.
- [INFO] Registry verified: S201 row exists in SPRINT_REGISTRY.md (line 285) with correct branch `s201-per-store-employee-billing`, status `GO`, and PR `TBD`. S202 row already reserved (line 287). Registry is current.

## S092 Anti-Corrupt-Success (L3)

- [OK] "L3 Workflow Scenarios" section present at line 210 with 6 scenarios in a structured table.
- [OK] Evidence file contract is explicit: `form_submissions.json`, `api_mutations.json`, `state_verification.json` in `output/l3/s201/`.
- [OK] Scenarios are concrete: each row specifies Action (what to do in the UI) and Verify (what DB state to confirm via API). L3-1 through L3-5 are well-formed; L3-6 requires salary slip generation and JE confirmation.
- [WARNING] L3 evidence directory `output/l3/s201/` does NOT YET EXIST. The L3 section says "Run these in a fresh Playwright session" but no l3/s201/ directory or files are present. This is expected pre-execution, but confirms L3 has not been run yet. The completion_condition requires L3 evidence before COMPLETED can be declared.
- [WARNING] Plan is 38u — exactly at the threshold where the S092 rule recommends a fresh session for L3. The plan does NOT include an explicit recommendation for L3 to run in a separate session. For 38u plans, this is borderline; the plan should include: "L3 MUST run in a separate Claude session from implementation (context budget)."
- [WARNING] L3-6 (Salary Slip posts to store Company) is the most complex scenario and requires the backfill patch to be applied first. The scenario does not specify: "L3-6 is only runnable AFTER Phase 7 is applied (not dry-run)." An agent running L3 before the live backfill will get a false negative on L3-6.
- [INFO] L3 scenarios cover create (L3-1 to L3-3), transfer (L3-4 to L3-5), and payroll (L3-6) — good coverage of the three main mutation paths.

## S087 Anti-Rewind

- [CRITICAL] No explicit protected surfaces list. The plan has a "Files To Be Modified/Created" table (lines 246-262) which implicitly defines in-scope surfaces, but there is no complementary "DO NOT TOUCH these files" list. Critical protected surfaces not mentioned:
  - `hrms/utils/roving_employees.py` — the plan says "keep ROVING_EMPLOYEES dict for backward compat" but there is no formal protection contract (e.g., "MUST NOT remove any existing bio_id from ROVING_EMPLOYEES dict").
  - `hrms/hr/doctype/employee/employee.py` — if Phase 4 adds to this file rather than using hooks.py override, existing Employee validate logic must not be removed.
  - `hrms/api/transfers.py` — existing transfer logic for non-company fields must remain intact.
- [WARNING] No remote-truth baseline SHA cited. The plan says "base: production" in YAML but does not capture the production HEAD SHA at plan creation time. If the branch drifts or production is updated before S201 merges, there is no recorded baseline to diff against for rewind detection. Best practice: `git log --oneline -1 production` SHA in plan or in `output/s201/diagnostics/`.
- [WARNING] No pre-touch backup contract for existing files. The Rollback Contract (lines 236-244) is execution-level (SQL TRUNCATE + git revert) but does not require a JSON/SQL backup of current tabEmployee.company values BEFORE Phase 7 runs. Compare with S196 which captured `output/s196/state/PRETOUCH_BACKUP.json` before any live mutation.
- [OK] Rollback Contract is present and covers all four mutation phases (4, 5, 6, 7) with specific reversal instructions.
- [OK] S201 is a single-agent plan with no concurrent agent ownership conflicts. Ownership matrix is implicitly satisfied by single-agent scope.
- [INFO] Branch is confirmed 5 commits ahead of production and 0 behind (git local check). Rebase rule is satisfied.

## S099 Branch & PR Isolation

- [OK] Plan YAML `branch: s201-per-store-employee-billing` present at line 4.
- [OK] Branch exists and matches the SPRINT_REGISTRY.md entry exactly.
- [OK] Branch is confirmed in git: `s201-per-store-employee-billing` local + `remotes/origin/s201-per-store-employee-billing` present.
- [OK] S201 branch is 0 commits behind production (verified via local git log). Rebase-before-merge requirement is satisfied at audit time.
- [OK] PR registry update is in completion_condition and Phase 9 closeout.
- [WARNING] A second branch `fix/s201-bgc-regional-area-manager` exists (both local and remote origin) and contains at least one commit (`322c7ea5e fix(S201): classifier catches REGIONAL AREA MANAGER; BGC resolves to BEI parent`). This commit is also present on `s201-per-store-employee-billing` (it appears in the branch log as the HEAD commit). If `fix/s201-bgc-regional-area-manager` was a hotfix that was already merged into the main S201 branch, the branch should be deleted to avoid confusion. If it is a separate ongoing fix, it needs its own PR isolated from S201.
- [WARNING] Plan does not have an explicit "Agent Boot Sequence" section telling the executing agent to `git checkout s201-per-store-employee-billing && git pull origin s201-per-store-employee-billing` before starting work. This is implicit from the branch YAML field but not stated as a mandatory first action.
- [INFO] No merged PRs exist for S201 yet (PR field is TBD in registry). The `block-push-to-merged-branch.py` hook is not yet a risk.

## S026 Shell-Prevention

- [INFO] S201 is backend-only (Python utilities, patches, hooks). `touches_frontend: false` confirmed in YAML. No Ionic Vue or React/Next.js surfaces are created or modified. S026 shell-prevention rules are largely not applicable.
- [WARNING] The plan's Notes section (line 278) states: "Frappe desk Employee form: Company field becomes read-only after Phase 4 hook is live, unless user has HR Manager role." This is a Frappe Desk UI behavior change that is NOT explicitly tested in the L3 scenarios. L3 scenarios test via API (`frappe.client.get_value`) not via Frappe Desk form interaction. If Phase 4 hook incorrectly sets `read_only` on the company field (or if Frappe Desk does not respect validate-hook-set fields as read-only), this becomes a hidden false-affordance: the UI field appears editable but any manual entry is silently overwritten on next save. This is a correctness risk, not a UI shell creation risk.
- [WARNING] Phase 4 includes "HR Manager role bypass: if user has HR Manager role AND company was manually changed in this save, skip derivation." The mechanism for detecting "manually changed in this save" is not specified. In Frappe, `doc.get_doc_before_save()` or `doc.flags` must be used. If implemented incorrectly (e.g., comparing doc.company to derived value AFTER the hook already set it), the bypass will never fire and all HR Manager manual overrides will be silently ignored.
- [INFO] No client-side JS is introduced in S201. The `hrms/public/js/erpnext/company.js` file in the diff is an existing file from earlier sprints, not added by S201.

---

## SUMMARY

| Severity | Count | Items |
|----------|-------|-------|
| CRITICAL | 5 | S154-ZeroSkip: no enforcement section; S154-ZeroSkip: no per-phase completion gate; S154-PhaseGate: no MUST_MODIFY inline in tasks; S154-PhaseGate: no MUST_CONTAIN assertions; S087: no protected surfaces list |
| WARNING | 14 | S091: statutory rule has no source file citation; S091: EMPLOYEE_MASTER count assumption undocumented risk; S154-ZeroSkip: no explicit skip-prohibition language; S154-ZeroSkip: Phase 7 thresholds lack tolerance/PASS-FAIL; S154-PhaseGate: Phase 5 git diff is advisory not scripted; S154-PhaseGate: Phases 6+7 bulk mutations lack script-based assertion; S089: Phase 6 branch rename has no inline HARD BLOCKER; S089: stop_only_for in YAML only, not at Phase 6 task level; S092-Closeout: no completed_date field in YAML; S092-Closeout: git add line may miss specific diagnostic files; S092-CorruptSuccess: L3 directory does not exist yet; S092-CorruptSuccess: no explicit fresh-session recommendation for L3; S092-CorruptSuccess: L3-6 dependency on live Phase 7 not stated; S087: no remote-truth baseline SHA; S087: no pre-touch backup contract before Phase 7 |
| WARNING (continued) | 3 | S099: fix/s201-bgc-regional-area-manager branch may be stale/orphaned; S099: no explicit Agent Boot Sequence; S026: Frappe Desk read-only behavior not L3-tested; S026: HR Manager bypass mechanism unspecified |
| INFO | 7 | S091: Locked Decisions comprehensive; S091: Design Rationale section covers all options; S089: scope right-sized at 38u; S092-Closeout: registry current with S202 reserved; S092-CorruptSuccess: 3 mutation paths covered in L3; S099: branch aligned with registry and 0 behind production; S026: fully backend-only |

**CRITICAL: 5, WARNING: 17, INFO: 7**

### Mandatory Fixes Before Execution

1. **Add Zero-Skip Enforcement section** to plan with explicit language: "NEVER proceed to Phase N+1 unless Phase N Verification has passed and evidence is written to output/s201/."
2. **Add inline MUST_MODIFY assertions** to each phase's task list referencing the exact file paths from the Files table.
3. **Add HARD BLOCKER annotation** to Phase 6 (branch rename) matching Phase 7's existing HARD BLOCKER pattern.
4. **Add pre-touch backup requirement** before Phase 7: capture current tabEmployee.company distribution to `output/s201/diagnostics/PRETOUCH_BACKUP.json`.
5. **Clarify fix/s201-bgc-regional-area-manager branch** — either confirm it is merged into the main S201 branch and delete the remote, or document why it exists as a separate branch.

### Recommended Fixes (Non-Blocking)

6. Add `completed_date:` field to plan YAML.
7. Add source file citation for statutory single-employer rule in Design Rationale.
8. Add explicit L3 fresh-session recommendation for 38u plan.
9. Specify L3-6 prerequisite: "Phase 7 must be live (not dry-run) before L3-6 is executable."
10. Specify HR Manager bypass implementation mechanism (doc.get_doc_before_save pattern).
