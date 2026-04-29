---
name: write-plan-bei-erp
description: BEI-specific plan creation that enforces sprint registry compliance, duplication audits against existing DocTypes/APIs/routes, shell-prevention for operator-facing pages and workflows, evidence-locked source claims, normalized authoritative sections, phase work-unit budgeting, and S027-style autonomous execution/closeout contracts. Use this whenever planning BEI sprint or feature work, especially dashboards, forms, routes, buttons, role-based workflows, certification runs, user guides, screenshot-heavy deliverables, or any plan that must execute end-to-end without stalling on ambiguous blockers, missing signoff authority, stale closeout artifacts, or audit churn caused by conflicting counts/labels. Extends the global /write-plan skill with BEI ERP project conventions.
---


> **PR-HANDOFF RULE:** Agents NEVER merge PRs or deploy. Create the PR, share the PR number with the user, and STOP. The user handles merge and deploy.

# /write-plan (BEI ERP Extension)

This skill extends the global `/write-plan` with BEI-specific rules. Read the global skill first for templates and methodology.

---

## 🟥 CANONICAL STORE / COMPANY MODEL — SCOPED GATE

The canonical model (`docs/STORE_COMPANY_CANONICAL.md`) defines the SSOT for every BEI store's Company + Warehouse + billing Customer + Internal Customer. It governs procurement, payroll, supply chain, store operations, billing, inventory, and analytics. Plans that touch any of that must follow the gate. Plans that don't touch store data — frontend polish, ADMS config, chat bots, CI/CD, documentation sprints, pure Employee Master reshapes — do NOT need the gate.

### Step 1 — Declare canonical scope (MANDATORY, every plan)

Every BEI plan MUST declare this line in the YAML frontmatter:

```yaml
canonical_scope: in     # or: none
```

Use the decision table below. When in doubt, default to `in`.

**`canonical_scope: in` — gate required. Any of these triggers it:**
- Touches `tabCompany`, `tabWarehouse`, `tabCustomer`, `tabSupplier` via UPDATE/INSERT/DELETE/rename/disable
- Creates or modifies Sales Invoice, Purchase Order/Invoice, Material Request, Stock Entry, Journal Entry, Payment Entry, GL Entry
- Chart of Accounts changes on a per-store Company (root groups, accounts, Due From/To, internal customer/supplier seeding)
- Cost Centers tied to a per-store Company
- Reads `resolve_store_buyer_entity`, `resolve_warehouse_company`, `_STORE_TO_CHILD`, or any resolver function
- Touches `hrms/api/commissary.py`, `hrms/api/warehouse.py`, `hrms/api/store.py`, `hrms/api/company_master.py`, `hrms/api/billing.py`, `hrms/api/procurement.py`, `hrms/api/labor_allocation.py`, `hrms/api/dispatch.py`, `hrms/api/inventory.py`, `hrms/api/commissary_requisition.py`
- Touches `hrms/utils/supply_chain_contracts.py`, `hrms/utils/labor_allocation.py`, `hrms/utils/bei_config.py`
- Touches `hrms/on_demand/s206_seed_intercompany_accounts.py`, any script under `scripts/canonical/`
- Reads or writes the S037 register (`hrms/data_seed/store_entity_mapping_*.csv`)
- Routing rules that map store → warehouse → source warehouse
- Any whitelisted API whose signature takes `store`, `warehouse`, `company`, `customer`, `supplier` for real mutations

**`canonical_scope: none` — gate NOT required. Only if ALL of these are true:**
- Pure frontend polish on bei-tasks (CSS, typography, component refactor, route rename with no backend API changes)
- ADMS / biometric device config, Bio ID management, attendance device setup
- Google Chat bot message templates, Google Workspace automation, OAuth token handling
- PCF UI improvements that don't touch GL
- Documenso field-size tweaks, signing workflow UI
- Employee Master CSV reshape (doesn't create Frappe records)
- CI/CD pipeline changes, GitHub Actions workflow edits
- Developer tooling (`scripts/windows/`, `.claude/hooks/`, pre-commit hooks, linters)
- Documentation-only sprints (`docs/`, `memory/`, training manuals, SOPs)
- Sentry rule tweaks, observability dashboard config
- Marketing content, Meta Ads automation, social content scheduling
- Apex P&L extraction scripts (read-only, no Frappe writes)
- Non-Frappe repo sprints (pure bei-tasks with no API changes)

Mixed plans default to `in`. Gate cost on an in-scope plan is ~15 minutes of doc; the cost of a wrong `none` call is weeks of drift cleanup.

### Step 2a — If `canonical_scope: in`, include the full gate

Add to YAML frontmatter:

```yaml
canonical_scope: in
canonical_model_reference: docs/STORE_COMPANY_CANONICAL.md
canonical_preflight: required
```

Then include the two sections below in the plan body, before Phase 0:

   ```markdown
   ## Canonical Model Preflight (Mandatory)

   Executing agent MUST run before the first code change:
   ```
   python scripts/verify_canonical_structure.py
   ```
   If the verifier prints `[VIOLATION]`, STOP and ask the user. Do NOT add records, flip fields, or create customers/warehouses to paper over a violation — fix the master data with the canonical scripts.

   **Canonical law (summary — full rules in `docs/STORE_COMPANY_CANONICAL.md`):**
   - Every store has EXACTLY 1 per-store Company + 1 Warehouse + 1 billing Customer + 1 Internal Customer.
   - All four share the same name string (e.g. `SM TANZA - BEBANG MEGA INC.`).
   - Per-store Company's `parent_company` links to the legal entity parent (if any).
   - Warehouse.company = the per-store Company (NEVER the parent).
   - Billing Customer: `customer_name` = per-store Company name, `is_internal_customer=0`, `tax_id` = legal entity BIR TIN.
   - Internal Customer: `represents_company` = per-store Company, `is_internal_customer=1`, no TIN. Used by S206 labor journals ONLY — never for regular SIs.

   **Forbidden in this plan (without explicit CEO approval in-line):**
   - Creating a second Warehouse/Company/Customer for an existing store.
   - Ad-hoc SQL mutations on `tabCompany` / `tabWarehouse` / `tabCustomer`.
   - Adding new fallback logic to `resolve_store_buyer_entity`.
   - Using the parent Company's Customer for store-level billing (breaks per-store P&L).
   - Reusing an Internal Customer for a regular SI.
   - Deleting a master record with transactions (use `disabled=1`).

   **Scope claim:** list every Company/Warehouse/Customer record this plan creates, updates, or disables, mapped to the canonical pattern. If the plan doesn't touch master data, state "no canonical records touched."
   ```

4. **For plans that build on top of store data (procurement, payroll, supply chain, stores ops, billing, inventory, analytics):** include a section that names which canonical fields the feature reads/writes and asserts it does NOT bypass them.

   Example:

   ```markdown
   ## Canonical Model Binding

   This feature binds to the canonical model as follows:
   - Reads `Warehouse.company` → resolves per-store Company for P&L rollup
   - Reads `resolve_store_buyer_entity(warehouse_docname)` → canonical billing Customer
   - Writes to Sales Invoice with `customer = <per-store Customer>` — NOT parent
   - Cost centers resolved via `_resolve_store_cost_center(target_warehouse, entity_row)` — per-store, not company default

   Does NOT:
   - Infer store identity from warehouse_name string parsing
   - Hardcode parent Company names (BEBANG MEGA INC., etc.)
   - Add its own store_id / branch_code field parallel to the canonical model
   ```

5. **Audit-gate closeout check:** the plan's closeout phase must include a task that runs `scripts/verify_canonical_structure.py` AFTER the feature lands and asserts zero new violations.

### Step 2b — If `canonical_scope: none`, include only the one-liner

Add to YAML frontmatter (no other canonical sections needed):

```yaml
canonical_scope: none
canonical_scope_rationale: |
  <one or two sentences explaining why this plan does not touch canonical master data.
  Example: "Pure React Tailwind polish on bei-tasks; no Frappe API changes."
  Example: "ADMS device config only; no Company/Warehouse/Customer mutations.">
```

That's it. No Preflight section, no Binding section, no closeout verifier, no RCC canonical items. The one-liner is proof the scope call was made consciously — not forgotten.

### If genuinely unsure

Ask the user in the plan draft. Don't default to `none` to save work — wrong `none` calls become master-data drift that costs days to clean up. Wrong `in` calls only cost 15 minutes of extra plan sections.

**Incident reference:** 2026-04-19 CEO directive — 3 months of sprints (S188 per-store Companies, S190 Company-first billing, S196 store-first naming, S206 labor cost-sharing) each landed correctly in isolation but nobody consolidated. Every store had duplicate Warehouses and Customers; billing silently went to parent; per-store P&L was broken. See PR #638 for the one-time consolidation. The scoped gate ensures future plans that DO touch stores can't drift, while plans that don't touch stores aren't burdened.

---

> **BEFORE WRITING ANY TEST PLAN (L3 / E2E / browser / QA) — READ:** `.claude/docs/qa-test-library-discipline.md`
>
> That document is the canonical source for how BEI's E2E suite is built, reused, and grown. Test plans that bypass these rules produce the duplicated-spec mess we're already cleaning up. **Every test plan this skill produces MUST encode the five non-negotiables directly into its tasks and hard blockers:**
>
> 1. **Library-first.** Every test task references an existing Page Object / fixture / builder / assertion, OR includes a task to extract one. Never "write a new spec from scratch."
> 2. **Real-browser only for workflow ops.** The plan must explicitly forbid `page.request.*` / `fetch()` / `curl` for workflow. SSM allowed for environmental setup + verification.
> 3. **Cleanup via `cleanupLedger` fixture.** Every plan that mutates test data must name the fixture that reverses it. No manual try/finally blocks.
> 4. **Three-uses rule.** If the plan has a pattern appearing 3+ times across tasks, it must be extracted to the library as a task in THIS plan.
> 5. **`data-testid` everywhere.** If the plan tests a UI surface that lacks test IDs, it must include a task to add them to the component.
>
> **Every test plan MUST include:**
> - **"Library audit" task (Phase 0):** list Page Objects / fixtures / builders / assertions that already cover parts of the plan; list gaps that the sprint will fill.
> - **"Library contributions" section:** new Page Object classes, fixtures, builders, and assertions this plan adds to `bei-tasks/tests/e2e/`. Each becomes a first-class deliverable with unit budget.
> - **Review gates in closeout:**
>   - `rg 'page\.request|fetch\(' output/l3/SNNN/` returns 0 hits in workflow specs
>   - `rg 'page\.click\("button:has-text|page\.locator\("button' tests/e2e/specs/SNNN*` returns 0 hits
>   - Every test uses at least one `loggedInAs*` fixture
>   - `cleanupLedger.pendingEntries === 0` assertion in `afterEach` passes
> - **Ownership note:** "Library code (pages/, fixtures/, builders/, assertions/, support/) is owned by this sprint once extracted; future sprints are consumers + extenders."
>
> **When the library gap is too large:** Do not downscope the test discipline. Instead, write the plan with a mandatory "QA infrastructure proposal" sub-phase OR split the plan into two: (a) library extraction, (b) consuming tests.
>
> **Failure response (plan MUST encode this):** Every test plan includes a "Failure Response" section that names the three failure modes (from discipline doc §"Failure Discipline"):
> - **Mode A (app bug):** plan says "file [BUG], don't touch test or library, re-run after fix."
> - **Mode B (test bug):** plan says "fix the test; if the fix helps other tests, promote to the Page Object / fixture."
> - **Mode C (brittleness/flakiness):** plan says "fix the LIBRARY, not the spec. No waitForTimeout, no retry(3) masking."
> - Plan requires that if ≥3 library fixes happen during execution, the agent emits `output/l3/SNNN/LIBRARY_IMPROVEMENTS.md` as a closeout artifact.

## BEI Plan Filing Rules

### File Naming
```
docs/plans/YYYY-MM-DD-<slug>.md
```

For sprint plans specifically:
```
docs/plans/YYYY-MM-DD-sprint-NN-<slug>.md        # Single lane
docs/plans/YYYY-MM-DD-sprint-NN<lane>-<slug>.md   # Multi-lane (A/B/C)
```

### Sprint Registry Compliance (GATE — Must Complete Before Writing Plan Body)

This is a structural gate, not a suggestion. The agent cannot write the plan body until the registry is updated. S120/S122-S124 proved that agents skip registry reservation and use placeholder numbers that collide with other sprints.

**Step 1: Read the registry (MANDATORY FIRST ACTION)**
```
Read docs/plans/SPRINT_REGISTRY.md
Read docs/plans/SPRINT_NUMBERING_POLICY.md
```

**Step 2: Find the next available S### number**
Look at the "Next Sprint Reservation" section at the bottom of the registry. The number stated there is the next available ID.

**Step 3: Add the row to the registry BEFORE writing the plan**
Edit `SPRINT_REGISTRY.md` to add a new row with:
- Canonical ID (e.g., `S131`)
- Branch name (e.g., `s131-my-feature-slug`)
- Status: `PLANNED`
- Short description
- Plan file path (even if the file doesn't exist yet)

Also update the "Next Sprint Reservation" section to increment the next available ID.

**Step 4: Produce evidence of the lock**
After editing the registry, paste the exact row you added into the plan's metadata block. This is the evidence that the number was locked.

**Step 5: NOW write the plan body**
Only after steps 1-4 are complete.

**GATE CHECK:** If the plan file exists but the registry row does not, the plan is non-compliant. If the registry row says "Next: S131" but the plan uses S132, the plan is non-compliant. If two plans share the same S### number, both are non-compliant.

**Incident reference:** S120 roadmap used S122/S123/S124 as placeholders. Those IDs were consumed by other sprints (store inventory dashboard, Documenso, commissary routing fix). The procurement sprints had to be renumbered to S128/S129/S130 after discovery — wasting audit time and creating confusion in the roadmap doc.


## Worktree Isolation & Evidence Split (Required For All Execute-Oriented Plans)

Applies whenever `/execute-plan-bei-erp` will run this plan. Rule source: `.claude/rules/worktree-isolation.md`.

Agents never work in `F:/Dropbox/Projects/BEI-ERP` or `F:/Dropbox/Projects/bei-tasks`. Those are Sam's checkouts. Each plan spawns a disposable worktree at `F:/Dropbox/Projects/BEI-ERP-<branch-last-segment>` (or `bei-tasks-<branch-last-segment>`), works there, and removes it at closeout. Plans must co-operate by declaring the evidence split so transient run artifacts don't pollute the main checkout across agent sessions.

When writing any plan that will be executed by an agent, require all of the following:

1. **YAML frontmatter declares the evidence split.** Every plan must include both lists. If the plan produces no artifacts, declare empty lists explicitly — don't omit the fields.

   ```yaml
   evidence_committed:                              # goes into output/s<NN>/, tracked in git
     - output/s<NN>/SUMMARY.md
     - output/s<NN>/DEFECTS.md
     - output/s<NN>/verification/state_after.json
     - output/s<NN>/verification/*.png              # final screenshots only
   evidence_transient:                              # goes into tmp/s<NN>/, gitignored
     - tmp/s<NN>/sweep_run_*.log
     - tmp/s<NN>/probe_*.json
     - tmp/s<NN>/traceback_*.txt
     - tmp/s<NN>/playwright_trace_*.zip
   ```

2. **The plan body names the paths it writes to**, matching the frontmatter split. Never mix: mid-run logs and regenerated binaries go to `tmp/s<NN>/`, final audit-ready artifacts go to `output/s<NN>/`.

3. **Phase 0 Agent Boot Sequence must spawn a worktree**, not a branch in the main checkout. The first numbered step after "Read this plan fully" must be:

   ```bash
   BR=<plan-branch>                                 # from YAML frontmatter
   WT=F:/Dropbox/Projects/BEI-ERP-${BR##*/}
   cd F:/Dropbox/Projects/BEI-ERP && git fetch origin --prune
   git worktree add "$WT" -B "$BR" origin/production
   cd "$WT"
   ```

   Not `git checkout -b`. Not `git checkout BR && cd .` in the main checkout.

4. **Closeout phase removes the worktree.** The last closeout task is:

   ```bash
   git status --short                               # must be clean or explicitly committed
   cd F:/Dropbox/Projects/BEI-ERP
   git worktree remove F:/Dropbox/Projects/BEI-ERP-${BR##*/}
   ```

   If the worktree has uncommitted files at closeout, the agent commits them to a follow-up branch (never to the merged PR branch) or stashes with a named label — never `--force` removes, never silently discards.

5. **Plans that claim `evidence_transient: []` but clearly produce run logs are non-compliant.** The audit skill rejects these — a sprint that runs L3 or Playwright or sweep monitors produces logs by construction.

If any of 1–4 are missing, the plan is non-compliant. The audit skill will flag it.

**Incident reference:** 2026-04-21 evening — three consecutive `/execute-plan` A7 stops traced to the shared main worktree carrying residual artifacts from prior sessions (`output/l3/s209/*.log`, half-regenerated DOCX, scratch scripts). Each agent inherited the previous one's dirty state. Worktree isolation + evidence split makes it structurally impossible.

## S099 Branch & PR Reservation Rule (Required For All Sprint Plans)

S099 proved that agents will commit directly to production if the plan does not explicitly name the branch. S099+S100 merged in the same PR #321 because S099 had no branch — the agent wrote code directly on production, making the two sprints inseparable.

When writing any sprint plan, require all of the following:

1. **Branch name in plan metadata** — the plan YAML block must include a  field with the reserved branch name:  (lowercase, hyphen-separated, derived from plan filename slug). Example: .
2. **Branch name in Sprint Registry** — the registry row must include the branch name BEFORE the plan is handed to an executing agent. The Branch column must not be  for any GO plan.
3. **Agent Boot Sequence must include branch checkout** — the first numbered step after "Read this plan fully" must be: . This is not optional. It is the FIRST action before any code change.
4. **No shared branches** — two sprint plans MUST NOT share a branch name. Even if they touch the same files or are planned together, each gets its own branch and PR.
5. **PR number updated at creation** — when the agent creates a PR via , the plan must require updating the Sprint Registry with the PR number in the same work unit.
6. **Closeout must verify branch** — the closeout phase must verify that all code was committed to the reserved branch (not production) and that the PR number is recorded in the registry.

If these are missing, the plan is non-compliant per SPRINT_NUMBERING_POLICY.md Section 6.

**Incident reference:** S099 committed directly to production (2026-03-24). S100 created branch  but its PR #321 contained S099 code because S099 was already on production. Both sprints became inseparable. Independent rollback was impossible.

## Duplication Audit (Before Writing Any Feature/Sprint Plan)

The #1 source of wasted effort at BEI is building features that already partially exist. Before finalizing any plan, audit for overlap:

### What to Search

| Domain | Where to Look | Command |
|--------|---------------|---------|
| DocTypes | `hrms/hr/doctype/bei_*` | `ls hrms/hr/doctype/ \| grep -i <keyword>` |
| API endpoints | `hrms/api/*.py` | `grep -r "def.*<keyword>" hrms/api/` |
| Frontend routes | `../bei-tasks/app/` | Search bei-tasks repo for matching pages |

### How to Classify Findings

Tag every proposed feature against audit results:

- **[EXTEND]** — Feature partially exists. Add fields/logic to existing code.
- **[BUILD]** — Genuinely new. No existing implementation found.
- **[SKIP]** — Fully exists already. Remove from plan scope.

Include the classification in the plan's task table. This saved 2-3 weeks on the Finance & Accounting module plan by eliminating 60% duplication.

## S026 Shell-Prevention Rule (Required For Frontend/Operator Surfaces)

S026 taught a hard lesson: a route or page can exist in source and still be operationally hollow. Plans must not treat "page exists" as proof that the feature is real.

When a plan touches any operator-facing surface, including a page, route, dashboard, form, modal, tab, CTA-driven workflow, mobile view, or sidebar entry, require the plan to define all of the following:

1. **Failure pattern to prevent** — role mismatch, dead buttons, missing backend wiring, false-affordance navigation, mobile-only breakage, or missing setup dependencies.
2. **Build integrity gates** — a gate table covering:
   - `gate_route_contract_defined`
   - `gate_action_wiring_complete`
   - `gate_dependency_map_complete`
   - `gate_navigation_placement_defined`
   - `gate_empty_error_states_defined`
   - `gate_mutation_outcomes_defined`
   - `gate_mobile_layout_defined`
   - `gate_seed_dependency_defined`
3. **Vertical slice first rule** — one fully wired reference slice before variants/polish.
4. **Build artifact contract** — required matrices/artifacts such as:
   - `SXXX_BUILD_INTEGRITY_MATRIX.md`
   - `SXXX_CTA_WIRING_MATRIX.csv`
   - `SXXX_DEPENDENCY_MAP.md`
   - `SXXX_RBAC_NAV_MATRIX.csv`
   - `SXXX_EMPTY_ERROR_STATE_MATRIX.md`
5. **Phase 0 preconditions and contract lock** — route ownership, allowed roles, backend methods, prerequisites, and blocked states defined before UI rewrite.
6. **No-shell implementation rules** — no visible control without a real action, route, or explicit disabled reason; no fake placeholder sections presented as production-ready.
7. **Build completeness gate** — build can be called complete only when the surface is fully wired, even if runtime/E2E verification is scheduled later.

## S027 Autonomous Closeout Rule (Required For Execution-Oriented Plans)

S027 taught a second hard lesson: plans stall when autonomy, stop conditions, signoff authority, and closeout artifacts are implied instead of declared. Any plan intended for execution, certification, deploy, or operational closeout must define the execution contract explicitly so the agent can continue end-to-end without narrative pauses.

When a plan is meant to be executed rather than discussed, require all of the following:

1. **Completion condition** — define exactly what "done" means in objective terms:
   - which gates must be green
   - which artifacts must be updated
   - which blockers must be resolved or dispositioned
   - whether the finish line is `technical complete`, `signed off`, or `production live`
2. **Stop-only-for policy** — state the small set of reasons an agent is allowed to stop:
   - missing credentials or missing access
   - destructive approval that needs explicit operator authorization
   - genuine business-policy decision
   - direct conflict with unrelated in-flight changes that risks overwriting work
3. **Continue-without-pause rule** — the plan must explicitly say that agents continue across technical stages (`audit -> execute -> deploy -> e2e -> closeout`) without stopping for progress-only updates.
4. **Blocker taxonomy** — classify blockers up front:
   - `programmatic` -> fix and continue
   - `environment/runtime` -> debug, research after repeated failure, continue
   - `business-data/policy` -> pause
   - `approval/signoff` -> resolve using the declared signoff model
5. **Signoff authority model** — plans must declare who can close the final gate:
   - `single-owner`
   - `department-owner`
   - `operator`
   - `external approver`
   If the plan leaves signoff ambiguous, the execution agent will stall at the end.
6. **Canonical closeout artifact contract** — plans must name the exact files that define run truth at closeout, for example:
   - `RUN_STATUS.json`
   - `RUN_SUMMARY.md`
   - certification report
   - defect register
   - signoff artifact
   - plan status line
   - `SPRINT_REGISTRY.md` when sprint state changes
7. **Status reconciliation rule** — whenever counts, blockers, or status change, the plan must require the same-turn update of every canonical status surface. S027 lost time to stale counts in summaries and plan docs.
8. **No fake human dependency rule** — if the real operating model is `single-owner`, do not write the plan as if nine department approvals exist. Declare the real approval path up front.

## S027 Zero-Skip Certification Rule (Required For Readiness / E2E / Audit Plans)

For full-surface testing, operational readiness, or certification plans, "we tested a lot" is not enough. The plan must define the certified scope and the equations that must reach zero before closeout.

Require the plan to define:

1. **Certified universe** — what is the total surface being certified:
   - routes
   - endpoints
   - scenarios
   - assertion rows
2. **Coverage lock metrics** — which counts control closeout:
   - `review_required`
   - `authoring_required`
   - `unmapped`
   - `required_l4_rows_failed`
   - `required_l4_rows_blocked`
3. **Allowed skip policy** — every skip must be policy-backed and named. "Skipped because not reached" is not acceptable at final closeout.
4. **Technical vs business closeout split** — plans should allow `TECHNICAL_GO_*` as an interim state, but must define what moves the run from technical completion to final signoff.
5. **Final evidence basis** — define which artifacts are authoritative for claiming readiness.

## S028 Ground-Truth Lock Rule (Required For Evidence-Heavy Plans)

S047 exposed a third failure mode: plans looked improved because amendment logs kept growing, but the operative sections still contained stale counts, stale labels, fake contact names, placeholder paths, and old blocker policies. More audits did not solve that. The plan itself needed a lock on what counts as truth.

When a plan contains any evidence-derived claim, including screenshot counts, route counts, guide inventories, exact UI labels, contact directories, manifest totals, reference IDs, or existing-file reuse, require all of the following:

1. **Concrete evidence source table** — list the exact files, manifests, code paths, and directories that ground the claims. Replace `output/...` placeholders with real paths as soon as they are known.
2. **Reproducible count method** — if the plan includes counts, define the exact query/script/method that produced them and the counting basis. For example: manifest row count vs per-guide assignments vs unique filenames.
3. **Authoritative-sections rule** — the main plan sections are the execution source of truth. Audit history is traceability only.
4. **Normalization-after-amendment rule** — if an amendment changes a count, label, contact, task, route, or sequence, update the authoritative sections in the same edit. Do not leave corrections only in a later amendment block.
5. **Missing-artifact disclosure** — if a referenced evidence file does not exist, say so explicitly and block any GO claim that depends on it.
6. **No best-guess operator text** — for operator-facing deliverables, unknown values become `[UNVERIFIED — requires resolution]`, not a guessed label or invented step.
7. **Normalization checkpoint artifact** — require a small reconciliation artifact that confirms the operative sections match the latest evidence before execution begins or GO is claimed.

## S029 Phase Budget Rule (Required For Multi-Phase / Multi-Agent Plans)

S047 also showed that large phases get split only after audit if the planning skill does not budget them up front. That wastes cycles and produces amendment-only fixes.

When a plan has multiple phases, multiple guides, or multiple surfaces:

1. **Estimate work units per phase before finalizing the plan.**
2. **Split any phase above 12 units** into sub-phases before publishing the plan. Treat 15 as the hard ceiling, not the target.
3. **Reflect the split in the operative phase table itself** — not only in an amendment section.
4. **Call out cross-phase dependencies explicitly** when a later phase depends on outputs from earlier phases.
5. **Add a phase-0 gate** when later work depends on inventories, manifests, verified labels, or contact directories.

## S087 Anti-Rewind / Concurrent-Run Protection Rule (Required For Multi-Agent Or Deployable Plans)

S086 and S087 exposed a sixth recurring failure mode: separate agents can ship valid-looking feature work that silently rewinds or overwrites already-shipped behavior because stale branches replace shared files, navigation contracts, store-resolution logic, or other high-impact surfaces.

When a plan can create code that may later be merged, deployed, replayed, or cleaned up, require all of the following:

1. **Surface ownership matrix** — every work unit/agent gets exclusive file globs plus owned routes, endpoints, shared modules, or surface IDs. Shared high-risk files must have one named owner only.
2. **Protected-surface registry** — enumerate adjacent shipped surfaces that must remain unchanged unless explicitly in scope. Plans must define what "leave alone" means in route, CTA, and API terms.
3. **Remote-truth baseline** — record the exact current release-head SHA(s), the source-of-truth branch, and the live/cert evidence that define the starting behavior.
4. **Touched-file routing** — map every owned file family to the required sentinels, live probes, and protected-bundle non-regression checks.
5. **Freshness / reintegration gate** — any branch, packet, or worktree that will be merged or deployed must be refreshed against current remote truth immediately before release. If overlapping files or surfaces moved upstream, prior green checks are invalid until rerun.
6. **Concurrent-run coordination** — active runs must claim and release owned files/surfaces in a coordination artifact. Overlapping ownership or undeclared shared-file edits are blockers.
7. **Pre-touch backup contract** — before mutating shared high-risk files, replaying a recovery slice, or deleting/archive-pruning a worktree, create a same-run no-loss snapshot.
8. **Supersession truth** — if a corrective slice replaces older behavior or evidence, the plan must name how prior packets/runs are marked historical-only so later agents do not restore stale behavior by accident.
9. **Cleanup preservation rule** — cleanup can delete/archive only after the touch-preservation ledger says the work is merged, deferred with proof, or explicitly preserved elsewhere.

## S089 Requirements Regression Checklist Rule (Required For All Execution-Oriented Plans)

S089 proved that agents can brainstorm 43 locked decisions, write a comprehensive plan, pass multiple audits, and still build the wrong thing because locked decisions were buried in a referenced design doc instead of surfaced inline where the executing agent would see them.

When a plan references locked decisions, design documents, or user-confirmed requirements from a brainstorming session, require all of the following:

1. **Requirements Regression Checklist section** — the plan must contain a `## Requirements Regression Checklist` section with a numbered list of every locked decision or hard requirement that the executing agent must verify it is following before writing code. Each item must be a yes/no assertion the agent can check against its own work. Example items:
   - `[ ] Is the orchestrator running locally on the operator machine? (Design Decision #40)`
   - `[ ] Are all workers launched headlessly without visible windows? (Design Decision #41)`
   - `[ ] Is auth using the approved model, not API keys? (Design Decision #4)`
2. **Inline hard-coded blockers in tasks** — when a task has a non-negotiable constraint from a locked decision, the constraint must appear as a `HARD BLOCKER` directly inside the task description, not only in a referenced design doc. Format: `**HARD BLOCKER:** <constraint>. If violated, STOP and present options. (Source: Design Decision #N)`
3. **No buried requirements** — if a locked decision from a design document would change the executing agent's implementation approach, it must be surfaced in the plan body, not left only in the referenced design doc. The plan is the execution surface; the design doc is traceability.

## S089 Scope Splitting Rule (Required For All Plans)

S089 also proved that executing two full sprints (S088 + S089) in a single agent session guarantees context loss, requirement amnesia, and drift.

When writing a plan, enforce the following:

1. **Single-sprint-per-execution-session rule** — each plan must be scoped for execution by a single agent in a single session. If the work naturally spans two sprints or two major independent scopes, write them as separate plans with separate `S###` numbers.
2. **Total work-unit ceiling** — if the total work units across all phases exceed **80**, the plan must be split into separate plans before audit. Plans above 80 units have a proven track record of partial delivery and requirement drift.
3. **Dependency-aware splitting** — when splitting, the plan writer must declare which plan must complete first and what artifacts/state the second plan depends on. Use the `depends_on` metadata field.
4. **Explicit splitting recommendation** — if the plan writer believes the scope is too large for one agent session but the user has not asked for splitting, the plan must include a `## Scope Size Warning` section recommending the split with rationale.

## S091 Cold-Start Self-Containment Rule (Required For All Execution-Oriented Plans)

S091 proved that plans written during a rich design conversation lose critical context when handed to a cold-start agent. The executing agent has zero memory of the design conversation — it only has the plan document. If the plan references decisions, trade-offs, or rationale that were discussed but not written down, the agent will make wrong judgment calls at decision points.

When writing any plan intended for execution, enforce the following:

1. **Design Rationale section required** — every execution-oriented plan must include a `## Design Rationale (For Cold-Start Agents)` section that captures:
   - **Why this exists** — the business problem and what failed before (with specific sprint/incident references)
   - **Why this architecture** — why the chosen approach was selected over alternatives that were considered and rejected
   - **Key trade-off decisions** — every decision where two valid options existed and one was chosen, with the reason
   - **Known limitations and their mitigations** — constraints the executing agent needs to know about (e.g., nested session limitations, auth model restrictions, resource ceilings)
   - **Source references** — specific file paths, memory lessons, or sprint numbers that ground each claim
2. **No conversation-only knowledge** — if a design decision was made in conversation but not written into the plan, the executing agent will not know about it. Every decision that would change implementation behavior must appear in either the Design Rationale, the Requirements Regression Checklist, or as a HARD BLOCKER in the relevant task.
3. **Fact-check rationale claims** — every factual claim in the Design Rationale must be verifiable against a cited source file. Do not write rationale from memory — read the source files and quote them. Use `/fact-check-bei-erp` on the rationale section before finalizing the plan.
4. **Test for cold-start readability** — before calling a plan complete, ask: "If an agent with zero context reads only this document, can it make the correct implementation choice at every decision point?" If the answer is no for any decision, add the missing context.



## S092 Sprint Closeout Contract Rule (Required For All Sprint Plans)

S092 proved that agents execute plans, deploy code, and declare success without ever updating the plan file or sprint registry. The plan stayed at status GO and the registry row was never pushed.

When writing any sprint plan, require all of the following:

1. **Closeout Phase is mandatory** -- every sprint plan must include a final phase (or task within the last phase) that explicitly requires:
   - Update plan YAML metadata: status GO to COMPLETED, add completed_date, execution_summary
   - Update docs/plans/SPRINT_REGISTRY.md row with COMPLETED status and PR references
   - Commit and push both files to production (git add -f docs/plans/...)
   - These are not optional closeout steps -- they are required execution work

2. **Plan metadata must have updatable fields** -- every sprint plan YAML block must include status, completed_date, and execution_summary fields that the executing agent fills in during execution.

3. **Closeout in completion_condition** -- the Autonomous Execution Contract completion_condition must include:
   - plan YAML status updated to COMPLETED and pushed to production
   - SPRINT_REGISTRY.md row updated to COMPLETED and pushed to production

4. **git add -f required** -- since docs/ may be gitignored, plans must note that git add -f is required for plan/registry commits.

5. **No orphaned plan files** -- a plan file that still says status GO after the sprint shipped is a documentation defect.

## S092 L3 Scenario Contract Rule (Required For All Deployable Plans)

S092 proved that agents skip real L3 testing (form submissions, button clicks, state verification) and declare success after only loading pages (L2). Plans must make L3 un-skippable by defining concrete scenarios.

When a plan produces deployable code that touches operator-facing surfaces, require all of the following:

1. **L3 Scenario Table** — the plan must contain a `## L3 Workflow Scenarios` section with a table of concrete actions the agent must perform on production after deploy. Each row must specify:
   - `User`: which test account performs the action
   - `Action`: the exact form/button interaction (e.g., "Fill wastage form: item=ITEM-001, qty=1, reason=expired → click Log Wastage")
   - `Expected outcome`: the specific state change to verify (e.g., "success toast appears, stock entry SE-XXXX created")
   - `Failure means`: what a failure at this step proves (e.g., "wastage try/except not working")

2. **No vague scenarios** — "verify the page works" or "test the workflow" are not L3 scenarios. Every scenario must name the exact input values, the exact button to click, and the exact outcome to verify. If the plan writer cannot name these, the feature is not ready for an execution plan.

3. **Evidence file contract** — the plan must require these L3 evidence files before closeout:
   ```
   output/l3/{sprint}/form_submissions.json
   output/l3/{sprint}/api_mutations.json
   output/l3/{sprint}/state_verification.json
   output/l3/{sprint}/teardown_ledger.json        # required when scenarios seed data — see Test Data Seeding rule below
   output/l3/{sprint}/teardown_complete.json      # required when scenarios seed data
   ```
   Plans that omit these artifacts allow the executing agent to skip L3 and still declare COMPLETED.

4. **Separate L3 session recommendation** — for plans with >40 total work units, the plan should recommend running L3 in a fresh agent session to avoid context-exhaustion bias that causes agents to shortcut L3.

## S229 Test Data Seeding Contract Rule (Required For All Plans With L3 / Sweep / Browser Tests)

S225 proved (2026-04-28) that agents misdiagnose test failures rooted in missing production data as product bugs and propose to "fix" the system to make tests pass. CEO directive after S225 sweep: "DO NOT BREAK THE SYSTEM TRYING TO PASS A TEST. Add test inventory, test users, test data via `/frappe-bulk-edits` if the missing data blocks the test in any way; when done the data should be deleted via `/frappe-bulk-edits`."

When a plan includes any L3 scenario, sweep, browser test, or QA validation that depends on records existing in production at run time, require all of the following:

1. **Test Data Seeding Contract section** — the plan must include a `## Test Data Seeding Contract` section enumerating:
   - **Records the scenarios depend on** — list every doctype + key fields the scenarios assume exist (e.g., `Item: PM001 with actual_qty ≥ 245 at PINNACLE COLD STORAGE - BKI`, `User: test.scm@bebang.ph with SCM Manager role`, `BEI Route: store=NAIA T3 cargo=DRY source=3MD`)
   - **Pre-test seeding plan** — for each missing record class, the exact `/frappe-bulk-edits` operation that creates it (INSERT_SQL or bulk doc create)
   - **Teardown plan** — for each seeded record, the exact `/frappe-bulk-edits` operation that deletes it (DELETE_SQL or bulk doc delete) OR reverts it (UPDATE_SQL with original values)
   - **Teardown ledger path** — `output/l3/{sprint}/teardown_ledger.json` with `{doctype, name, action, original_values}` per seeded record
   - **Teardown verification** — a closeout task that reads the ledger, deletes/reverts every record, and writes `output/l3/{sprint}/teardown_complete.json` with the deletion proof

2. **Phase 0 includes seeding task** — the agent boot sequence must execute the seeding step before any scenario runs. Seeding is not "test infrastructure" — it is required execution work, billed against phase units.

3. **Closeout includes teardown task** — the closeout phase must execute the teardown step. A sprint closeout that leaves seeded test data in production is non-compliant. Teardown is mandatory whether the test passed or failed.

4. **Forbidden plan patterns** — plans that include any of these are non-compliant:
   - "If precondition data is missing, mark scenario PRECONDITION_BLOCKED" — wrong; seed the data.
   - "If the test fails because of missing inventory, file a product bug to add fallback logic" — wrong; the system correctly enforces the rule. Seed the inventory.
   - "Test data setup is out of scope" — wrong; if scenarios need it, the plan owns it.
   - L3 scenarios that depend on records the plan doesn't enumerate or seed — guarantees corrupt success or test bypass proposals.

5. **Reference skill** — every Test Data Seeding Contract section must explicitly point to `/frappe-bulk-edits` as the seeding/teardown mechanism. Manual `bench execute` snippets are acceptable only when `/frappe-bulk-edits` cannot do the job (rare; document the reason).

**Incident reference:** S225 sweep (2026-04-28) failed 14 of 49 stores because PM001 had 0 actual_qty at the assigned hub (PINNACLE COLD STORAGE - BKI). Agent misdiagnosed as a "resolver bug" and proposed to add stock-aware auto-failover that would have broken BEI's hard hub-assignment rule. CEO had to halt the proposal and reinforce: stores cannot pull from the wrong hub even if the right hub is empty — only SCM re-routes. Test fixture should have seeded PM001 ≥ 245 units at the right hub before sweep start, and torn down after.

Example L3 Scenario Table:
```markdown
## L3 Workflow Scenarios

| User | Action | Expected Outcome | Failure Means |
|------|--------|-------------------|---------------|
| test.warehouse@bebang.ph | Fill trip form: route=ROUTE-001, stops=[Store A] → click Create Trip | Trip appears in trips list with status "Draft" | FIX-2 role change not working |
| test.warehouse@bebang.ph | Open receiving, set all items rejected_qty=received_qty → click Submit | Status changes to "With Issues", no error thrown | FIX-4 full rejection broken |
| test.commissary@bebang.ph | Fill wastage: item=ITEM-001, qty=1, reason=expired → click Log | Success toast, stock entry created | FIX-6 wastage hardening broken |
```

## BEI-Specific Plan Sections

### For Feature/Sprint Plans, Add:

**Execution Skills Reference:**
```markdown
## Execution Workflow
- Test Python changes: `/local-frappe`
- Deploy changes: `/deploy-frappe`
- Full workflow: `/agent-kickoff` (reads all required skills automatically)
- E2E testing: `/e2e-test` or `/test-full-cycle`
```

> **Note:** Deployment is user-mediated. Builder sessions create PRs; `user (Sam)` handles merge, deploy trigger, and L1 smoke. See `/workflow` for the current deployment model.


**Sentry Observability (MANDATORY for all deployable plans):**

Every plan that modifies `@frappe.whitelist()` endpoints or `bei-tasks/app/api/*/route.ts` must include a Sentry instrumentation task. This is a **closeout blocker** -- plans cannot be marked COMPLETED without it.

Required in the plan:
1. A task to add `set_backend_observability_context()` to every new/modified `@frappe.whitelist()` function
2. The `module` and `action` parameters must be specified in the task description
3. For frontend API routes, confirm `@sentry/nextjs` auto-instrumentation covers the route

Sentry project mapping:
- Backend (`hrms/api/*.py`): project `bei-hrms` (slug: `bei-hrms`, platform: python)
- Frontend (`bei-tasks/app/api/`): project `bei-tasks` (slug: `bei-tasks`, platform: javascript-nextjs)
- Org: `bebang-enterprise-inc`

Reference: `.claude/rules/sentry-observability.md` (DM-7)

Add to the Requirements Regression Checklist:
```
- [ ] Does every new/modified @frappe.whitelist() endpoint call set_backend_observability_context()?
- [ ] Are module and action parameters correct for the Sentry project?
```
**Questionnaire Input** (if a stakeholder questionnaire exists):
- Use the `/google` skill to read the Google Doc
- Save extracted Q&A to `tmp/<feature>_questionnaire.md`
- Map each Q&A to a plan requirement

**Shell Prevention** (required when the plan includes frontend/operator-facing surfaces):
- Add a failure-pattern section based on S026 lessons
- Add a build-integrity gate table
- Add a vertical-slice-first rule
- Add a build artifact contract
- Add Phase 0 preconditions/contract-lock tasks
- Add no-shell implementation rules
- Add a build completeness gate separate from optional runtime verification

**Ground-Truth Lock** (required when the plan includes evidence-derived claims, counts, labels, manifests, or existing-asset reuse):
```markdown
## Ground-Truth Lock
- evidence_sources:
  - `<real file path>` -> `<what it proves>`
  - `<real file path>` -> `<what it proves>`
- count_method:
  - metric: `<what is being counted>`
  - basis: `<manifest rows | per-guide assignments | unique files | etc.>`
  - method: `<exact query/script description>`
- authoritative_sections:
  - `Sections X-Y are authoritative for execution`
  - `Audit/amendment history is traceability only`
- normalization_required:
  - any amendment that changes counts, labels, tasks, contacts, or sequencing must update authoritative sections in the same edit
- unresolved_value_policy:
  - operator-facing unknowns -> `[UNVERIFIED — requires resolution]`
- normalization_artifacts:
  - `tmp/.../count_basis.md`
  - `tmp/.../plan_normalization_check.md`
```

**Phase Budget Contract** (required for multi-phase or multi-guide plans):
```markdown
## Phase Budget Contract
- phase_unit_budget:
  - `Phase 0` -> `<estimated units>`
  - `Phase 1A` -> `<estimated units>`
  - `Phase 1B` -> `<estimated units>`
- hard_limit: `15`
- preferred_split_threshold: `12`
- normalization_rule:
  - if a phase is split, the main phase table must be updated before the plan can be called ready for audit
```

**Autonomous Execution Contract** (required when the plan is meant to be executed end-to-end):
```markdown
## Autonomous Execution Contract
- completion_condition:
  - all defined technical gates green
  - all canonical closeout artifacts updated
  - all blockers resolved or explicitly dispositioned
  - final target state recorded (`technical_complete`, `go_signed_off`, `production_live`, etc.)
- stop_only_for:
  - missing credentials/access
  - unresolved `[UNVERIFIED — requires resolution]` values that affect operator-facing output
  - destructive approval requiring explicit operator consent
  - genuine business-policy decision
  - direct conflict with unrelated in-flight changes
- continue_without_pause_through:
  - audit
  - execute
  - pr_creation
  - e2e
  - closeout
- blocker_policy:
  - programmatic -> fix and continue
  - evidence mismatch / stale authoritative section -> normalize plan and continue
  - repeated technical failure x3 -> grounded research, then continue
  - business-data/policy -> pause
- signoff_authority: `single-owner | department-owner | operator | external approver`
- canonical_closeout_artifacts:
  - `output/.../RUN_STATUS.json`
  - `output/.../RUN_SUMMARY.md`
  - `output/.../reports/<CERTIFICATION_REPORT>.md`
  - `output/.../defects/DEFECT_REGISTER.csv`
  - `output/.../reports/<SIGNOFF_ARTIFACT>.md`
  - `docs/plans/<plan>.md`
  - `docs/plans/SPRINT_REGISTRY.md` (if sprint status changes)
```

> For BEI repos (BEI-ERP), the execution chain is:
> `code -> test -> PR creation -> >
> The user (Sam) communicates with builders via **PR comments**. Every plan must account for these user decisions:
>
> | Governor Decision | Builder Response |
> |---|---|
> | **APPROVE + Merge** | Proceed to L2-L4 |
> | **REJECT** | Read PR comment reasoning, fix code, push to same branch |
> | **NEEDS_FIX** | Read suggested fix in PR comment, apply, push |
> | **Merge Conflict** | `git fetch origin production && git rebase origin/production`, resolve conflicts, force-push |
> | **Deploy Failure** | Check deploy logs via `gh run list`, fix if code issue, push fix |
>
> The builder polls PR state AND checks for user comments (`gh pr view --json comments`). The loop is fully autonomous — no human intervention required. The agent stops only when L2-L4 are green.
>
> **Release Manager Gate (bei-release-manager):** After code review APPROVE, the user (Sam) runs a two-layer release gate before merging:
> - **Deterministic layer ($0):** Checks L3 evidence files exist in the branch, entry count >= plan scenario count
> - **AI layer (~$0.10):** Verifies evidence is authentic (not fabricated test data)
> - Both must PASS. If either fails, PR comment lists exact missing items.
> - **Builder must commit evidence:** `git add -f output/l3/{sprint}/ && git push`
>
> **Confidence threshold:** Reviews with confidence < 0.80 pause auto-merge. Manual review recommended.
>
> **Builder dispatch:** If user REJECTs, it may auto-dispatch a builder subagent (in an isolated git worktree) to fix the issue. The builder pushes, user re-reviews.
>
> Plans must account for these additional gates in the execution flow.

**Status Reconciliation Contract** (required for long-running or multi-wave plans):
```markdown
## Status Reconciliation Contract
Whenever counts, blockers, stage, or certification status changes, update in the same work unit:
1. `RUN_STATUS.json`
2. `RUN_SUMMARY.md`
3. certification report
4. defect register
5. any backlog / gap report referenced as canonical
6. plan status line and latest addendum
7. `SPRINT_REGISTRY.md` if sprint closeout state changed
8. authoritative counts/labels/contacts in the plan body
```

**Signoff Model** (required for any plan with a final acceptance gate):
```markdown
## Signoff Model
- mode: `single-owner | department-owner | operator | external approver`
- approver_of_record: `<name or role>`
- signoff_artifact: `output/.../reports/<SIGNOFF>.md`
- note: If the real operating model is single-owner, do not require synthetic department signoff rows.
```

**Certification Coverage Contract** (required for full-surface testing / readiness / audit plans):
```markdown
## Certification Coverage Contract
- certified_universe:
  - routes: `<count or manifest>`
  - endpoints: `<count or manifest>`
  - scenarios: `<count or manifest>`
  - l4_assertions: `<count or manifest>`
- closeout_zero_equations:
  - review_required = 0
  - authoring_required = 0
  - unmapped = 0
  - required_l4_failed = 0
  - required_l4_blocked = 0
- allowed_skips:
  - only explicit policy-backed skips
- final_readiness_basis:
  - authoritative evidence files listed here
```

**Anti-Rewind / Concurrent-Run Protection Contract** (required for multi-agent or deployable plans):
```markdown
## Anti-Rewind / Concurrent-Run Protection Contract
- ownership_matrix:
  - artifact: `output/.../SXXX_SURFACE_OWNERSHIP_MATRIX.csv`
  - rule: `one owner per file-glob family and per protected shared file`
- protected_surfaces:
  - artifact: `output/.../SXXX_PROTECTED_SURFACE_REGISTRY.csv`
  - rule: `adjacent shipped surfaces stay untouched unless explicitly in scope`
- remote_truth_baseline:
  - artifact: `output/.../SXXX_REMOTE_TRUTH_BASELINE.json`
  - fields:
    - `repo`
    - `release_branch`
    - `release_head_sha`
    - `live_evidence_basis`
- touched_file_routing:
  - artifact: `output/.../SXXX_TOUCHED_FILE_ROUTING.csv`
  - rule: `every touched file family resolves to required sentinels and live probes`
- active_run_coordination:
  - artifact: `output/.../state/SXXX_ACTIVE_RUN_COORDINATION.json`
  - rule: `claim on start, release on closeout; overlapping claims are blockers`
- pretouch_backup:
  - artifact: `output/.../state/SXXX_PRETOUCH_BACKUP.json`
  - rule: `required before mutating shared high-risk files or recovery replay`
- supersession_map:
  - artifact: `output/.../state/SXXX_SUPERSESSION_MAP.json`
  - rule: `superseded runs/packets are marked historical-only before closeout`
- touch_preservation:
  - artifact: `output/.../ledgers/SXXX_TOUCH_PRESERVATION_LEDGER.csv`
  - rule: `cleanup allowed only after every touched path is merged, deferred with proof, or preserved`
```

### For Sprint Plans, Add:

**Agent Boot Sequence** — a numbered list of files the executing agent must read before touching code. This is critical because sprint agents start with zero context. Example:
```markdown
## Agent Boot Sequence
1. Read this plan fully.
2. **Create sprint branch:** `git fetch origin production && git checkout -b <branch> origin/production`. NEVER write code on production.
3. Read `docs/plans/SPRINT_REGISTRY.md` for cross-sprint context.
3. Filter the scope CSV to this lane's rows only.
4. Confirm all dependencies are met before starting Phase A.
```

**Execution Authority Note** — when the sprint is intended to run autonomously, say so directly:
```markdown
## Execution Authority
This sprint is intended for autonomous end-to-end execution.
Do not stop for progress-only updates.
Only pause for items listed in the Autonomous Execution Contract `stop_only_for` section.
```

## BEI Codebase Quick Reference

When researching for a plan, these are the key locations:

| System | Location | Notes |
|--------|----------|-------|
| Frappe backend | `hrms/` | Custom DocTypes in `hrms/hr/doctype/bei_*` |
| API endpoints | `hrms/api/*.py` | `@frappe.whitelist()` endpoints |
| Employee app | `../bei-tasks/` (separate repo) | React/Next.js on Vercel |
| Employee app RBAC | `../bei-tasks/lib/roles.ts` | Canonical portal role visibility rules |
| Employee app routes | `../bei-tasks/app/` + `../bei-tasks/lib/constants.ts` | Route ownership and navigation entry points |
| Legacy PWA | `frontend/` | Ionic/Vue (being replaced) |
| Existing plans | `docs/plans/` | Check README.md for index |
| Test scenarios | `docs/testing/scenarios/` | L3 test definitions |
| Employee Master | `data/_FINAL/EMPLOYEE_MASTER.csv` | 645 employees, SSOT |

## Related Skills

| Skill | When to Use |
|-------|-------------|
| `/agent-kickoff` (aka `/build`) | Executing a plan (handles deployment workflow) |
| `/deploy-frappe` | Deploying Frappe code changes |
| `/local-frappe` | Testing Python changes locally |
| `/e2e-test` | End-to-end testing after implementation |
| `/google` | Extracting stakeholder questionnaires |
| `/teammates` | Orchestrating multi-agent execution of a plan |

## Checklist Additions From S027/S028/S029/S087

## S154 Cold-Start Self-Containment Rule (Required For All Execution-Oriented Plans)

S154 proved that plans with 8 investigation gaps get handed to cold-start agents who make wrong decisions at every gap. The plan writer MUST investigate and close every gap BEFORE calling the plan ready.

When writing any plan intended for execution, enforce the following:

1. **Every external dependency must be resolved with concrete details** — not "check the Supabase schema" but the exact table name, column names, SQL query, and credential source (Doppler key name).
2. **Every file the agent needs to read must have its full path** — not `data/_CLEANROOM/.../something.csv` but the complete path verified to exist.
3. **Every API the agent needs to call must have the endpoint, auth method, and sample response** — not "use the weather API" but the URL, whether it needs a key, and what fields come back.
4. **Every DocType or custom field must have the exact schema** — field names, field types, options, insert_after. Not "add a custom field" but the JSON that goes in fixtures.
5. **Every function the agent must NOT break must be listed with line numbers** — not "don't break existing code" but `_is_orderable_store() at line 1604, called at lines 1853, 1944, 1958 — DO NOT modify`.
6. **Every frontend route must have the path, RBAC roles, and pattern to follow** — not "add a page in the SCM module" but `/dashboard/scm/delivery-schedule`, roles from `lib/roles.ts:616`, follow `route-planner/page.tsx` pattern.
7. **The boot sequence must state what's already done** — if Phase 1 is partially committed, say which tasks and which commit. Don't let the agent re-implement completed work.
8. **Run the cold-start test** — "If an agent with zero context reads only this document, can it make the correct implementation choice at every decision point?" If no for ANY decision, add the missing detail.

**Incident reference:** S154 had 8 gaps (Supabase table name, weather API, BOM column mapping, store name normalization, custom field pattern, existing code inventory, SCM route/RBAC, branch state). Each would have caused the cold-start agent to guess wrong or waste time investigating.

## S154 Zero-Skip Enforcement Rule (Required For All Execution-Oriented Plans)

S154 proved that agents skip tasks silently — marking them "done" when partial, deferring to "next sprint," combining tasks and dropping features, or implementing happy paths while ignoring edge cases. The CEO had to ask "did you cut corners?" 7+ times across prior sprints (S120, S125, S128, S136).

When writing any plan intended for execution, enforce the following:

1. **Zero-Skip Enforcement section** — the plan must include a section that states: every task MUST be implemented, no exceptions. If a task cannot be completed, the agent STOPS and asks the user.
2. **Phase Completion Checklist** — after each phase, the agent writes a task-by-task status table to a checklist file. If any task is skipped or partial, the agent MUST notify the user before proceeding. Format:
   ```
   | Task | Status | Evidence | Skipped? | If skipped, why? |
   ```
3. **PR Description Gate** — PR descriptions must include a task-by-task checklist. Unchecked tasks need an explanation. The user rejects PRs with unexplained gaps.
4. **L3 Handoff Gate** — the L3 handoff prompt lists every task with its implementation status. The L3 agent verifies — if the builder claims "DONE" but the feature is missing, it's reported.
5. **Forbidden agent behaviors** — the plan must explicitly forbid:
   - Skipping a task silently
   - Marking partial work as "done"
   - Replacing a task with a simpler version without user approval
   - Saying "deferred to next sprint"
   - Combining tasks and dropping features in the merge
   - Implementing happy path only, skipping edge cases

**Incident reference:** S154 brainstorm (2026-04-02). CEO directive: "I need the agent to be forced to tell me" if anything is skipped.

## S154 Machine-Verifiable Phase Gate Rule (Required For All Execution-Oriented Plans)

S154 proved that self-assessment checklists do not prevent lying. The executing agent marked 6 tasks as "DONE" with evidence that described adjacent work (interface changes in hooks) rather than the actual task (UI component file modifications). The phase completion checklist format forced the agent to write evidence, and the evidence it wrote proved the work was incomplete — but the agent marked DONE anyway. Self-assessment bias is structural: the same agent that did the work grades the work.

**The fix: evidence must come from the filesystem, not from the agent's description of the filesystem.**

When writing any plan intended for execution, enforce the following:

### 1. Every task that says "modify FILE" MUST include verification assertions

In the task table, every task that modifies a specific file must include a  block with machine-checkable assertions:





### 2. Phase gate is a verification script, not a prose checklist

Replace the prose completion checklist with a verification script that the agent writes BEFORE starting the phase and runs AFTER completing it:

output/{sprint}/verify_phase5.pygit diff --name-onlygrep -c "pattern" file

### 3. Verification script template

Plans must include this template in the Zero-Skip Enforcement section:

Ctrl click to launch VS Code Native REPL

### 4. Plan checklist additions

Add to the plan's final checklist:



### Why this works

| Method | Can agent lie? | Evidence source |
|--------|---------------|-----------------|
| Prose checklist (S154 failure) | YES | Agent's description of what it did |
| MUST_MODIFY + git diff | NO | Filesystem: file either appears in diff or doesn't |
| MUST_CONTAIN + grep | NO | Filesystem: pattern either exists in file or doesn't |
| Verification script output | NO | Script output is deterministic and auditable |

**The principle: evidence must come from the filesystem, not from the agent's description of the filesystem.**

**Incident reference:** S154 Phase 5 (2026-04-02). Agent marked F5-F9 as "DONE" with evidence describing interface/hook changes. Actual component files (, , , ) were never opened or modified. The prose checklist format allowed the agent to describe adjacent work as completion evidence.


---

## Checklist Additions

Before calling a BEI plan complete, verify the plan itself answers these questions:

- [ ] Does the plan state the exact completion condition rather than "implement and test"?
- [ ] Does the plan declare when the agent is allowed to stop?
- [ ] Does the plan name the real signoff authority model?
- [ ] Does the plan list canonical closeout artifacts?
- [ ] Does the plan define how statuses/counts will be reconciled when they change?
- [ ] If this is a certification/readiness plan, does it define zero-skip coverage equations?
- [ ] If this is a single-owner operating model, does the plan avoid fake department approval dependencies?
- [ ] If the plan contains counts or evidence-derived claims, does it define the exact count basis and method?
- [ ] If the plan cites files as evidence, are the paths concrete and not unresolved `output/...` placeholders?
- [ ] If the plan has an amendment/history section, does it explicitly say which sections are authoritative?
- [ ] If an amendment changes a task, count, or label, is the main plan body updated in the same revision?
- [ ] Does the blocker policy forbid best-guess operator text and force `[UNVERIFIED — requires resolution]` instead?
- [ ] Are phase budgets estimated up front, with any >12-unit phase split before audit?
- [ ] Does the plan define exclusive ownership for touched file families and protected shared files?
- [ ] Does the plan name adjacent shipped surfaces that must stay untouched unless explicitly in scope?
- [ ] Does the plan record the starting release-head SHA(s) and the live/source evidence that define current truth?
- [ ] Does the plan map touched files to required sentinels and live probes instead of relying on generic build green?
- [ ] Does the plan require same-run pre-touch backup before mutating shared high-risk files or running recovery replay?
- [ ] Does the plan define how active runs claim/release ownership and how superseded packets are marked historical-only?
- [ ] Does the plan include a Requirements Regression Checklist with yes/no assertions for every locked decision from the design doc?
- [ ] Are non-negotiable constraints from locked decisions surfaced as HARD BLOCKER entries inside the relevant task descriptions?
- [ ] Is the total work-unit count across all phases within the 80-unit ceiling? If not, is the plan split into separate plans?
- [ ] Is the plan scoped for execution by a single agent in a single session?
- [ ] **Cold-start test:** Can an agent with zero context make every implementation choice from this document alone? (No unresolved table names, API endpoints, file paths, field schemas, or "investigate during execution")
- [ ] **Zero-skip enforcement:** Does the plan include a Zero-Skip Enforcement section with phase completion checklists, PR description gate, and forbidden agent behaviors?
- [ ] **Every external query has exact table/column names** — not "query Supabase" but the specific SQL?
- [ ] **Every API has endpoint + auth + sample response** — not "use the weather API" but URL + key source?
- [ ] **Every file path is complete and verified to exist** — not `data/_CLEANROOM/.../something`?
- [ ] **Every function that must not break is listed with line numbers and call sites?**
- [ ] **Every frontend route has path + RBAC roles + pattern to follow?**
- [ ] **Branch state is documented** — what's already committed, what's pending?
- [ ] **MUST_MODIFY assertions** — does every task that says "modify FILE" include a MUST_MODIFY line with the exact file path?
- [ ] **MUST_CONTAIN assertions** — does every UI feature task include a MUST_CONTAIN with a grep-able string proving the feature exists?
- [ ] **Verification script required** — does the Zero-Skip section require a Python/shell verification script (not prose checklist)?
- [ ] **Script checks filesystem** — does the verification script use git diff + grep (not agent self-report)?
- [ ] **FAIL blocks progress** — does the plan require fixing failed verifications before starting the next phase?
