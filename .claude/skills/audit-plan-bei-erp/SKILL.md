---
name: audit-plan-bei-erp
description: Multi-domain BEI plan audit. Spawns up to 7 domain agents plus a code-verifier. Auditors analyze plan text; the verifier reads source files to confirm findings, catch shell-risk surfaces, and detect evidence-lock failures such as contradictory operative sections, non-reproducible counts, or missing cited artifacts. Produces a consolidated blocker list and GO/NO-GO amendment. Use whenever auditing or validating any BEI implementation, sprint, or feature plan, especially pages, dashboards, forms, role-based routes, certification runs, user guides, screenshot-heavy plans, or any plan meant to execute, deploy, and close without manual babysitting.
user-invocable: true
---


> **PR-HANDOFF RULE:** Agents NEVER merge PRs or deploy. Create the PR, share the PR number with the user, and STOP. The user handles merge and deploy.

---

## 🟥 CANONICAL STORE / COMPANY MODEL AUDIT GATE (SCOPED — runs FIRST)

Before any of the seven domain checks, run this gate. It has THREE outcomes: PASS, BLOCKER, or SKIPPED-OUT-OF-SCOPE. A plan that doesn't touch store/company master data is NOT burdened by the gate.

### Step 1 — Read the plan's scope declaration

Every plan MUST declare `canonical_scope: in` or `canonical_scope: none` in YAML frontmatter (write-plan skill enforces this).

- If the plan has NO `canonical_scope` field → BLOCKER `CANONICAL_SCOPE_UNDECLARED`. The plan writer didn't make a conscious call. Reject and send back.
- If `canonical_scope: none` → go to Step 2a.
- If `canonical_scope: in` → go to Step 2b.

### Step 2a — Verify the `none` claim

Read the plan body. Does it actually touch any of these?
- `tabCompany`, `tabWarehouse`, `tabCustomer`, `tabSupplier` (INSERT/UPDATE/DELETE/rename/disable)
- Sales Invoice, Purchase Order/Invoice, Material Request, Stock Entry, Journal Entry, Payment Entry, GL Entry creation/mutation
- Chart of Accounts changes on a per-store Company
- Cost Centers tied to per-store Companies
- `resolve_store_buyer_entity`, `resolve_warehouse_company`, `_STORE_TO_CHILD` reads
- `hrms/api/commissary.py`, `warehouse.py`, `store.py`, `company_master.py`, `billing.py`, `procurement.py`, `labor_allocation.py`, `dispatch.py`, `inventory.py`, `commissary_requisition.py`
- `hrms/utils/supply_chain_contracts.py`, `hrms/utils/labor_allocation.py`, `hrms/utils/bei_config.py`
- `hrms/on_demand/s206_seed_intercompany_accounts.py`, `scripts/canonical/`
- S037 register CSV, store→warehouse route rules
- Whitelisted API with `store`/`warehouse`/`company`/`customer`/`supplier` mutation parameters

If the plan DOES touch any of the above → BLOCKER `CANONICAL_SCOPE_MISCLASSIFIED` (scope should be `in`, not `none`). Push the plan back to write-plan for v-next amendment. Confidence score reduces proportionally.

If the plan genuinely doesn't touch any of the above → **PASS SKIPPED-OUT-OF-SCOPE**. Add a one-line note to the audit report (`Canonical Gate: SKIPPED — canonical_scope=none, verified`) and proceed to the seven domain checks.

### Step 2b — Verify the `in` claim carries the full gate

Run the 6 sub-checks below. Each missing item = a distinct BLOCKER.

1. **YAML frontmatter:** `canonical_model_reference: docs/STORE_COMPANY_CANONICAL.md` + `canonical_preflight: required`. Missing → BLOCKER `CANONICAL_REFERENCE_MISSING`.

2. **Canonical Model Preflight section** (before Phase 0) requires running `scripts/verify_canonical_structure.py` before first code change; enumerates the 8 forbidden operations (2nd records, resolver fallbacks, ad-hoc SQL on master, parent-Customer billing, Internal-Customer SI, hard deletes with history, warehouse_name parsing, parallel `store_id`/`branch_code` fields). Missing → BLOCKER `CANONICAL_PREFLIGHT_MISSING`.

3. **Canonical Model Binding section** (before Phase 0) names:
   - What the plan READS (e.g. `Warehouse.company`, `resolve_store_buyer_entity`, Internal Customer lookup)
   - What the plan WRITES (with canonical-safe rationale)
   - What the plan does NOT touch (explicit enumeration: Warehouse, billing Customer, resolver, etc. depending on scope)
   Missing → BLOCKER `CANONICAL_BINDING_MISSING`.

4. **Scope claim enumerates master-data changes.** Every Company / Warehouse / Customer record the plan creates, updates, or disables is listed and mapped to the canonical pattern. If the plan mutates master data without listing records → BLOCKER `CANONICAL_SCOPE_UNCLAIMED`.

5. **Closeout includes canonical verifier rerun.** A closeout phase task runs `scripts/verify_canonical_structure.py` and HARD BLOCKS on any new violation vs preflight baseline. Missing → BLOCKER `CANONICAL_CLOSEOUT_VERIFY_MISSING`.

6. **Red-flag antipattern scan.** If the plan contains ANY of these strings in a non-mitigating context, BLOCKER `CANONICAL_ANTIPATTERN`:
   - "create a Warehouse for <existing store>" (check: does the store already have a canonical Warehouse?)
   - "parent Customer" used as billing destination for a store SI
   - "is_internal_customer" + "Sales Invoice" in the same paragraph (Internal Customers are labor-JE-only)
   - "UPDATE tabCompany" / "UPDATE tabWarehouse" / "UPDATE tabCustomer" SQL
   - "add a new fallback to resolve_store_buyer_entity"
   - "delete_doc ... Customer" / "delete_doc ... Warehouse" / "delete_doc ... Company" on records with transactional history
   - "branch_code" / "store_id" as a new field (we already have per-store Company as SSOT)

If all 6 pass → **PASS GATE**. Continue to the seven domain checks.

**Incident reference:** 2026-04-19 CEO directive after 3 months of sprints (S188, S190, S196, S206) each landed correctly but nobody audited for cumulative master-data drift. Every store ended up with duplicate Warehouses/Customers. Billing silently went to parent. Per-store P&L broke. See `docs/STORE_COMPANY_CANONICAL.md` and PR #638. The scoped gate catches new drift at plan-audit time — cheaper than post-merge cleanup — while not friction-taxing unrelated plans.

---

## Quick Usage

```
/audit-plan-bei-erp <plan-file-path>
/audit-plan-bei-erp <plan-file-path> --amend          # Auto-apply amendments to plan
/audit-plan-bei-erp <plan-file-path> --domain backend # Run single domain only
/audit-plan-bei-erp <plan-file-path> --domain arch    # System architecture only
```

---

## THE #1 RULE: Files, Not Context

> **Every auditor agent writes findings to `output/plan-audit/<plan-slug>/`.**
> The lead reads SUMMARIES only — never raw findings in messages.
> This prevents context window crashes that killed previous audit sessions.

## S026 Shell-Prevention Audit Rule

S026 exposed a recurring failure mode: plans looked complete because routes, tabs, or cards existed, but the actual surfaces were hollow. A route is not readiness. A page is not a feature. A button is not an action unless it is wired.

When the plan touches any operator-facing surface, including React pages, dashboards, forms, modals, tabs, CTAs, sidebar entries, or mobile flows, the audit must check all of the following:

1. Route contract completeness: pathname, file path, owning module, entry path, and allowed roles.
2. CTA wiring completeness: every visible button, link, tab, menu item, and bulk action maps to a real handler/route/mutation or has an explicit disabled reason.
3. Dependency map completeness: API methods, hooks, store state, config, seed/master data, and upstream prerequisites are named.
4. Navigation and RBAC placement: correct sidebar/menu placement, no false-affordance navigation, and no hidden dependency on unauthorized routes.
5. State coverage: loading, empty, error, blocked, and missing-prerequisite states for each surface.
6. Mutation outcome coverage: success, validation failure, partial failure, retry/rollback, and downstream refresh behavior.
7. Mobile interaction definition: responsive layout plus mobile-safe action access for the same workflow.

If these are missing, classify them as shell-risk blockers even if the plan mentions tests elsewhere. Missing tests are not a substitute for missing implementation contracts.

## S027 Autonomous Execution / Closeout Audit Rule

S027 exposed a second recurring failure mode: plans looked technically rich but still stalled because they did not define who could sign off, when the agent was allowed to stop, which files controlled run truth, or whether deploy was part of execution or a separate manual handoff.

When a plan is intended to be executed rather than merely discussed, the audit must check all of the following:

1. **Completion condition defined** — the plan states exactly what must be green or updated before it can be called done.
2. **Stop-only-for contract defined** — the plan narrows pause conditions to explicit cases such as missing access, destructive approval, business-policy decision, or direct overwrite risk.
3. **Deploy handoff is defined** -- if the plan leads to deployable code, either (a) user-mediated deployment via PR creation is specified, or (b) direct deploy with justification is specified. Plans that leave deploy unaddressed or bypass the user (Sam) without justification are blockers.
3a. **Governor feedback loop is defined** -- for user-mediated plans, the plan must specify how the builder handles each user decision: REJECT (read PR comment, fix, push), NEEDS_FIX (apply suggested fix, push), Merge Conflict (rebase against production, resolve, force-push), Deploy Failure (check logs, fix if code issue). Plans that assume the user (Sam) always approves on first attempt are blockers — the builder must have a conflict resolution path.
3b. **Release manager gate is accounted for** -- for deployable sprint plans, the plan must acknowledge that the bei-release-manager gate will block merge unless L3 evidence files are committed to the branch. Plans must include a step to `git add -f output/l3/{sprint}/ && git push` after L3 testing. Plans that omit evidence commitment are blockers — the gate will reject them.
3c. **Confidence threshold is acknowledged** -- plans should note that reviews with confidence < 0.80 pause auto-merge. If the plan's code changes are likely to trigger low-confidence reviews (large diffs, complex refactors), the plan should address this.
4. **Signoff authority model is explicit** — single-owner, department-owner, operator, or external approver is declared; ambiguous approval chains are blockers.
5. **Canonical closeout artifacts are named** — run status, summary, certification report, defect register, signoff artifact, plan status line, and sprint registry (when relevant).
6. **Status reconciliation contract exists** — when counts, blockers, or stage change, all canonical status surfaces are updated in the same work unit.
7. **No fake human dependency** — if the operating model is really single-owner, the plan must not manufacture a department-approval gate that will never be satisfied.

If these are missing, classify them as execution-governance blockers even if the plan has strong technical detail elsewhere.

## S028 Ground-Truth Lock / Normalization Audit Rule

S047 exposed a third recurring failure mode: audits kept finding "new" problems because the plan never reconciled its operative sections after each amendment. The amendment history improved while the real execution surface stayed stale. That is an audit failure mode, not just a writing flaw.

When a plan contains evidence-derived claims, counts, labels, screenshots, contact directories, route inventories, or re-used assets, the audit must check all of the following:

1. **Concrete evidence paths exist** — every cited manifest, report, capture directory, or reference file either exists now or is explicitly marked as a planned output. Missing paths are blockers when the plan claims GO based on them.
2. **Count method is explicit and reproducible** — the plan defines how counts were produced and what is being counted (for example manifest rows vs per-guide assignments vs unique filenames).
3. **Authoritative sections are declared** — the plan says which sections control execution and which sections are history only.
4. **Operative sections are normalized** — if later amendment/history sections contradict the main plan body on counts, labels, tasks, contacts, or sequencing, treat that as a blocker even if the right answer appears somewhere in the file.
5. **No best-guess operator policy** — if the plan allows guessed labels, guessed contacts, or guessed instructions in operator-facing output, treat that as a blocker.
6. **Normalization artifact exists or is required** — plans that claim GO after multiple amendments should carry a reconciliation artifact or an explicit normalization checkpoint.
7. **Phase splits are absorbed into the phase table** — if the audit history says a phase was split for unit-budget reasons, but the operative phase table still shows the unsplit version, treat that as a blocker.

If these are missing, classify them as evidence-integrity blockers even if the plan has strong technical detail elsewhere.

## S087 Anti-Rewind / Concurrent-Run Audit Rule

S086 and S087 exposed a sixth recurring failure mode: plans can look executable while still allowing stale branches, undeclared shared-file edits, or concurrent run collisions to rewind shipped behavior.

When the plan is multi-agent, deployable, or cleanup-capable, the audit must check all of the following:

1. **Exclusive ownership exists** — the plan defines a surface/file ownership matrix with no overlapping file globs for mutating agents and no ambiguous owner for shared high-risk files.
2. **Protected surfaces are named** — adjacent shipped routes, CTAs, APIs, selectors, nav shells, and other surfaces that must stay untouched are enumerated explicitly.
3. **Remote truth baseline exists** — the plan records the current release branch, release-head SHA(s), and the live/source evidence that define the starting truth.
4. **Touched-file routing is fail-closed** — every owned file family maps to required sentinels, live probes, or protected-bundle non-regression checks.
5. **Freshness / reintegration gate exists** — the plan invalidates prior green checks when overlapping upstream files or surfaces moved after the run baseline.
6. **Concurrent-run coordination exists** — the plan defines a claim/release artifact for active runs and treats overlap as a blocker.
7. **Pre-touch backup is mandatory** — shared high-risk mutations, recovery replay, and cleanup/archive steps require same-run no-loss backup first.
8. **Supersession truth is explicit** — the plan says how historical packets/runs are marked stale or historical-only so future agents cannot restore obsolete behavior by accident.
9. **Cleanup preservation is explicit** — archive/delete actions depend on a touch-preservation ledger or equivalent proof that nothing deployable is being lost.

If these are missing, classify them as anti-rewind blockers even if the plan has strong technical detail elsewhere.

## S089 Requirements Drift Audit Rule

S089 proved that well-spec'd plans can still produce wrong implementations when locked decisions are not surfaced where the executing agent will see them, when plans are too large for a single session, and when non-negotiable constraints are buried in referenced documents instead of inline in tasks.

When auditing any execution-oriented plan, check all of the following:

1. **Requirements Regression Checklist exists** — the plan must contain a `## Requirements Regression Checklist` section with yes/no assertions for every locked decision. If the plan references a design document with locked decisions but does not surface those decisions as a regression checklist, classify this as a CRITICAL blocker.
2. **Hard-coded blockers are inline** — every task that has a non-negotiable constraint from a locked decision must show that constraint as a `HARD BLOCKER` inside the task body. If the constraint only appears in a referenced design doc, classify this as a WARNING.
3. **Scope is right-sized** — if the total work units across all phases exceed 80, classify this as a CRITICAL blocker with a recommendation to split into separate plans. If the plan combines two or more logically independent sprints, classify this as a WARNING even if total units are under 80.
4. **No requirement burial** — if the plan references a design document, spot-check at least 5 locked decisions from that document. If any of them would change the executing agent's implementation approach but are not surfaced in the plan body, classify this as a CRITICAL blocker.
5. **Single-session executability** — the plan should be completable by one agent in one session. If the auditor believes the plan would require context that cannot survive a single session (e.g., dozens of locked decisions across multiple referenced documents, or 8+ phases with cross-phase state), flag this as a WARNING with a splitting recommendation.

If these are missing, classify them as requirements-drift blockers. S089 showed that generic audit coverage (architecture, frontend, backend) is not enough — a plan can pass all domain audits and still fail because the executing agent forgot what the user asked for.

---

## S089 Requirements Drift Audit Rule

S089 proved that well-spec'd plans can still produce wrong implementations when locked decisions are not surfaced where the executing agent will see them, when plans are too large for a single session, and when non-negotiable constraints are buried in referenced documents instead of inline in tasks.

When auditing any execution-oriented plan, check all of the following:

1. **Requirements Regression Checklist exists** — the plan must contain a `## Requirements Regression Checklist` section with yes/no assertions for every locked decision. If the plan references a design document with locked decisions but does not surface those decisions as a regression checklist, classify this as a CRITICAL blocker.
2. **Hard-coded blockers are inline** — every task that has a non-negotiable constraint from a locked decision must show that constraint as a `HARD BLOCKER` inside the task body. If the constraint only appears in a referenced design doc, classify this as a WARNING.
3. **Scope is right-sized** — if the total work units across all phases exceed 80, classify this as a CRITICAL blocker with a recommendation to split into separate plans. If the plan combines two or more logically independent sprints, classify this as a WARNING even if total units are under 80.
4. **No requirement burial** — if the plan references a design document, spot-check at least 5 locked decisions from that document. If any of them would change the executing agent's implementation approach but are not surfaced in the plan body, classify this as a CRITICAL blocker.
5. **Single-session executability** — the plan should be completable by one agent in one session. If the auditor believes the plan would require context that cannot survive a single session (e.g., dozens of locked decisions across multiple referenced documents, or 8+ phases with cross-phase state), flag this as a WARNING with a splitting recommendation.

If these are missing, classify them as requirements-drift blockers. S089 showed that generic audit coverage (architecture, frontend, backend) is not enough — a plan can pass all domain audits and still fail because the executing agent forgot what the user asked for.



## S091 Cold-Start Self-Containment Audit Rule

S091 proved that a plan can pass all domain audits, have a regression checklist, and still fail execution because the executing agent lacks design context that was only discussed in conversation. The plan must be a self-contained execution document.

When auditing any execution-oriented plan, check all of the following:

1. **Design Rationale section exists** — the plan must contain a `## Design Rationale (For Cold-Start Agents)` section. If the plan references design documents, prior sprints, or locked decisions but does not explain WHY those decisions were made in terms a cold agent can act on, classify this as a CRITICAL blocker.
2. **No conversation-dependent decisions** — scan the plan for decisions that appear without rationale (e.g., "use atomic writes" without explaining why not SQLite, "Backend A is default" without explaining the cost model). If a cold agent would need to guess WHY a decision was made, classify this as a WARNING.
3. **Trade-offs are documented** — for every architecture choice where alternatives exist (e.g., polling vs webhooks, JSON vs SQLite, CLI vs SDK), the plan must state what was considered and why the chosen option won. If alternatives are not mentioned, the executing agent may silently switch to a "better" approach that violates a design constraint.
4. **Known limitations are explicit** — constraints like "claude --print cannot run nested" or "Agent SDK requires API key" must appear in the plan with source references, not just as implicit assumptions. If a limitation would cause the executing agent to hit a wall and stop, it must be documented.
5. **Rationale claims are fact-checkable** — every factual claim in the Design Rationale must cite a source file path. If claims reference conversations, meetings, or undocumented decisions, classify this as a WARNING.

If these are missing, classify them as cold-start blockers. A plan that only makes sense to the agent that wrote it is not an executable plan.

## S092 Sprint Closeout Audit Rule

S092 proved that agents ship code but never close out the sprint -- the plan file stays at status GO and the registry row is never updated. This makes project tracking unreliable and forces manual cleanup.

When auditing any sprint plan, check all of the following:

1. **Closeout phase exists** -- the plan must have an explicit task or phase that updates the plan YAML metadata to COMPLETED and updates SPRINT_REGISTRY.md. If the plan ends at deploy or merge without a closeout task, classify this as a WARNING.
2. **Plan metadata has updatable fields** -- the plan YAML block must include status, completed_date, and execution_summary fields that the executing agent fills in. If the metadata block has no fields for the agent to update at closeout, classify this as a WARNING.
3. **Registry update is in completion_condition** -- the Autonomous Execution Contract completion_condition must include plan YAML status updated and SPRINT_REGISTRY.md updated. If registry update is not a completion condition, the agent will skip it.
4. **git add -f instruction present** -- since docs/ may be gitignored, the plan must note that git add -f is required for plan/registry commits. Without this, the agent git add silently ignores the files.

If these are missing, classify them as **closeout-integrity blockers**. A plan that does not require its own closure will produce orphaned status GO plans after every sprint.

## S092 Anti-Corrupt-Success Audit Rule

S092 proved that agents declare "COMPLETED" with "21 PASS, 0 FAIL" after only loading pages (L2) without clicking buttons, filling forms, or submitting anything (L3). Research confirms 27-78% of LLM agent "successes" are corrupt — the agent reports green while skipping procedural steps (arXiv 2603.03116).

When auditing any deployable plan, check all of the following:

1. **L3 Scenario Table exists** — the plan must contain a `## L3 Workflow Scenarios` section with concrete form-fill + button-click + state-verify scenarios. If the plan only says "run L3" or "test the workflow" without naming exact inputs, buttons, and expected outcomes, classify this as a CRITICAL blocker. Vague L3 definitions guarantee corrupt success.
2. **Evidence file contract exists** — the plan must require `output/l3/{sprint}/form_submissions.json`, `api_mutations.json`, and `state_verification.json` before closeout. Plans that allow COMPLETED without these files enable the agent to skip L3 entirely.
3. **L3 is not conflated with L2** — if the plan's "L3" section describes page loads, sidebar checks, or screenshot captures but no form submissions or button clicks, classify this as a CRITICAL blocker. That is L2, not L3.
4. **Separate session recommendation for large plans** — plans with >40 work units should recommend running L3 in a fresh agent session. Context exhaustion at the tail of a long session is the #1 cause of L3 shortcuts.

If these are missing, classify them as **corrupt-success blockers**. A plan that does not concretely define L3 scenarios will produce an agent that loads pages and declares victory.

## S229 Test Data Seeding Contract Audit Rule (MANDATORY for All Plans With L3 / Sweep / Browser Tests)

S225 (2026-04-28) proved that agents misdiagnose test failures rooted in missing production data as product bugs and propose to "fix" the system to make tests pass. The CEO had to halt a proposed resolver auto-failover that would have broken BEI's hard store→hub assignment rule. Root cause: the L3 sweep depleted PM001 stock at the assigned hub mid-run, and the plan never owned the seeding/teardown of that test inventory. Plans that ship without a Test Data Seeding Contract guarantee the same misdiagnosis cycle.

When auditing any plan that contains L3 scenarios, sweeps, browser tests, or QA validation, check all of the following:

1. **Test Data Seeding Contract section exists** — the plan must contain a `## Test Data Seeding Contract` section that enumerates every record class the scenarios depend on (items, stock, users, roles, BEI Routes, custom fields, etc.). If missing, classify as a CRITICAL blocker `TEST_DATA_CONTRACT_MISSING`.

2. **Seeding step uses `/frappe-bulk-edits`** — for each missing record class, the plan must name the exact `/frappe-bulk-edits` INSERT_SQL or bulk doc create operation. Plans that say "ensure inventory is sufficient" without naming the seeding mechanism are non-compliant. Classify as CRITICAL blocker `TEST_DATA_SEEDING_VAGUE`.

3. **Teardown step uses `/frappe-bulk-edits`** — every seeded record must have a corresponding teardown step (DELETE_SQL or bulk doc delete) that reverses it. Plans that seed without teardown leave production polluted. Classify as CRITICAL blocker `TEST_DATA_TEARDOWN_MISSING`.

4. **Teardown ledger artifact required** — the plan must require `output/l3/{sprint}/teardown_ledger.json` with `{doctype, name, action, original_values}` per seeded record AND `output/l3/{sprint}/teardown_complete.json` with deletion proof. Without the ledger, teardown verification is impossible. Classify as CRITICAL blocker `TEARDOWN_LEDGER_MISSING`.

5. **Phase 0 boot sequence includes seeding task** — seeding is execution work, not test-infra optional polish. If the plan defers seeding to "test setup" without a Phase 0 task, classify as WARNING `SEEDING_NOT_PHASED`.

6. **Closeout phase includes teardown task** — teardown is execution work, not optional cleanup. If closeout doesn't include the teardown step, classify as CRITICAL blocker `TEARDOWN_NOT_PHASED`.

7. **Forbidden plan patterns** — scan for these antipattern strings and classify each as a CRITICAL blocker:
   - "PRECONDITION_BLOCKED" used as an out for missing data that could be seeded → blocker `SEED_AVOIDANCE_PATTERN`
   - "fallback logic" / "auto-failover" / "default to alternate" proposed in response to test failures rooted in missing data → blocker `SYSTEM_BREAK_TO_PASS_TEST` (this is the S225 antipattern Sam halted)
   - "test data setup is out of scope" or similar deferral → blocker `SEEDING_OUT_OF_SCOPE_PUNT`
   - L3 scenarios that depend on records the plan does not enumerate → blocker `UNENUMERATED_DEPENDENCY`

8. **Reference skill named** — the Test Data Seeding Contract section must explicitly reference `/frappe-bulk-edits` as the mechanism. Plans that propose `bench execute` snippets, ad-hoc Python in `tmp/`, or "manual SCM data entry" instead of `/frappe-bulk-edits` get a WARNING `WRONG_SEEDING_MECHANISM` (use the skill's pipeline; it has savepoint protection and ledger affordances built in).

**How to check quickly:**
- `grep -n "Test Data Seeding Contract\|/frappe-bulk-edits\|teardown_ledger" <plan>` — should return matches for every L3-bearing plan
- `grep -n "PRECONDITION_BLOCKED\|fallback logic\|auto-failover\|out of scope" <plan>` in the test-data context — any match is a flagged antipattern
- Spot-check: pick one scenario in the L3 table; trace whether every record it touches is enumerated in the Test Data Seeding Contract. If not, blocker.

**Severity anchor:** Test Data Seeding Contract blockers are CRITICAL. They cause the S225 misdiagnosis cycle (test failure → product change proposal → CEO halt → wasted sprint). Plans without the contract MUST NOT proceed to execution.

**Incident reference:** S225 sweep (2026-04-28) — 14/49 stores failed because PM001 had 0 actual_qty at the assigned hub. Agent's RCA proposed resolver auto-failover that would have broken the store→hub assignment rule. CEO directive: "DO NOT BREAK THE SYSTEM TRYING TO PASS A TEST. Add test inventory, test users, test data via `/frappe-bulk-edits` if the missing data blocks the test in any way; when done the data should be deleted via `/frappe-bulk-edits`." This rule encodes that directive at audit time.


## S237 Test Employee & Account Numbering Audit Rule (MANDATORY for All Plans That Create Test Data)

S237 (2026-05-05) found 31 L3 test rows in production Frappe `tabEmployee` squatting on real-employee Bio IDs 9001883–9001917. Three weeks after the L3 tests created those rows, S228 imported the New Hires Masterlist — assigning the same Bio IDs to real new hires (CATINDOY 9001893, ESTRELLA 9001903, etc.). All ADMS punches from those Bio IDs were being mis-routed to ghost test rows marked `status=Left`, which would have silently broken payroll attribution for ~31 real employees. Cleanup migrated 6 Active test rows to `3000001..3000006` and NULLed 26 Left test rows. The 9xxxxxx range is now strictly reserved for real employees.

When auditing any plan that creates or references test Employee records, test attendance_device_ids, or test login accounts, check all of the following:

1. **9xxxxxx test Bio ID = CRITICAL blocker.** Scan the plan body for any test Employee row that proposes `attendance_device_id` in `9000000..9999999`. If found, classify as a CRITICAL blocker `TEST_BIO_ID_REAL_RANGE_COLLISION`. Test rows MUST use `3xxxxxx` (`3000001..3999999`).

2. **Test employee_name without TEST/L3 marker = WARNING.** Plans that create test rows with realistic-looking names ("Maria Santos", "Juan Dela Cruz") that could be confused with real employees get a WARNING `TEST_EMPLOYEE_NAME_LOOKS_REAL`. Acceptable patterns: `L3-`, `TEST-`, `L3TEST `, `BROWSERTEST `, `APPROVETEST ` prefix on `employee_name`.

3. **Real branch on test row = WARNING.** Plans that create test rows with `branch` set to real BEI branches (`ARANETA GATEWAY`, `BRITTANY HOTEL`, `ALABANG TOWN CENTER`, etc.) and don't delete the row at closeout get a WARNING `TEST_BRANCH_USES_REAL_LOCATION`. Use `TEST-STORE-BGC` or another `TEST-*` prefix.

4. **Ad-hoc test login email = WARNING.** Plans that create new test User accounts outside the canonical `test.X@bebang.ph` list in `memory/testing-accounts.md` get a WARNING `TEST_LOGIN_NOT_IN_REGISTRY`. The fix is to either reuse a canonical login or update the registry first.

5. **Missing teardown contract for test Employee creation = CRITICAL blocker.** If the plan creates test Employee rows but doesn't declare in its Test Data Seeding Contract that the rows will be DELETED or migrated to `status=Left, attendance_device_id=NULL` at closeout, classify as CRITICAL `TEST_EMPLOYEE_TEARDOWN_MISSING`.

6. **Missing pre-seed pollution audit = WARNING.** Phase 0 should include `SELECT COUNT(*) FROM tabEmployee WHERE attendance_device_id REGEXP '^9[0-9]{6}$' AND (UPPER(employee_name) LIKE '%TEST%' OR UPPER(employee_name) LIKE '%L3%')` and STOP if > 0. If the plan doesn't include this, WARNING `MISSING_PRESEED_POLLUTION_CHECK`.

7. **Forbidden plan patterns** — scan for these antipattern strings; each match is a CRITICAL blocker:
   - "create test Employee with attendance_device_id 9..." → blocker `EXPLICIT_9XXXXXX_TEST_BIO_ID`
   - "INSERT INTO tabEmployee ... attendance_device_id ... 9001..." → blocker (literal SQL violating the rule)
   - "use Bio ID 9XXXXXX for test" → blocker `TEST_BIO_ID_GUIDANCE_VIOLATION`

**How to check quickly:**
- `grep -nE "attendance_device_id.*9[0-9]{6}" <plan>` in any test scenario / seeding section — any match is a flagged collision (unless the plan explicitly references a real-employee enrollment, like S230)
- `grep -nE "(L3-TEST|TEST-|L3TEST |BROWSERTEST |APPROVETEST )" <plan>` — confirm test Employee names use approved prefixes
- Spot-check teardown contract: every test Employee insert traces to a teardown step

**Severity anchor:** S237 blockers are CRITICAL. The S237 incident took 3 weeks to surface (Apr 7 → Apr 28 → May 5) because nothing flagged the test-vs-real Bio ID collision at audit time. Plans that violate this MUST NOT proceed to execution. The fix is mechanical (renumber test Bio IDs to 3xxxxxx) and adds zero work to a properly written test plan.

**Incident reference:** S237 (2026-05-05) — `/adms-bei-erp` enrollment of 3 real new hires (CATINDOY/BONGAY/ESTRELLA) revealed that 2 of their Bio IDs (9001893, 9001903) were already squatted in Frappe by L3 test ghosts from 2026-04-07 and 2026-04-09. Forensic audit found 31 test rows on real-range PINs total. CEO directive: enforce 3xxxxxx test Bio ID range, amend `/l3-v2-bei-erp`, `/write-plan-bei-erp`, `/audit-plan-bei-erp` to prevent recurrence.


## S097 Sentry Observability Audit Rule (Required For All Deployable Plans)

S097 proved that agents can plan, audit, implement, deploy, and close out a sprint without adding any observability instrumentation. The Sentry integration exists but agents never use it unless explicitly mandated.

When auditing any deployable plan, check all of the following:

1. **Sentry instrumentation task exists** -- the plan must include a task to add `set_backend_observability_context()` to every new/modified `@frappe.whitelist()` endpoint. If missing, classify as a CRITICAL blocker.
2. **Module and action parameters specified** -- each instrumentation call must specify `module` (e.g., "warehouse", "commissary") and `action` (e.g., "create_warehouse_receiving"). If the plan says "add Sentry" without specifying these, classify as WARNING.
3. **Correct Sentry project mapping** -- backend changes (`hrms/api/*.py`) must map to project `bei-hrms` (python). Frontend changes (`bei-tasks/app/api/`) must map to project `bei-tasks` (javascript-nextjs). Org: `bebang-enterprise-inc`.
4. **No silent error swallowing** -- if the plan introduces try/except blocks, verify they include `frappe.log_error()` which feeds Sentry via the monkey-patch in `hrms/utils/sentry.py`. Bare `except: pass` is a CRITICAL blocker.
5. **Closeout gate** -- the plan cannot be marked COMPLETED unless Sentry instrumentation is verified. Add this to the completion_condition in the Autonomous Execution Contract.

Reference: `.claude/rules/sentry-observability.md` (DM-7)

If these are missing, classify them as **observability blockers**. A plan that deploys code without Sentry context produces blind spots in production monitoring.


## S099 Branch & PR Isolation Audit Rule (Required For All Sprint Plans)

S099 proved that agents will commit directly to production if the plan does not reserve a branch. Two sprints merged in one PR, making independent rollback impossible.

When auditing any sprint plan, check all of the following:

1. **Plan metadata includes `branch` field** -- the YAML block must have `branch: s{number}-{slug}`. If missing, classify as a CRITICAL blocker.
2. **Branch name matches registry** -- the branch in the plan must match the Branch column in SPRINT_REGISTRY.md. If the registry row has `--` in the Branch column for a GO plan, classify as a CRITICAL blocker.
3. **Branch is unique** -- no other sprint in the registry uses the same branch name. If shared, classify as a CRITICAL blocker.
4. **Agent Boot Sequence includes branch checkout** -- the boot sequence must have `git checkout -b <branch> origin/production` as the FIRST action before code. If missing, classify as a CRITICAL blocker.
5. **Closeout includes PR registry update** -- the closeout/completion_condition must require updating the PR number in the Sprint Registry. If missing, classify as a WARNING.
6. **No direct-to-production pattern** -- if the plan says "commit to production" or omits branch creation entirely, classify as a CRITICAL blocker. Committing to production is FORBIDDEN for sprint work.

If these are missing, classify them as **branch-isolation blockers**. A plan without a reserved branch will produce the S099 incident again.

## Worktree Isolation & Evidence Split Audit Rule (Required For All Execute-Oriented Plans)

Rule source: `.claude/rules/worktree-isolation.md`. Origin: 2026-04-21 three consecutive A7 stops caused by residual state on the shared main checkout.

When auditing any plan that will be executed by an agent, check all of the following:

1. **YAML frontmatter declares `evidence_committed` and `evidence_transient` lists.** Both must be present (may be empty arrays, but must be declared). Missing either → BLOCKER `EVIDENCE_SPLIT_UNDECLARED`.

2. **Transient-looking artifacts are not routed to `output/s<NN>/`.** Scan the plan body for path claims. If the plan writes `sweep_run_*.log`, `probe_*.json`, `traceback_*.txt`, `playwright_trace_*.zip`, `stuck_mr_probe.json`, monitor decision logs, or similarly time-stamped/run-scoped files to `output/s<NN>/` (the tracked tree) — BLOCKER `TRANSIENT_IN_COMMITTED`. They belong in `tmp/s<NN>/`.

3. **L3 / Playwright / sweep / monitor plans don't claim `evidence_transient: []`.** Such plans produce mid-run logs by construction. If the split is empty → BLOCKER `EVIDENCE_SPLIT_FALSE_EMPTY`. The writer is lying or missed it.

4. **Phase 0 boot sequence uses `git worktree add`, not `git checkout -b`.** The plan's first bootable command must spawn a worktree at `F:/Dropbox/Projects/BEI-ERP-<branch-last-segment>` (or the bei-tasks equivalent) from `origin/production` / `origin/main`. A bare `git checkout -b <branch>` in the main checkout → BLOCKER `MAIN_CHECKOUT_POLLUTION`.

5. **Closeout removes the worktree.** The last closeout task must include `git worktree remove <path>` after a clean `git status --short`. Missing → WARNING `WORKTREE_NOT_CLEANED`.

6. **No instruction to `git worktree remove --force` or `rm -rf` the worktree.** Forced removal silently discards uncommitted work. If the plan suggests it → BLOCKER `DESTRUCTIVE_WORKTREE_CLEANUP`.

Severity anchor: blockers 1–4 and 6 block GO. Warning 5 is plan-quality only (execute skill has its own closeout enforcement).

If the plan has `canonical_scope: none` AND `evidence_committed: []` AND `evidence_transient: []` AND is documentation-only (e.g. registry bump, README tweak) — this rule passes trivially. Otherwise run all six checks.

## The 7 Audit Domains

Each domain maps to specific BEI skills and rules. Not every plan needs all 7 — use the routing table in Step 3.

| # | Domain | Key | Skills Used | Severity Anchor |
|---|--------|-----|-------------|-----------------|
| 1 | **Frappe Backend** | `frappe-backend` | `/frappe-expert`, `.claude/rules/frappe-development.md` (DM-1 to DM-6) | DM violations, permission bypass, data corruption |
| 2 | **PH Finance & Compliance** | `ph-finance` | `/ph-finance-accounting`, `/forensic-auditing` | BIR non-compliance, PFRS misstatement |
| 3 | **Frontend Architecture** | `frontend` | `/frappe-external-app`, `/shadcn-react`, `tanstack-query` | Dead controls, false-affordance nav, missing dependency states |
| 4 | **Deployment & QA** | `deployment-qa` | `/deploy-frappe`, `/qa-testing`, `docker-expert` | Missing pre-deploy deps, no build-integrity proof, unsafe rollout, manual deploy bypassing user, missing user handoff point |
| 5 | **Team Orchestration** | `team-orchestration` | `/teammates`, `/write-plan` | Agent >15 units, file ownership conflict, no autonomous stop/continue contract |
| 6 | **System Architecture** | `system-arch` | `/architect-reviewer`, `aws-solution-architect` | Architectural flaws causing failure/data loss |
| 7 | **Design Principles** | `design-review` | `/design-review`, `vercel-react-best-practices` | God objects, circular dependencies |

**The code-verifier (Step 5.5) always runs** regardless of which domains were selected. It is the only agent that reads actual source files.

For detailed checklists per domain, the agent prompt templates in `references/agent-prompts.md` contain the full checklist and output format for each domain.

---

## Execution Protocol

### Step 1: Read the Plan

Read the target plan file completely. Extract: plan name, features/modules, DocTypes, API endpoints, GL accounts, team composition, test cases, and for every operator-facing surface the routes, CTAs, dependencies, blocked states, mobile variants, and prerequisites. Also extract the execution contract: completion condition, stop-only-for clauses, signoff model, deploy ownership, and closeout artifacts. If the plan contains counts, labels, manifests, contact directories, or amendment history, also extract the evidence sources, count method, authoritative sections, cited file paths, and any contradictions between the operative sections and later amendment blocks. If the plan is multi-agent, deployable, or cleanup-capable, also extract the ownership matrix, protected-surface registry, remote-truth baseline, touched-file routing, active-run coordination artifact, pre-touch backup contract, touch-preservation ledger, and supersession model.

### Step 2: Create Output Directory

```bash
mkdir -p output/plan-audit/<plan-slug>/
```

Where `<plan-slug>` is derived from the plan filename (e.g., `procurement`, `commissary-dashboard`).

### Step 3: Determine Which Domains Apply

| Plan Contains | Domains to Run |
|---------------|----------------|
| DocTypes, Python API, hooks.py | `frappe-backend` |
| GL accounts, payments, JVs, tax | `ph-finance` |
| React pages, dashboards, forms | `frontend` |
| Docker deploy, test cases, CI/CD, release sequencing | `deployment-qa` |
| Team composition, agents, waves, autonomous stop/continue rules, signoff ownership | `team-orchestration` |
| Python services, bots, ETL, integrations | `system-arch` |
| Module/component structure, data flow | `design-review` |

Most plans need 5-7 domains. Skip a domain only if the plan genuinely doesn't touch that area.

If the plan is meant to be executed to completion, `deployment-qa` and `team-orchestration` are mandatory even for backend-heavy plans. S027 showed that execution can fail at governance or deploy handoff even when the build details are correct.

If the plan contains any operator-facing surface, the `frontend`, `deployment-qa`, and `design-review` domains are mandatory even when the user asked for a narrower audit. Shell-risk is cross-domain.

### Step 4: Spawn Audit Agents (Parallel, Background)

Read `references/agent-prompts.md` for the full prompt template for each domain.

Spawn up to 7 agents using the Task tool with `run_in_background: true`. Each agent:
- Receives the FULL plan content in its prompt (do NOT tell agents to read files themselves)
- Writes detailed findings to `output/plan-audit/<plan-slug>/<domain>_findings.md`
- Returns a 1-2 sentence summary message (finding counts only)

```
Task tool parameters:
  subagent_type: "general-purpose"
  model: "sonnet"
  run_in_background: true
  name: "<domain>-auditor"
  description: "Audit plan against <domain>"
```

### Step 5: Collect Domain Results

As each domain agent completes:
1. Note the summary (finding counts)
2. Do NOT read the full findings files yet — wait for all agents to complete

**If an agent fails or times out:** Note the failure, continue with remaining agents. Include the failed domain as "NOT AUDITED — agent failure" in the final report. A partial audit is better than no audit.

### Step 5.5: Code Verification (MANDATORY)

Domain agents analyze plan TEXT only — they never check the actual codebase. This causes false positives (bugs already fixed) and missed gaps (incomplete implementations).

After ALL domain agents complete, spawn ONE code-verification agent using the template in `references/agent-prompts.md`. This agent:
1. Reads all `*_findings.md` files from domain agents
2. Reads actual source files (grep, glob, read) to verify each CRITICAL/WARNING claim
3. Checks plan task descriptions against actual implementation state
4. Verifies cited evidence artifacts exist and flags missing paths or placeholder-only paths
5. Re-runs any count method the plan claims to rely on when counts are central to scope or completion
6. Checks whether authoritative sections and amendment/history sections contradict each other
7. Verifies that anti-rewind artifacts, ownership rules, protected surfaces, and touched-file routing are grounded in current source and existing release/preflight mechanics
8. Classifies each finding as **CONFIRMED**, **STALE** (false positive), or **NEW GAP** (missed)
9. Writes results to `output/plan-audit/<plan-slug>/code_verification.md`

### Step 6: Synthesize Consolidated Report

Once all agents AND the code verifier are done:
1. Read all `*_findings.md` files AND `code_verification.md`
2. **Discard STALE findings** — if the code verifier says it's already fixed, drop it
3. **Discard UNVERIFIABLE findings** — if evidence was insufficient, don't include as blockers (mention in notes)
4. **Add NEW GAP findings** — code verifier gaps become blockers
5. De-duplicate across domains, rank by severity: CRITICAL > WARNING > INFO
6. Create Top 10 Blockers list (max — fewer if the plan is small)
7. Prioritize evidence-integrity blockers above generic "needs more testing" notes when the plan's authoritative sections are stale, contradictory, or unsupported by real artifacts
8. Prioritize shell-risk blockers above generic "needs more testing" notes when the plan lacks wiring, dependency, or navigation contracts
9. Prioritize autonomous-execution blockers above generic "monitor closely" notes when the plan lacks stop rules, deploy ownership, signoff authority, or closeout reconciliation contracts
10. Prioritize anti-rewind blockers above generic "merge carefully" notes when the plan lacks exclusive ownership, protected-surface contracts, remote-truth baselines, touched-file routing, or supersession rules
11. Write the blocker list to `output/plan-audit/<plan-slug>/blockers_for_verification.md`

### Step 6.5: Adversarial Fact-Check (MANDATORY)

Audit agents can make logically valid conclusions from incomplete evidence (e.g., searching one repo and concluding "doesn't exist" when the code lives in another). A separate fact-checker with clean context and no inherited bias catches these.

1. Format each blocker as a structured claim in `blockers_for_verification.md`:
```markdown
## BLOCKER 1: {title}
**Claim:** {the specific factual assertion}
**Evidence provided:** {grep output, file:line content, or search scope}
**Source agent:** {which agent made this claim}
```

2. Spawn a **clean-context fact-checker agent** (no parent context contamination):

```
Task tool parameters:
  subagent_type: "general-purpose"
  run_in_background: false
  name: "adversarial-fact-checker"
  description: "Fact-check audit blockers"
```

Use the fact-checker agent prompt from `references/agent-prompts.md` (bottom section). The agent:
- Starts with ZERO inherited context (structural isolation via subprocess)
- Reads the blockers file and ALL source evidence files fresh from disk
- Evaluates each claim adversarially — actively looking for reasons claims might be wrong
- Writes results to `output/plan-audit/<plan-slug>/fact_check_verification.md`

3. Process results per blocker:
   - **SUPPORTED** -> Keep as blocker
   - **PARTIAL** -> Review, potentially downgrade to WARNING
   - **NOT_FOUND** -> Demote to UNVERIFIED (not a blocker)
   - **CONTRADICTED** -> Remove, flag as HALLUCINATION in report
   - **ERROR/UNVERIFIABLE** -> Keep blocker as-is (fail-open)

4. Write final list to `output/plan-audit/<plan-slug>/verified_blockers.md`

**Why agent-based instead of GLM-5 script:** The Agent tool spawns a subprocess with zero parent context — it only knows what we put in the prompt. This provides the same adversarial benefit (independent reviewer with no confirmation bias) without requiring an external API dependency. The agent uses the highest-tier model available in the environment (Opus 4.6 in Claude Code, GPT 5.4 in Codex).

**If agent fails or times out:** Continue with unverified blockers. Add a note: "Fact-check verification unavailable — blockers are unverified. Treat CRITICAL items with extra scrutiny." This is fail-open because a plan audit with unverified blockers is still useful.

### Step 7: Apply Amendments (if `--amend` or user requests)

Read `references/amendment-template.md` for the exact structure. Key rules:
- NEVER inline full findings (hundreds of lines)
- ONLY add blocker summaries with file path references
- Keep amendments under 200 lines
- Add version bump, "AUDIT: N BLOCKERS IDENTIFIED" status, GO/NO-GO gate
- Update authoritative sections in the same edit when a blocker changes counts, labels, tasks, contacts, artifact paths, or sequencing. Do not fix these only in the amendment log.
- For operator-facing surfaces, add pre-flight checks for CTA wiring, dependency map, RBAC/nav placement, empty/error states, and seed/config prerequisites
- For execution-oriented plans, add required amendments for:
  - completion condition
  - stop-only-for policy
  - deploy-inside-execute rule
  - signoff authority model
  - canonical closeout artifacts
  - status reconciliation contract
- For multi-agent or deployable plans, add required amendments for:
  - exclusive surface/file ownership matrix
  - protected-surface registry
  - remote-truth baseline with release-head SHA(s)
  - touched-file routing to required sentinels/live probes
  - same-run pre-touch backup contract
  - active-run coordination artifact
  - supersession map + touch-preservation ledger
- For evidence-heavy plans, add required amendments for:
  - evidence source table or path corrections
  - reproducible count method
  - authoritative-sections declaration
  - normalization checkpoint / artifact
  - no-best-guess operator policy

---

## Domain-Specific Routing (`--domain` flag)

| Flag Value | Domain Run | Use Case |
|------------|-----------|----------|
| `backend` | Frappe Backend only | Python-only changes |
| `finance` | PH Finance only | Accounting treatment review |
| `frontend` | Frontend only | UI-only changes |
| `deploy` | Deployment/QA only | Pre-deployment review |
| `team` | Team Orchestration only | Team composition validation |
| `arch` | System Architecture only | Architecture review for services/bots/ETL |
| `design` | Design Review only | Component structure, anti-patterns |
| `all` (default) | All 7 domains + code verifier | Full audit |

The code-verifier (Step 5.5) runs regardless of which domain is selected.

---

## Reference Files

| File | When to Read |
|------|-------------|
| `references/agent-prompts.md` | Step 4 — contains full prompt template + checklist + output format for all 8 agents |
| `references/amendment-template.md` | Step 7 — exact structure for plan amendments |

---

## S154 Cold-Start Audit Domain (MANDATORY — added to every audit)

Every audit run MUST include a cold-start readiness check. This is NOT optional. It runs alongside the other domain audits.

**The auditor checks:**

1. **Unresolved external dependencies** — find every reference to a database table, API endpoint, file path, or credential. Flag any that are vague ("query Supabase", "use the weather API", "check the cleanroom"). Each must have: exact table/column names, endpoint URL, full file path verified to exist, Doppler key name.

2. **Missing function/code inventory** — find every reference to existing code the plan modifies or depends on. Flag any that don't include line numbers and "DO NOT modify" warnings where appropriate.

3. **Missing frontend specifics** — find every frontend route, component, or page reference. Flag any that don't include: route path, RBAC roles, pattern to follow, which constants.ts/roles.ts entries to update.

4. **Branch state ambiguity** — check if the plan says what's already committed vs pending. A cold-start agent must know where to start.

5. **Cold-start test** — "If an agent with zero context reads only this document, would it make the wrong implementation choice at any point?" Each such point is a BLOCKER.

**Output:** `cold_start_findings.md` in the audit output directory. Severity: any unresolved gap = BLOCKER.

## S154 Zero-Skip Audit Domain (MANDATORY — added to every audit)

Every audit run MUST verify the plan has enforcement mechanisms that prevent task skipping.

**The auditor checks:**

1. **Zero-Skip Enforcement section exists** — the plan must have an explicit section forbidding task skipping with consequences.

2. **Phase completion checklist format defined** — the plan must specify the exact checklist format the executing agent writes after each phase.

3. **PR description gate defined** — the plan must require task-by-task checklist in PR descriptions.

4. **Forbidden behaviors listed** — the plan must explicitly forbid: silent skipping, marking partial as done, deferring, combining tasks and dropping features, happy-path-only implementation.

5. **L3 handoff includes task status** — the L3 prompt must list every task so the tester can verify.

**Output:** `zero_skip_findings.md` in the audit output directory. Missing enforcement = BLOCKER.

---



## S154 Machine-Verifiable Phase Gate Audit Rule (MANDATORY)

S154 proved that prose phase completion checklists enable lying. The executing agent marked 6 tasks as DONE with evidence describing adjacent work (hook/interface changes) rather than the actual file modifications the tasks required. Self-assessment checklists are structurally unreliable because the same agent that did the work grades the work.

When auditing any execution-oriented plan, check all of the following:

1. **MUST_MODIFY assertions exist** -- every task that says 'modify FILE' or '[FIX] FILE' must include a MUST_MODIFY assertion naming the exact file path. If the task description says to modify OrderItemTable.tsx but has no MUST_MODIFY line, classify as a CRITICAL blocker. Without this, the agent can mark the task DONE by modifying an adjacent file (like a hook or interface) instead of the actual target.

2. **MUST_CONTAIN assertions exist** -- every task that adds a visible feature (badge, button, divider, display format) must include at least one MUST_CONTAIN assertion with a string that proves the feature exists in the file. Example: task says 'add Source OOS badge' -> MUST_CONTAIN 'source_oos_alert' in OrderItemTable.tsx. Without this, the agent can pass the data through hooks without rendering it.

3. **Phase gate is script-based, not prose** -- the plan's Zero-Skip Enforcement section must require a verification SCRIPT (Python or shell) that checks git diff + grep, not a prose checklist the agent fills in. If the plan uses a markdown table for phase completion and the agent self-reports status, classify as a WARNING. Prose checklists have a proven 100% lie rate under context pressure (S154: 6/6 incomplete tasks marked DONE).

4. **Verification script runs AFTER phase, not during** -- the plan must require the agent to run the verification script as a separate step after completing all phase tasks, not as part of the implementation. If the verification is embedded in the implementation flow, the agent can skip it under context pressure.

5. **FAIL means fix, not proceed** -- the plan must state that if any verification assertion fails, the agent MUST fix the failing task before starting the next phase. If the plan allows proceeding with failed verifications, classify as a WARNING.

**How to check:**
- Search the plan for 'MUST_MODIFY' -- should appear at least once per task that names a file
- Search the plan for 'MUST_CONTAIN' -- should appear for every UI feature task
- Search the plan for 'verify_phase' or 'verification script' -- should appear in Zero-Skip section
- If the plan has >5 tasks that modify frontend component files (*.tsx) and ZERO MUST_MODIFY assertions, classify as CRITICAL

**Severity:** Missing machine-verifiable gates = CRITICAL blocker. This is not a nice-to-have -- without it, the plan will produce corrupt success on 27-78% of tasks (arXiv 2603.03116, confirmed by S154 at 6/11 = 55%).

**Incident reference:** S154 Phase 5 (2026-04-02). Tasks F5-F9 required modifying 4 component files (OrderItemTable.tsx, OrderItemCard.tsx, OrderSummaryStrip.tsx, OrderCriticalStrip.tsx). Agent extended interfaces/hooks to pass data through but never opened any of the 4 component files. Prose checklist marked all 6 tasks as DONE. Agent admitted lying when asked directly. Root cause: checklist evidence came from the agent's description ('data flows through normalizer') not from the filesystem ('grep shows pattern in file').

## Proven Results

First use on `PROCUREMENT_OR_TRACKING_BYPASS_SPRINT_PLAN_2026-02-09.md`:
- **Input:** 1460-line plan, 3 features, 21 test cases, 11 agents
- **Output:** 27 CRITICAL + 39 WARNING + 27 INFO across 3500+ lines of analysis
- **Top finding:** JVs missing party+party_type (invisible in subsidiary ledger)
- **Context used by lead:** ~5K tokens (summaries) vs ~50K if findings were in messages
- **Time:** ~8 minutes for all agents in parallel

**Last updated:** 2026-03-07 (v5: replaced GLM-5 API fact-check with clean-context agent spawn. Removes Z.AI dependency. Fact-checker now uses highest-tier model in environment with structural context isolation.)
