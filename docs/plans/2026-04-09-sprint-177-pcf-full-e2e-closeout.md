# Sprint 177 — PCF Full End-to-End Closeout

```yaml
sprint_id: S177
sprint_name: pcf-full-e2e-closeout
sprint_date: 2026-04-09
plan_version: 1
status: PLANNED
owner_decision_maker: Sam (CEO)
owner_technical_executor: Claude (single-owner execution)
branch: s177-pcf-full-e2e-closeout
target_repo: BEI-ERP
target_branch_base: production
registry_row: "| `S177` | Sprint 177 | `s177-pcf-full-e2e-closeout` | — | PLANNED 2026-04-09 | `docs/plans/2026-04-09-sprint-177-pcf-full-e2e-closeout.md` |"
depends_on: S167 (COMPLETED 2026-04-09, hrms#516 verification evidence PR pending merge)
completed_date: null
execution_summary: null
```

---

## Mission

S167 REDO proved the PCF happy path works end-to-end in browser. But S167's scope was the happy path. There are **7 real-user paths + 1 infra gap = 8 total gaps** that S167 did not exercise. A real BEI crew member rolling out this feature will hit these paths on day one. This sprint closes each gap with browser or SSM evidence, fixes any bugs found, and gives Sam a factual green-light decision for full rollout (45 stores + all dept custodians).

---

## Pre-execution policy decisions (LOCKED before Phase 0)

Decisions made before sprint kickoff so the executing agent never stalls on a business-policy question.

### PD-1. PCF replenishment is a cash-swap, NOT a withholding event
**Decision (Sam, 2026-04-09):** The PCF float is a reimbursement mechanism — the custodian pre-pays for expenses on behalf of BEI and the replenishment JE is a **cash-to-cash transfer** from a source bank/cash account to the custodian's PCF float. EWT and VAT are handled at the **original supplier invoice booking** (which happens separately when the actual procurement invoice is processed), NOT at the PCF replenishment step. The 2-row JE (Dr PCF cash 1113000 / Cr source account) is correct accounting for a cash swap.

**Implication for Phase 1:**
- DM-3 (EWT/VAT) is **DOCUMENTED NON-APPLICABLE** for the replenishment JE. Phase 1 does NOT add EWT Payable or Input VAT lines. This is a policy decision, not a code gap.
- Custodian `party_type="Employee"` + `party=<custodian_employee_id>` IS still required on the Dr row per DM-1 (subsidiary ledger traceability — which employee holds the float).
- Source account row has no party (internal cash account, not receivable/payable).

### PD-2. Phase 5.3 fund-disabled-mid-submission policy
**Decision:** If admin disables a fund with pending expenses: (a) existing pending expenses stay visible and submittable by the custodian, (b) new `add_expense_to_pending` calls return 4xx "fund disabled", (c) custodian CAN still submit the existing batch. Matches existing `is_enabled` guard pattern; avoids destroying in-flight work.

### PD-3. Phase 2 HEIC + 10 MB cap policy
**Decision:** HEIC is expected to either be rejected by the OS file picker (`accept="image/*,.pdf"`) OR to fail gracefully client-side. The 10 MB `alert()` cap in `document-upload-field.tsx` is acceptable for MVP — iPhone camera JPGs are typically 2-5 MB. Phase 2.4 accepts "picker rejects OR clear error surfaces" as PASS.

### PD-4. Phase 1.5 UI path
**Decision:** No `Request Replenishment` button exists on the accountant review page as of 2026-04-09 (verified via grep — `request_replenishment` is wired in `app/api/pcf/route.ts` and `hooks/use-pcf.ts` but no component renders it). Phase 1.5 runs as **SSM-only** backend call via `bench execute`. DEFECT-036 candidate (out of S177 scope): add custodian-facing Request Replenishment button.

---

## PROOF — What S167 Actually Verified (With Citations)

Every claim below is backed by an artifact on disk or in a merged PR. Nothing from memory.

### Admin dept-fund creation
- **Flow:** sam → `/dashboard/accounting/pcf/admin` → Create Department Fund dialog → native select dept → fill amount+threshold → Create click → enable switch → Save.
- **Proof:** `scripts/s167r_phase0_1.js` executed 2026-04-09; form_submissions.json entries `0.1_HR`/`0.1_SupplyChain`/`0.1_Commissary` with `method: "BROWSER dialog clicks + switch + save"`, `submit_action: "combobox pick + fill + Create click → navigate + switch click + Save click"`, response `{status: 200}`.
- **Screenshots:** `output/l3/s167/screenshots/p0.1_{HR,SupplyChain,Commissary}_{admin,dialog_open,filled,after_create,enabled}.png` — 15 files, each >5 KB.

### Fund resolution per role (6 users × 6 routes)
- **Flow:** test.{staff,supv,hr,warehouse,commi,finance} → their dept PCF route → DOM scrape confirms fund label + amount.
- **Proof:** `scripts/s167r_phase0_2.js`; state_verification.json entries `0.2_{who}` with `passed: true` for all 6.
- **Screenshots:** `output/l3/s167/screenshots/p0.2_{staff,supv,hr,warehouse,commi,finance}.png`.

### Store PCF lifecycle (6 scenarios)
- **Flow:** test.staff adds Mercury Drug ₱250 → 7-Eleven ₱150 → Globe Telecom ₱299. test.supervisor sees fund-wide ₱699 pending. Inline edit 7-Eleven 150→180 via `button[aria-label="Edit expense 7-Eleven"]`. Submit Batch.
- **Proof:** `scripts/s167r_phase1.js` + `s167r_phase1_edit_submit.js`; form_submissions entries `1.1_MercuryDrug`/`1.1_7Eleven`/`1.1_Globe`/`1.3_edit`/`1.4_submit`. DB state verified via `s167r_handoff_snapshot.py`: `BEI-PCF-2026-00003` total 729.0 (250 + 180 + 299 = 729, confirming the 150→180 edit persisted).
- **Screenshots:** `p1.1_{MercuryDrug,7Eleven,Globe}_{filled,after}.png`, `p1.2_supv_pending.png`, `p1.3_{before_edit,dialog_open,amount_changed,after_edit}.png`, `p1.4_{before,after}_submit.png`.

### HR dept PCF lifecycle
- **Flow:** test.hr adds NBS ₱480 + Jollibee ₱350. Submit batch.
- **Proof:** `scripts/s167r_phase2.js`; batch `BEI-PCF-2026-00004` total 1,660 (4 items) submitted with 200 OK.
- **Screenshots:** `p2.1_{NBS,Jollibee}_{filled,after}.png`, `p2.2_{hr_pending,pending,after}.png`.

### Accountant review (classify + approve + reject + empty-COA validation)
- **Flow:** test.finance opens review queue → clicks HR fund (→ `/review/fund/PCF-HR%20and%20Admin`) → clicks Run AI Classification → edits Final COA cells → clicks Approve with COA (200 OK). On commissary batch: clicks Reject Batch + fills reason textarea (200 OK). Clicks Approve on empty COA → client-side validation fires: "Some rows are invalid — see highlighted items".
- **Proof:** `scripts/s167r_phase3.js` + `s167r_phase3_approve_only.js`; form_submissions entries `3.2a_ai_classify`/`3.2b_approve`/`3.2b_retry`/`3.3_reject`/`3.4_empty_coa`. Batch `BEI-PCF-2026-00004` final status Approved; `BEI-PCF-2026-00005` final status Rejected.
- **Screenshots:** `p3.1_queue.png`, `p3.2a_after.png`, `p3.2b_{filled,after,retry_before,retry_filled,retry_after}.png`, `p3.3_{before,dialog,after}.png`, `p3.4_{before,after}.png`.

### Admin edit HR fund (5000/60 → 8000/70)
- **Flow:** sam → admin card for HR and Admin → amount 5000→8000, threshold 60→70 → Save click. Then test.hr dashboard shows ₱8,000 / 70%.
- **Proof:** `scripts/s167r_phase4.js` + `s167r_phase4_verify.js`; form_submissions `4.1_edit_hr_fund` response `{"success":true,"message":"PCF settings updated for HR and Admin"}`. DOM scrape of test.hr dashboard matched `/8,?000/` and `/70\s?%/`.
- **Screenshots:** `p4.1_{admin,hr_card,filled,after,dialog,hr_visible}.png`, `p4.2_{hr_dashboard,verify}.png`.

### Sidebar RBAC + legacy redirect
- **Flow:** expand sidebar group headers for test.staff/test.hr/test.finance, scrape anchors, verify R3 (PCF under dept) + R10 (no PCF under My Expenses). Legacy `/dashboard/expense/pcf` → dept-correct redirect.
- **Proof:** `scripts/s167r_phase5.js` + post-fix `s167r_verify_fixes.js`; state_verification entries show R3:true R10_noPcf:true. Legacy redirect test: test.hr → `https://my.bebang.ph/dashboard/hr-admin/pcf`, test.commi → `/dashboard/commissary/pcf`.
- **Screenshots:** `p5_sidebar_{staff,hr,finance}.png`, `verify_028_{hr,commi}_redirect.png`.

### Full rollback (Phase 6)
- **Flow:** delete batches → delete child items → delete expense requests → delete dept funds → restore employee depts.
- **Proof:** `scripts/s167r_phase6_rollback.py` executed 3× across the REDO session; final run deleted `BEI-PCF-2026-00006` + expenses 91-93 + 3 dept funds, restored 3 emps. Orphan audit via `s167_audit_orphans.py`: `BEI PCF Batch Item` orphan count = 0, `BEI Expense Request` dangling `pcf_batch` count = 0.

### DEFECT-009 resolver end-to-end (post fix-PR #513)
- **Flow:** create Lalamove expense → batch → `classify_batch_items()` → inspect `suggested_coa`.
- **Proof:** `scripts/s167r_e2e_defect_009.py` executed 2026-04-09 against backend `457f5de63c5f`. Output: batch `BEI-PCF-2026-00008`, expense `BEI-EXP-2026-00095`, `suggested_coa = "DELIVERY RIDERS - Bebang Enterprise Inc."` (NOT naked `6009003`). Rollback: batch + expense + item all deleted.

### DEFECT-029 classifier OpenAI fallback (post in-container config)
- **Flow:** install `openai_api_key` in `site_config.json` via SSM from Doppler. Re-run `classify_expense()` on Jollibee + NBS.
- **Proof:** `scripts/s167r_configure_openai.py`; classify result — `National Book Store` → `coa=6006003`, `method=openai`; `Jollibee` → `coa=6010100`, `method=openai`. Runtime health: `openai_key_configured=True`, `openai_available=True`.

### Test-infra role trim
- **Proof:** `scripts/s167r_scope_test_roles.py`; test.hr before=[Accts Mgr, Employee, HQ User, HR Mgr, HR User], after=[Employee, HR User]. test.finance before=[Accts Mgr, HR User], after=[Accts Mgr, Accts User, Employee].

---

## Remaining Gaps (7 paths NOT verified by S167)

Each gap below becomes one Phase in this sprint. Every gap must close with browser or SSM evidence following S167 discipline.

### Gap 1 — Replenishment flow (`request_replenishment`)
- **What's untested:** after a batch is Approved, the custodian (or finance) calls `request_replenishment` which creates a Journal Entry moving cash from the replenishment source account back into the custodian's float. S167 stopped at Approved; the money-movement half was never exercised.
- **Code path:** `hrms/api/pcf.py::request_replenishment` (line 880) + `_create_replenishment_journal_entry` (line 929).
- **Risk:** breaks on missing source account, wrong cost center, EWT/VAT treatment, or savepoint rollback. DM-1/DM-2/DM-3/DM-6 from `.claude/rules/frappe-development.md` all apply.

### Gap 2 — Real-sized receipt upload
- **What's untested:** DEFECT-023 fix was verified with `test_receipt.png` (1.6 KB). Real crew members upload 2-8 MB phone photos. The downscale path (`components/pcf/pcf-add-entry.tsx::downscaleImageDataUrl`, canvas resize to 1800px/0.85 JPEG) was proven once (Sam's 3.3 MB Gemini JPG) but has not been re-verified after all the downstream fixes.
- **Also untested:** HEIC format from iPhone cameras. The Vercel API route has a 4.5 MB body limit for base64 payloads.

### Gap 3 — Mobile viewport
- **What's untested:** all S167 Playwright runs used 1440×900 desktop viewport. Shadcn Sidebar, inline edit dialogs, receipt upload, and the Add PCF Entry form behave differently at mobile breakpoints (<768px). Crew members use phones, not desktops.

### Gap 4 — Google Chat threshold notification
- **What's untested:** the PCF admin card has a "Send Google Chat notification when threshold reached" switch. S167 never exercised the send path. Code: `hrms/api/pcf.py` — need to locate the threshold-check function + Google Chat webhook client.

### Gap 5 — Edge cases
- **Cancel a Draft batch** — not tested.
- **Delete a Pending expense from the custodian pending list** — partially tested by DEFECT-022 fix but never end-to-end.
- **Re-submit a Rejected batch** — after reject, can the custodian edit + resubmit? Untested.
- **Fund disabled mid-submission** — what happens if admin disables fund while custodian has pending expenses? Untested.

### Gap 6 — Concurrent users
- **What's untested:** 2-3 users simultaneously adding expenses to the same fund. Potential row-lock / race conditions in `pending_total` updates, `fund_label` autoname, batch item idx assignment.

### Gap 7 — Month-end auto-submit cron
- **What's untested:** the `month_end_auto_submit` flag is settable per fund, but the cron that honors it (Frappe scheduler) has never been verified running on the 28th/last-day-of-month.

### Gap 8 (infra) — DEFECT-029 persistence
- **What's untested:** `openai_api_key` lives in the `sites` Docker volume. Persists across container restarts, **vanishes on full teardown** (new volume). Need a bootstrap entry in the Frappe image or init hook that reads from env and writes to `site_config.json` at startup.

---

## Phase Budget Contract

| Phase | Title | Units | Notes |
|---|---|---|---|
| Phase 0 | Preconditions + baseline snapshot | 4 | Create 3 dept funds, realign emps, snapshot `handoff_snapshot.json` |
| Phase 1 | Replenishment flow e2e | 12 | Browser approve → SSM-probe JE existence → verify DM-1 through DM-6 |
| Phase 2 | Receipt upload stress | 8 | 3 MB JPG, 8 MB JPG, HEIC, upload through Add PCF Entry |
| Phase 3 | Mobile viewport | 10 | iPhone 13 Pro + Pixel 7 emulation, full 1.1 → 1.4 flow |
| Phase 4 | Chat threshold notification | 8 | Drive pending toward 60%, watch Chat Space, verify via Chat API |
| Phase 5 | Edge cases (cancel/delete/resubmit/disable) | 10 | 4 sub-scenarios, each browser-captured |
| Phase 6 | Concurrent users | 6 | 2-context Playwright, same fund, race the pending_total |
| Phase 7 | Month-end auto-submit cron | 6 | SSM time-travel (mock date), verify scheduler fires |
| Phase 8 | DEFECT-029 persistence (Dockerfile bootstrap) | 8 | Edit `frappe_docker_build/images/bench/Dockerfile` or entrypoint to read `OPENAI_API_KEY` env and patch `site_config.json` |
| Phase 9 | Rollback + closeout | 4 | Delete test data, restore emps, update plan YAML + registry, create PR |
| **Total** | | **76** | within 80-unit ceiling |

`hard_limit: 15 per phase` — no phase above 15 units. `preferred_split_threshold: 12`. Phase 1 is 12 (at threshold); Phase 3 is 10 (safe).

---

## Ground-Truth Lock

```yaml
evidence_sources:
  - output/l3/s167/form_submissions.json -> proves every S167 scenario was captured as a browser form submit
  - output/l3/s167/api_mutations.json -> proves every mutation was via waitForResponse, not page.request.post
  - output/l3/s167/state_verification.json -> proves per-scenario DOM scrape outcomes
  - output/l3/s167/audit_orphans.json -> proves Phase 6 rollback was clean
  - output/l3/s167/DEFECT_REGISTER.md -> final S167 defect ledger (29 defects, 28 resolved, 1 WONTFIX)
  - hrms#510 merged commit -> DEFECT-009 initial fix (`_resolve_coa_code_to_account` introduced)
  - hrms#512 merged commit -> DEFECT-017 flat fund response
  - hrms#513 merged commit -> DEFECT-009 resolver fix (account_number lookup)
  - BEI-Tasks#367 merged commit -> DEFECT-026/027/028 frontend fixes
  - BEI-Tasks#370 merged commit -> DEFECT-027 follow-up (procurement/projects/campaign)
count_method:
  - metric: "S167 defects resolved"
    basis: "entries in output/l3/s167/DEFECT_REGISTER.md counted manually"
    method: "grep -c '^## DEFECT-' output/l3/s167/DEFECT_REGISTER.md"
authoritative_sections:
  - "PROOF section above is authoritative for what S167 verified"
  - "Remaining Gaps section above is authoritative for what S177 must close"
  - "Phase tables below are authoritative for execution"
normalization_required:
  - any new defect discovered during S177 must be logged in output/l3/s177/DEFECT_REGISTER.md AND the PROOF section amendment block of this plan in the same commit
unresolved_value_policy:
  - any path the agent cannot verify as existing becomes "[UNVERIFIED — requires resolution]" and blocks the phase
normalization_artifacts:
  - output/l3/s177/RUN_STATUS.json
  - output/l3/s177/RUN_SUMMARY.md
  - output/l3/s177/DEFECT_REGISTER.md
```

---

## Autonomous Execution Contract

```yaml
completion_condition:
  - all 8 gaps closed with browser or SSM evidence on disk
  - any new defects surfaced are fixed via PR and re-verified (zero-carry-forward rule)
  - output/l3/s177/RUN_STATUS.json.passed >= 0.95 (allow 5% slack for mobile-viewport cosmetic nits)
  - plan YAML status: PLANNED -> COMPLETED with completed_date + execution_summary
  - SPRINT_REGISTRY.md row updated with PR number(s) and status COMPLETED
  - closeout PR created against production, PR number recorded
stop_only_for:
  - missing OpenAI key in Doppler (Gap 8 blocker)
  - real Google Chat webhook space not configured for test fund (Gap 4 blocker)
  - Frappe bench image source not accessible (Gap 8 blocker)
  - destructive change to production cron schedule that needs explicit Sam approval
  - business-policy decision (e.g., "should HR managers see warehouse PCF?" type role-mapping questions)
continue_without_pause_through:
  - phase execution
  - defect fix PR creation
  - L3 evidence write
  - rollback
  - registry update
blocker_policy:
  - programmatic -> fix and continue
  - 3x repeated technical failure on the same approach -> STOP, present options, wait for Sam
  - business-data/policy -> STOP
  - shared-state race in concurrent test -> fix and continue
signoff_authority: single-owner
canonical_closeout_artifacts:
  - output/l3/s177/RUN_STATUS.json
  - output/l3/s177/RUN_SUMMARY.md
  - output/l3/s177/DEFECT_REGISTER.md
  - output/l3/s177/form_submissions.json
  - output/l3/s177/api_mutations.json
  - output/l3/s177/state_verification.json
  - output/l3/s177/screenshots/<phase>/<scenario>.png
  - docs/plans/2026-04-09-sprint-177-pcf-full-e2e-closeout.md
  - docs/plans/SPRINT_REGISTRY.md
```

---

## Agent Boot Sequence

1. **Read this plan fully.** The PROOF + Remaining Gaps sections are the mental model.
2. **Create sprint branch:** `git fetch origin production && git checkout -b s177-pcf-full-e2e-closeout origin/production`. NEVER write code on production.
3. Read `docs/plans/SPRINT_REGISTRY.md` row for S177 and confirm the branch name matches.
4. Read `output/l3/s167/DEFECT_REGISTER.md` (final resolution summary section) to avoid re-surfacing already-closed defects.
5. Read `scripts/s167_lib.js` to understand the shared helpers (login, shot, attachNetwork, recordForm, recordState, recordDefect). Every S177 Playwright script reuses this lib.
6. Read `scripts/s167_ssm_run.py` + `scripts/s167_ssm_run_with_arg.py` — the SSM runner pattern for backend probes.
7. Read `hrms/api/pcf.py` lines 880-1000 (`request_replenishment` + `_create_replenishment_journal_entry`) — Phase 1 target.
8. Read `frappe_docker_build/images/bench/Dockerfile` — Phase 8 target.
9. Confirm Doppler has `OPENAI_API_KEY` (already verified 2026-04-09 in this session).
10. Run `doppler run --project bei-erp --config dev -- python scripts/s167_ssm_run.py scripts/s167r_handoff_snapshot.py` to snapshot current prod state. Save output to `output/l3/s177/baseline_snapshot.json`.
11. **Only after steps 1-10:** begin Phase 0.

---

## Design Rationale (For Cold-Start Agents)

**Why this exists:**
S167 ran a 22-scenario acceptance test against the PCF system with browser-only discipline. All 28 defects were resolved (`output/l3/s167/DEFECT_REGISTER.md`). But on 2026-04-09, Sam asked "is PCF accepted and ready to be used by real users today?" and the honest answer was "functionally working, but 7 real-user paths weren't tested." Sam's response: "run the full cycle and fix any remaining bugs, feature should work end to end."

**Why 8 gaps, not 7:** the 7 gaps in the narrative are user-visible flows. Gap 8 (DEFECT-029 persistence via Dockerfile bootstrap) is infrastructure — without it, the OpenAI classifier config is lost on any container teardown. If we leave that unfixed, the S167 DEFECT-009 chain becomes fragile again the next time the Frappe image is rebuilt from scratch.

**Why not split into multiple sprints:** the 8 gaps are tightly coupled — Gap 1 (replenishment) needs a fund and an approved batch. Gap 2 (receipt upload) needs a fund. Gap 4 (threshold notification) needs a fund with pending expenses. Running them in one session with one fund lifecycle is more efficient than separate sprints. Total is 76 units, under the 80-unit ceiling.

**Why browser-only for most phases but SSM for some:**
- Gap 1 (replenishment) — browser-click Approve, then SSM-probe the Journal Entry because no UI shows GL entries yet.
- Gap 4 (Chat notification) — browser-click add expense to cross threshold, then SSM-check the cron log + Chat webhook call.
- Gap 7 (month-end cron) — pure SSM because there's no UI to trigger a cron; must time-travel the scheduler.
- Everything else is browser because that's what the real user does.

**Why Playwright emulation for mobile (not real devices):**
Playwright's device emulation is good enough for layout + touch-event verification. Real-device testing requires BrowserStack or physical phones, which are out of scope for this sprint. If mobile reveals layout bugs, they get fixed in the same session.

**Key trade-offs already decided:**
- Concurrent-user race detection uses 2 Playwright contexts, not load-testing frameworks. If the race surfaces in 2 users, it'll surface in 20; if it doesn't surface in 2, it's probably unreachable without more aggressive tooling.
- Month-end cron is verified by `frappe.utils.data.nowdate()` monkey-patch within an SSM script, not by changing OS clock.
- Dockerfile bootstrap reads env at container start time (not build time) so the key isn't baked into the image.

**Known limitations:**
- Real carrier networks (3G/4G throttling) aren't simulated — if the receipt upload is slow on real phones, that's a separate perf-test sprint.
- No load test beyond 2-3 concurrent users.
- No GL reconciliation beyond DM-1 through DM-6 spot-checks.

---

## Requirements Regression Checklist

Before writing code, confirm:

- [ ] Every new/modified `@frappe.whitelist()` endpoint calls `set_backend_observability_context()` per `.claude/rules/sentry-observability.md`.
- [ ] Module parameter = `"pcf"`, action parameter = the function name.
- [ ] Every browser mutation goes through `page.getByRole('button').click()` + `waitForResponse` — NO `page.request.post`, NO in-page `fetch()`, NO synthetic API calls.
- [ ] Every SSM script prints actual values from `frappe.db.get_value()` / `frappe.db.sql()` — not inferred values.
- [ ] The PCF cash Dr row has `party_type="Employee"` + `party=<custodian_employee_id>` (DM-1). Source row is a Bank/Cash account with no party (internal cash movement).
- [ ] `request_replenishment` wraps its mutation span in `frappe.db.savepoint("pcf_replenish")` with rollback on exception, AND the `frappe.db.commit()` is moved to AFTER the final `set_value` (DM-2).
- [ ] DM-3 (EWT + VAT) is DOCUMENTED NON-APPLICABLE per PD-1 — PCF replenishment is a cash swap, not a withholding event. EWT/VAT are handled at the original supplier invoice booking upstream.
- [ ] No stored duplicate fields introduced (DM-5).
- [ ] Phase 6 rollback leaves zero orphans (verify via `scripts/s167_audit_orphans.py` — 0 BEI PCF Batch Item orphans, 0 dangling `pcf_batch` references).
- [ ] No existing S167 script is modified without a `# S177: ...` comment explaining why.
- [ ] Dockerfile changes in Phase 8 do not break existing bench initialization.
- [ ] Every new script under `scripts/s177r_*.js` or `scripts/s177r_*.py` follows the naming convention and reuses `s167_lib.js` for browser scripts.

---

## Zero-Skip Enforcement

Every scenario below MUST be executed in real browser or SSM. If the agent cannot execute a scenario, the agent STOPS and asks Sam.

**Forbidden behaviors:**
- Skipping a scenario and marking "deferred to next sprint"
- Replacing a scenario with a simpler version without Sam's approval
- Claiming a mobile-viewport scenario passed after running in desktop viewport
- Claiming a concurrent-user scenario passed without running 2+ Playwright contexts
- Using `page.request.post` to fake a mutation
- Marking a phase complete without writing the verification script output to `output/l3/s177/verify_phase<N>.log`

**Phase Completion Checklist format:**
Every phase ends with a checklist file `output/l3/s177/phase<N>_checklist.md`:

```
| Scenario | Status | Evidence | Skipped? | If skipped, why? |
|---|---|---|---|---|
| 1.1 approve HR batch (prereq) | PASS | form_submissions.json entry 1.1 | No | |
| 1.2 call request_replenishment | PASS | api_mutations.json response 200 | No | |
| 1.3 verify JE exists with party_type | PASS | SSM output in verify_phase1.log | No | |
...
```

**Verification script per phase:** `scripts/s177r_verify_phase<N>.py` — reads the phase's evidence files and prints PASS/FAIL per scenario. Exits non-zero on any FAIL.

---

## L3 Workflow Scenarios

Every scenario specifies exact user, exact action, exact outcome, exact failure meaning, **and machine-verifiable assertions (MUST_MODIFY / MUST_CONTAIN / HARD BLOCKER)** so the phase gate script verifies completion from filesystem rather than agent self-report. Closes S154 corrupt-success risk.

### Phase 0 — Preconditions + baseline snapshot + policy probes

**Phase 0 Verification Contract:**
- `MUST_CREATE: output/l3/s177/baseline_snapshot.json`
- `MUST_CREATE: output/l3/s177/phase0_probes.json`
- `HARD BLOCKER: chat_space_erp_automation is not None` (Phase 4 cannot run without a real Chat space)
- `HARD BLOCKER: fallback_source_account is not None` (Phase 1 cannot run without a cash account)
- `verify_script: scripts/s177r_verify_phase0.py`

| # | User | Action | Expected Outcome |
|---|---|---|---|
| 0.1 | sam (browser) | Run `scripts/s177r_phase0_1.js` (wraps s167r_phase0_1.js) → creates 3 dept funds + enables each via switch click | 3 funds exist + `is_enabled=1` via SSM |
| 0.2 | SSM | `scripts/s177r_realign_emps.py` — realign test employees to match dept funds | 3 employee depts realigned |
| 0.3 | SSM | Set `frappe.db.set_value("BEI Petty Cash Fund", "PCF-HR and Admin", "month_end_auto_submit", 1)` | flag set on HR fund (required for Phase 7) |
| 0.4 | SSM probe | Print BEI Settings `pcf_replenishment_source_account` + Company `default_cash_account` fallback → save to `phase0_probes.json` | fallback non-null |
| 0.5 | SSM probe | `from hrms.utils.bei_config import get_chat_space, SPACE_ERP_AUTOMATION; print(repr(get_chat_space(SPACE_ERP_AUTOMATION)))` → save to `phase0_probes.json` | **HARD BLOCKER if None/raises** |
| 0.6 | SSM | `scripts/s167_ssm_run.py scripts/s167r_handoff_snapshot.py` → `output/l3/s177/baseline_snapshot.json` | file exists, non-empty |

### Phase 1 — Replenishment DM-1/DM-2 retrofit + e2e verify

**Phase 1 Verification Contract:**
- `MUST_MODIFY: hrms/api/pcf.py` (must appear in `git diff --name-only`)
- `MUST_CONTAIN: "set_backend_observability_context" inside def request_replenishment`
- `MUST_CONTAIN: "\"party_type\": \"Employee\"" inside _create_replenishment_journal_entry`
- `MUST_CONTAIN: "frappe.db.savepoint(\"pcf_replenish\")" inside def request_replenishment`
- `MUST_NOT_CONTAIN: "frappe.db.commit()" BEFORE the final set_value call inside def request_replenishment` (commit must move AFTER set_value)
- `HARD BLOCKER: DM-3 EWT/VAT is DOCUMENTED NON-APPLICABLE per PD-1 — do NOT add EWT Payable or Input VAT lines`
- `HARD BLOCKER: cash flows FROM source TO PCF — source is CREDITED, PCF cash 1113000 is DEBITED (never the reverse)`
- `HARD BLOCKER: Phase 1.5 is SSM-only per PD-4 — no Request Replenishment button exists`
- `verify_script: scripts/s177r_verify_phase1.py`

#### Phase 1 code tasks (BEFORE scenarios run)

| Task | File | Change | MUST_CONTAIN |
|---|---|---|---|
| 1A | `hrms/api/pcf.py::_create_replenishment_journal_entry` ~line 967 | Add `party_type="Employee"` + `party=<custodian_employee_id>` on PCF cash Dr row. Custodian employee ID resolved via `frappe.db.get_value("Employee", {"user_id": batch.custodian}, "name")`. Source row has no party (internal cash account). | `"party_type": "Employee"` inside the function |
| 1B | `hrms/api/pcf.py::request_replenishment` ~line 905-918 | Wrap mutation block in `frappe.db.savepoint("pcf_replenish")` with rollback-on-exception. Move `frappe.db.commit()` to AFTER the final `set_value` on `last_replenishment_date`. | `frappe.db.savepoint("pcf_replenish")` |
| 1C | `hrms/api/pcf.py::request_replenishment` ~line 880 | Add `set_backend_observability_context(module="pcf", action="request_replenishment", mutation_type="update", extras={"batch_name": batch_name})` as first line after docstring. | `set_backend_observability_context(` inside `def request_replenishment` |
| 1D | this plan file | Narrative fix: scenario 1.5 must say "source account CREDITED, PCF cash 1113000 DEBITED" (done in v2 amendments) | "source CREDITED" |

#### Phase 1 browser/SSM scenarios (AFTER code tasks)

| # | User | Action | Expected Outcome |
|---|---|---|---|
| 1.1 | test.staff (browser) | Add 3 store expenses (Mercury Drug ₱250, 7-Eleven ₱150, Globe ₱299) via `/dashboard/store-ops/pcf/add` | 3 expenses pending, 200 OK each |
| 1.2 | test.supervisor (browser) | Click Submit Batch | batch `status=Submitted`, total 699 |
| 1.3 | test.finance (browser) | `/review` → click fund → click batch → Run AI Classification | items classified with resolved Account names |
| 1.4 | test.finance (browser) | Approve with COA | batch `status=Approved` (prereq for 1.5) |
| 1.5 | **SSM only (per PD-4)** | `bench execute hrms.api.pcf.request_replenishment --kwargs '{"batch_name":"<from 1.4>"}'` | returns `{"success": True, "journal_entry": "<JE-name>"}` |
| 1.6 | SSM probe | Read JE accounts — assert PCF cash 1113000 is DEBITED, source account is CREDITED; PCF cash row has `party_type == "Employee"` AND `party` equals the custodian's Employee ID; `reference_type`/`reference_name` point to batch | all assertions pass |
| 1.7 | SSM probe | `last_replenishment_date` is today; `pending_total` is 0 | state matches |
| 1.8 | SSM negative | Temporarily mock `_get_account_by_number` to return None for 1113000 → call `request_replenishment` → expect error returned AND `batch.replenishment_requested` STILL 0 (no half-state — savepoint rolled back) | half-state prevented |
| 1.9 | SSM observability | `grep "set_backend_observability_context" hrms/api/pcf.py` shows call inside `def request_replenishment` | Sentry context wired |

### Phase 2 — Receipt upload stress (locked selectors + Vercel body assertion)

**Phase 2 Verification Contract:**
- `MUST_CONTAIN: "#pcf_receipt_photo" in scripts/s177r_phase2.js` — real DocumentUploadField selector
- `MUST_CONTAIN: postData().length OR content-length assertion <4.5 MB` — Vercel body-limit guard
- `HARD BLOCKER: HEIC outcome is "picker rejects OR clear error" per PD-3 — both PASS`
- `HARD BLOCKER: do NOT test >10 MB files (alert() client cap per PD-3)`
- `verify_script: scripts/s177r_verify_phase2.py`

| # | User | Action | Expected Outcome |
|---|---|---|---|
| 2.1 | test.staff | Upload 2 MB JPG via `page.locator('#pcf_receipt_photo').setInputFiles(...)` | 200 OK, POST body <4.5 MB via `waitForRequest` + `postData().length` assertion |
| 2.2 | test.staff | Upload 5 MB JPG | 200 OK, POST body <4.5 MB (canvas downscale verified) |
| 2.3 | test.staff | Upload 8 MB JPG | 200 OK, POST body <4.5 MB (canvas resize to 1800px/0.85 active) |
| 2.4 | test.staff | Upload `.heic` file | EITHER OS picker rejects (Playwright throws) OR client alert fires — both PASS per PD-3 |
| 2.5 | test.staff | Upload 1 MB PDF | 200 OK (PDF is in `accept="image/*,.pdf"` but was never tested in S167) |
| 2.6 | test.staff | Attempt upload 11 MB JPG | Client `alert("File size must be less than 10MB")` fires, POST is NOT made — 10 MB cap proven |

### Phase 3 — Mobile viewport (locked Sidebar trigger + newMobileBrowser helper)

**Phase 3 Verification Contract:**
- `MUST_CREATE: scripts/s177_lib.js` with `newMobileBrowser(deviceName)` helper
- `MUST_CONTAIN: "devices['iPhone 13 Pro']" AND "devices['Pixel 7']" in scripts/s177r_phase3.js`
- `MUST_CONTAIN: exact SidebarTrigger selector locked per Boot Sequence step 15 (after reading sidebar.tsx)`
- `HARD BLOCKER: desktop viewport in Phase 3 = FAIL — mobile device emulation is required, verified via Chromium screenshot dimensions`
- `verify_script: scripts/s177r_verify_phase3.py`

| # | User | Viewport | Action | Expected Outcome |
|---|---|---|---|---|
| 3.1 | test.staff | iPhone 13 Pro (390×844) | Login → `SidebarTrigger` click → PCF → Add entry → fill → submit | full flow, no layout breakage, Submit button on screen |
| 3.2 | test.supervisor | iPhone 13 Pro | Inline edit 7-Eleven dialog → amount → Save | dialog fits, Save button reachable |
| 3.3 | test.finance | Pixel 7 (412×915) | Review queue → fund drilldown → batch review → Approve with COA | full path, COA cells usable |
| 3.4 | test.staff | iPhone 13 Pro | Upload 3 MB camera JPG | same result as Phase 2.2 |

### Phase 4 — Chat threshold notification (dual trigger: inline + hourly)

**Phase 4 Verification Contract:**
- `HARD BLOCKER: Phase 0.5 get_chat_space(SPACE_ERP_AUTOMATION) must be non-None`
- `MUST_CONTAIN: grep for BOTH success log ("Threshold notification sent for") AND failure log ("Failed to send threshold notification") in scripts/s177r_verify_phase4.py`
- `HARD BLOCKER: notification fires from TWO triggers per code reality — (a) inline from add_expense_to_pending at pcf.py:192, (b) hourly cron via check_threshold_and_notify. Test BOTH.`
- `verify_script: scripts/s177r_verify_phase4.py`

| # | User | Action | Expected Outcome |
|---|---|---|---|
| 4.1 | test.hr (browser) | Add expenses totaling ≥60% of HR fund (₱4,800 ≥ 60% of ₱8,000) | `pending_total` crosses threshold; inline `send_threshold_notification` fires from `add_expense_to_pending` |
| 4.2 | SSM probe | `frappe.get_all("Error Log", filters={"error":["like","%Threshold notification sent for PCF-HR%"]}, order_by="creation desc", limit=1)` — shows success log within last 60s | inline trigger confirmed |
| 4.3 | SSM invoke | `bench execute hrms.api.pcf.check_threshold_and_notify` (hourly cron path) — drive the second trigger directly | second notification attempt logged |
| 4.4 | manual + Chat | Open ERP_AUTOMATION Chat space, verify "Threshold reached" message is visible | real delivery confirmed (not just logged) |

### Phase 5 — Edge cases (real controls only, phantom scenarios removed)

**Phase 5 Verification Contract:**
- `HARD BLOCKER: no cancel_batch/cancel_draft/custodian-resubmit UI exists as of 2026-04-09 — do not hunt for phantom buttons`
- `MUST_CONTAIN: 'button[aria-label^="Remove expense"]' in scripts/s177r_phase5.js` — real delete selector
- `verify_script: scripts/s177r_verify_phase5.py`

| # | User | Scenario | Expected |
|---|---|---|---|
| 5.1 | test.staff (browser) | Add 3 pending expenses → click per-expense `button[aria-label="Remove expense Mercury Drug"]` → confirm → pending_total decrements | `remove_pending_expense` 200 OK, pending list updates |
| 5.2 | test.finance reject → test.staff new-batch workaround | Accountant rejects batch → custodian adds new expenses → submits a NEW batch (real-world workaround per PD-4 since no custodian-resubmit UI exists) | new batch `status=Submitted`, old batch stays `Rejected` |
| 5.3 | sam + test.hr (per PD-2) | Admin disables HR fund while test.hr has 2 pending expenses | Existing pendings stay visible; `add_expense_to_pending` returns 4xx "fund disabled"; test.hr CAN still submit existing batch |
| 5.4 | DEFECT log | Custodian-facing Request Replenishment button does NOT exist — log DEFECT-036 candidate for S178 | entry added to `output/l3/s177/DEFECT_REGISTER.md` |

### Phase 6 — Concurrent users (Promise.all + per-context mutation files)

**Phase 6 Verification Contract:**
- `MUST_CONTAIN: "Promise.all" in scripts/s177r_phase6.js` — genuine parallel execution
- `MUST_CREATE: scripts/s177_lib.js` provides per-context `attachNetwork` writing to `api_mutations_ctx<N>.json` (avoids race on shared file)
- `HARD BLOCKER: sequential awaits (await A; await B) are NOT a race — must use Promise.all([ctxA_click, ctxB_click])`
- `HARD BLOCKER: each scenario runs ≥10 iterations; PASS = 9/10 AND zero 500s AND pending_total reconciles every run`
- `verify_script: scripts/s177r_verify_phase6.py`

| # | Scenario | Expected |
|---|---|---|
| 6.1 | 10× iterations: 2 Playwright contexts via `Promise.all` both call `add_expense_to_pending` on the same store fund | All 20 adds succeed, `pending_total` reconciles per iteration, no 500s |
| 6.2 | 10× iterations: both contexts submit batch simultaneously via `Promise.all` | One wins 200 OK, other gets clean 4xx "batch already in progress", no 500s |
| 6.3 | 10× iterations: supv edits `7-Eleven 150→180` concurrently with staff adding Globe ₱299 | Both succeed, final pending math is exact |
| 6.4 | SSM SQL stress fallback | 5 parallel `add_expense_to_pending` SSM calls via `multiprocessing.Pool` — DB-level race test | All succeed, pending_total reconciles |

### Phase 7 — Daily job with inside-day guard at `last_day - 1` (NOT month-end cron)

**Phase 7 Verification Contract:**
- `HARD BLOCKER: monkey-patch target is hrms.api.pcf.datetime (via unittest.mock.patch), NOT frappe.utils.nowdate`
- `HARD BLOCKER: test date is last_day - 1 (second-to-last day of month), NOT last_day`
- `HARD BLOCKER: Phase 0.3 must have set month_end_auto_submit=1 (NOT auto_submit_enabled=1 — that's a different filter on a different function)`
- `HARD BLOCKER: no monkey-patch of datetime/nowdate may be committed to hrms/ files — only inside scripts/s177r_*.py`
- `MUST_CONTAIN: "unittest.mock.patch" AND "hrms.api.pcf.datetime" in scripts/s177r_phase7.py`
- `verify_script: scripts/s177r_verify_phase7.py`

| # | Action | Expected |
|---|---|---|
| 7.1 | SSM verify | Phase 0.3 set `month_end_auto_submit=1` on PCF-HR and Admin | flag is 1 |
| 7.2 | SSM probe | Read `hrms/hooks.py` lines 360-440, assert `"hrms.api.pcf.check_month_end_auto_submit"` under `"daily"` at line 425 | registration confirmed (already exists) |
| 7.3 | SSM mock | `with unittest.mock.patch("hrms.api.pcf.datetime") as mock_dt: mock_dt.now.return_value = datetime(2026, 4, 29)` (2026-04-30 is last_day, so 29 is last_day-1) → call `hrms.api.pcf.check_month_end_auto_submit()` directly | function enters auto-submit branch |
| 7.4 | SSM verify | New batch created on HR fund with `status=Submitted`, pending expenses rolled into it | cron logic works |

### Phase 8 — DEFECT-029 persistence via `hrms/hooks.py::before_migrate` hook (NOT Dockerfile)

**Phase 8 Verification Contract:**
- `MUST_MODIFY: hrms/hooks.py` (add before_migrate entry)
- `MUST_CREATE: hrms/utils/bei_openai_bootstrap.py` with `sync_openai_key_from_env()` function
- `MUST_CONTAIN: "before_migrate" in hrms/hooks.py` AND `"openai_api_key" in hrms/utils/bei_openai_bootstrap.py`
- `HARD BLOCKER: do NOT edit frappe_docker_build/images/bench/Dockerfile — it is a dev builder, no ENTRYPOINT/CMD (verified by audit 2026-04-09)`
- `HARD BLOCKER: bootstrap must be idempotent — running twice must not corrupt site_config.json`
- `HARD BLOCKER: bootstrap must NOT clear an existing non-empty openai_api_key if env var is empty (no silent overwrite)`
- `verify_script: scripts/s177r_verify_phase8.py`

| # | Action | Expected |
|---|---|---|
| 8.1 | Code | Create `hrms/utils/bei_openai_bootstrap.py::sync_openai_key_from_env()` — reads `os.environ.get("OPENAI_API_KEY")`, calls `frappe.installer.update_site_config("openai_api_key", value)` ONLY if non-empty. No-op if env unset. | helper exists, imports clean |
| 8.2 | Code | Register in `hrms/hooks.py` under `before_migrate = ["hrms.utils.bei_openai_bootstrap.sync_openai_key_from_env"]` (append to existing list if present) | hook registered |
| 8.3 | Local test | `bench --site hq.bebang.ph migrate` with `OPENAI_API_KEY` env var set → verify `site_config.json` has the key | integration works |
| 8.4 | Idempotency test | Run `bench migrate` twice → verify `site_config.json` is valid JSON with single key entry | no corruption |
| 8.5 | Empty env test | Run `bench migrate` with `OPENAI_API_KEY` unset → existing `site_config.json` key NOT cleared | no silent overwrite |
| 8.6 | SSM prod verify | After deploy: `docker exec frappe_backend bench --site hq.bebang.ph migrate` → key still present | prod migration clean |

### Phase 9 — Rollback + closeout

**Phase 9 Verification Contract:**
- `MUST_MODIFY: docs/plans/2026-04-09-sprint-177-pcf-full-e2e-closeout.md` (status PLANNED → COMPLETED)
- `MUST_MODIFY: docs/plans/SPRINT_REGISTRY.md` (S177 row status + PR number)
- `HARD BLOCKER: git add -f for output/l3/s177/ AND docs/plans/ (both may be gitignored)`
- `HARD BLOCKER: orphan audit returns 0 BEI PCF Batch Item orphans + 0 dangling pcf_batch references`
- `verify_script: scripts/s177r_verify_phase9.py`

| # | Action |
|---|---|
| 9.1 | `scripts/s177r_phase9_rollback.py` — delete S177 batches/expenses/funds |
| 9.2 | Restore 3 employee depts to originals |
| 9.3 | Run `scripts/s167_audit_orphans.py` — assert 0 orphans |
| 9.4 | Update plan YAML: `status: COMPLETED`, fill `completed_date`, fill `execution_summary` |
| 9.5 | Update `SPRINT_REGISTRY.md` row: status COMPLETED + PR number |
| 9.6 | `git add -f docs/plans/2026-04-09-sprint-177-pcf-full-e2e-closeout.md docs/plans/SPRINT_REGISTRY.md output/l3/s177/` — explicit path enumeration |
| 9.7 | `git commit` + `git push origin s177-pcf-full-e2e-closeout` |
| 9.8 | PR #517 auto-updates with new commits. Share updated state with Sam. STOP per PR-Handoff rule. |

---

## Execution Workflow

- Test Python changes: `/local-frappe` (for request_replenishment work)
- Deploy Frappe: `/deploy-frappe` (if any hrms/api/pcf.py changes)
- Full workflow: `/agent-kickoff`
- E2E: `/e2e-test`

Deployment is user-mediated (Sam merges + deploys). Agent stops at PR creation.

---

## Sentry Observability

All new `@frappe.whitelist()` endpoints or significant modifications to existing ones in this sprint MUST call `set_backend_observability_context()`:

```python
from hrms.utils.sentry import set_backend_observability_context
set_backend_observability_context(
    module="pcf",
    action="<function_name>",
    mutation_type="create" | "update" | "read",
    extras={"batch_name": batch_name},  # or relevant context
)
```

Affected functions likely touched in Phase 1:
- `hrms/api/pcf.py::request_replenishment` — MUST add observability
- `hrms/api/pcf.py::_create_replenishment_journal_entry` — private helper, no observability needed

Frontend API routes are auto-instrumented by `@sentry/nextjs`. No new backend routes expected.

---

## Anti-Rewind / Concurrent-Run Protection Contract

```yaml
ownership_matrix:
  artifact: output/l3/s177/S177_SURFACE_OWNERSHIP_MATRIX.csv
  owned_files:
    - hrms/api/pcf.py (ONLY request_replenishment + _create_replenishment_journal_entry — party fields, savepoint, commit reorder, Sentry context)
    - hrms/hooks.py (Phase 8: add before_migrate hook entry)
    - hrms/utils/bei_openai_bootstrap.py (Phase 8: NEW file)
    - scripts/s177r_*.js + scripts/s177r_*.py (all NEW)
    - scripts/s177_lib.js (Phase 3/6: NEW, mobile + per-context helpers)
    - output/l3/s177/* (all NEW)
    - docs/plans/2026-04-09-sprint-177-pcf-full-e2e-closeout.md
    - docs/plans/SPRINT_REGISTRY.md (S177 row + Next Sprint Reservation)
  do_not_touch:
    - frappe_docker_build/images/bench/Dockerfile (dev builder, NOT runtime — Phase 8 uses hrms/hooks.py instead per Amendment B)
    - scripts/s167_lib.js (Phase 3/6 creates scripts/s177_lib.js instead of modifying S167 lib, per Requirements Regression Checklist line 275)
protected_surfaces:
  - hrms/api/pcf.py::classify_batch_items at line ~1077 (owned by S167 PR #513, do not touch)
  - hrms/api/pcf.py::_resolve_coa_code_to_account (owned by S167 PR #510+#513, do not touch)
  - hrms/api/pcf.py::check_month_end_auto_submit at line 1507 (DO NOT modify — Phase 7 only monkey-patches in test scripts, never in this file)
  - hrms/api/pcf.py::check_threshold_and_notify at line ~1479 (DO NOT modify — Phase 4 verifies, never modifies)
  - hrms/api/pcf.py::send_threshold_notification at line 1641 (DO NOT modify — Phase 4 verifies)
  - hrms/api/pcf.py::add_expense_to_pending (DO NOT modify — already calls send_threshold_notification inline at pcf.py:192)
  - bei-tasks/components/pcf/* (owned by S167 PRs #357/#358/#359/#360/#361)
  - bei-tasks/components/layout/nav-main.tsx PCF sidebar groups (owned by S167 #367+#370)
  - bei-tasks/app/dashboard/accounting/pcf/review/fund/[fund_name]/page.tsx (owned by S167 #367)
  - bei-tasks/components/pcf/pcf-legacy-redirect.tsx (owned by S167 #367)
  - frappe_docker_build/** (Phase 8 does NOT edit any file in this tree — uses hrms/hooks.py instead)
remote_truth_baseline:
  artifact: output/l3/s177/S177_REMOTE_TRUTH_BASELINE.json
  captured_at_phase_0: true
  fields:
    - repo: Bebang-Enterprise-Inc/hrms
    - release_branch: production
    - release_head_sha: <captured in Phase 0>
    - bei_tasks_release_head_sha: <captured in Phase 0>
    - s167_pr_numbers: [510, 512, 513, 516, 367, 370]
active_run_coordination:
  artifact: output/l3/s177/state/S177_ACTIVE_RUN_COORDINATION.json
  rule: claim on start, release on closeout
pretouch_backup:
  artifact: output/l3/s177/state/S177_PRETOUCH_BACKUP.json
  rule: before mutating hrms/api/pcf.py OR Dockerfile, snapshot file SHAs
```

---

## Signoff Model

```yaml
mode: single-owner
approver_of_record: Sam (CEO)
signoff_artifact: output/l3/s177/RUN_SUMMARY.md
rule: Sam reviews closeout PR comments. No synthetic department-signoff rows.
```

---

## Status Reconciliation Contract

Whenever counts, blockers, stage, or certification status changes during execution, update in the same work unit:
1. `output/l3/s177/RUN_STATUS.json`
2. `output/l3/s177/RUN_SUMMARY.md`
3. `output/l3/s177/DEFECT_REGISTER.md`
4. This plan's `execution_summary` field (within YAML metadata block at top)
5. `docs/plans/SPRINT_REGISTRY.md` row

---

## Certification Coverage Contract

```yaml
certified_universe:
  gaps: 8
  phases: 10  # Phase 0 + 8 gap phases + Phase 9 closeout
  scenarios: 48  # sum of all L3 Workflow Scenarios table rows after v2 amendments
  # Breakdown: P0=6, P1=9 (4 code tasks + 5 browser/SSM), P2=6, P3=4, P4=4, P5=4, P6=4, P7=4, P8=6, P9=8
closeout_zero_equations:
  gaps_open_after_closeout: 0
  scenarios_skipped: 0
  scenarios_failing: 0
  orphan_records_post_rollback: 0
  new_HIGH_or_CRITICAL_defects_unresolved: 0
allowed_skips:
  - only with Sam's explicit written approval via PR comment
final_readiness_basis:
  - output/l3/s177/RUN_STATUS.json passed = true
  - output/l3/s177/DEFECT_REGISTER.md final_defects_open = 0 HIGH/CRITICAL
  - output/l3/s177/form_submissions.json entries ≥ 28 (browser-only scenarios after v2 amendments — SSM-only rows like Phase 1.5-1.9, 4.2-4.3, 7.1-7.4, 8.1-8.6 are counted in state_verification.json instead)
  - output/l3/s177/api_mutations.json 200 OK responses ≥ expected count
  - orphan audit output showing 0 BEI PCF Batch Item + 0 dangling pcf_batch
```

---

## Scope Size Warning

Current estimate: **76 units across 10 phases**. This is within the 80-unit hard ceiling but close enough that:

- If any phase (especially Phase 1 or Phase 8) exceeds its budget by >30%, the agent must stop and notify Sam before proceeding.
- If Phase 1 (replenishment) uncovers DM-1/DM-2/DM-3 violations that require substantial hrms/api/pcf.py refactoring, that becomes its own sprint (S178) and S177 stops at "DEFECT logged, fix deferred".

---

## Risks + Known Unknowns (after 2026-04-09 audit pass, v2 amendments)

1. **Phase 1.5 `request_replenishment` is SSM-only per PD-4.** No UI button exists (grep confirmed). Backend call via `bench execute`. Browser-proved column will be "N/A — SSM-only". Follow-up DEFECT-036 candidate: add custodian-facing Request Replenishment button in a future sprint.
2. **Chat space existence is a HARD BLOCKER (Phase 0.5)** — if `get_chat_space(SPACE_ERP_AUTOMATION)` returns None, Phase 4 cannot run. Agent STOPS and asks Sam to configure the space before resuming. Space ID is in `hrms.utils.bei_config::SPACE_ERP_AUTOMATION`.
3. **Phase 7 monkey-patch must target `hrms.api.pcf.datetime`** via `unittest.mock.patch`. Target is NOT `frappe.utils.nowdate`. Test date is `last_day - 1` (second-to-last day). Patching only works in-process for the function invocation from the test script — not for real scheduler runs.
4. **Phase 8 `hrms/hooks.py::before_migrate` hook requires careful idempotency** — the bootstrap must be a no-op if the env var is unset AND must not silently clear an existing key. Tested via 8.4/8.5 scenarios. Fails-safe.
5. **Concurrent-user race may be masked by Playwright's single-process model.** Phase 6 uses `Promise.all` across 2 contexts AND a 5-worker `multiprocessing.Pool` SSM fallback. If neither reproduces a race across 10 iterations, classify as "not-reproducible-in-test-harness, monitor prod via Sentry" and move on.
6. **Replenishment JE party resolution edge case** — the custodian's employee ID is derived via `frappe.db.get_value("Employee", {"user_id": batch.custodian}, "name")`. If the custodian user has no Employee record (like test.finance per S167), the JE party cannot be set and Phase 1.8 negative path must cover this.
7. **Phase 1 DM-1 code change is narrow** — only 2 param assignments + 1 savepoint wrap + 1 `commit()` move + 1 Sentry context call. Total change ≤30 LOC in `hrms/api/pcf.py`. If the code change exceeds 100 LOC, STOP and convert to S178 per Scope Size Warning.
8. **PR #517 already exists against production** — this amendment pass updates the same branch, so the PR description should be refreshed via `gh pr edit 517` at closeout, not a new PR.

---

## PR Creation Rules (PR-Handoff)

Per `.claude/rules/core-governance.md` and CLAUDE.md, agents NEVER merge PRs or deploy. At the end of Phase 9:

1. Create PR against `production` with `gh pr create --repo Bebang-Enterprise-Inc/hrms --base production --head s177-pcf-full-e2e-closeout ...`
2. PR description must include:
   - Reference to this plan file
   - Per-phase PASS/FAIL summary
   - Any new defects discovered with severity
   - Link to evidence files in `output/l3/s177/`
3. Share PR number via chat + STOP. Do not deploy.

---

## Amendment Log

### v2 — 2026-04-09 (Amendments A-K, audit response)

Applied after `/audit-plan-bei-erp` full pass (6 domain agents + code-verifier + adversarial fact-checker) identified 12 SUPPORTED blockers + 2 policy-gated findings + 1 unverified. All 15 addressed in-place while preserving all 8 gap scopes. Authoritative sections updated: Phase Budget Contract, L3 Workflow Scenarios, Agent Boot Sequence, Requirements Regression Checklist, Anti-Rewind Protection, Risks, Certification Coverage Contract.

**Amendments applied:**

- **A (Branch handling)** — Agent Boot Sequence Step 2 now handles pre-existing `s177-pcf-full-e2e-closeout` branch via conditional `show-ref` check + `reset --hard`. Previously would have failed with `fatal: A branch named '...' already exists`.
- **B (Phase 8 retarget)** — Phase 8 now adds a `before_migrate` hook in `hrms/hooks.py` + a new `hrms/utils/bei_openai_bootstrap.py` helper. Does NOT edit `frappe_docker_build/images/bench/Dockerfile` (which is a dev builder with no ENTRYPOINT/CMD — verified by code-verifier CF-8). This survives container rebuilds without forking the Docker image.
- **C (Phase 7 strategy)** — Monkey-patch target changed from `frappe.utils.nowdate` to `hrms.api.pcf.datetime` via `unittest.mock.patch`. Test date changed from `last_day` to `last_day - 1`. Removed "cron may not be registered" hedge (it IS registered at `hrms/hooks.py:425` under `daily`).
- **D (Phase 1 build+verify)** — Phase 1 increased 12 → 15 units. Added 4 explicit code tasks (1A party fields, 1B savepoint + commit reorder, 1C Sentry context, 1D scenario 1.5 narrative fix). Added negative test 1.8 (missing 1113000 account) and observability check 1.9. DM-3 documented non-applicable per PD-1.
- **E (Phase 5 phantom removal)** — Deleted "Cancel Draft batch" (no backend action exists), deleted "Draft batch approval" (no such state). Kept remove-pending-expense (real control: `button[aria-label^="Remove expense"]`). Rejected-batch resubmit downgraded to "new batch workaround" (no custodian-facing resubmit UI). Custodian Request Replenishment logged as DEFECT-036 candidate.
- **F (Phase 0 expansion)** — Phase 0 increased 4 → 6 units. Added 3 SSM probes: BEI Settings source account fallback, `get_chat_space(SPACE_ERP_AUTOMATION)` existence, `month_end_auto_submit=1` flag set on HR fund. Baseline snapshot captured to `baseline_snapshot.json`.
- **G (Machine-verifiable phase gate)** — Every phase now has a Verification Contract block with `MUST_MODIFY` / `MUST_CONTAIN` / `MUST_CREATE` / `MUST_NOT_CONTAIN` / `HARD BLOCKER` assertions. Each phase has a named `scripts/s177r_verify_phaseN.py` that reads filesystem evidence (git diff + grep), not agent prose. Closes S154 corrupt-success risk.
- **H (Housekeeping)** — Fixed unit count mismatch (registry said 70, plan said 76 — now 76 everywhere). Clarified `depends_on` to list real merged PRs (#510, #512, #513, #367, #370). Fixed "7 paths" vs "8 gaps" narrative inconsistency.
- **I (Phase 6 concurrency fix)** — Mandated `Promise.all` for genuine parallel execution. Replaced shared `api_mutations.json` with per-context files (`api_mutations_ctx1.json`, `api_mutations_ctx2.json`) via new `scripts/s177_lib.js`. Each scenario runs ≥10 iterations; PASS = 9/10 + zero 500s. Added SSM-level 5-worker `multiprocessing.Pool` SQL stress fallback.
- **J (Phase 2 selectors + PDF)** — Locked `#pcf_receipt_photo` selector + Vercel body-limit assertion (POST body <4.5 MB verified via `waitForRequest` + `postData().length`). Added 2.5 PDF scenario and 2.6 explicit 11 MB `alert()` cap verification. HEIC policy per PD-3.
- **K (Mobile Sidebar trigger)** — Added Agent Boot Sequence step 15 to read `components/ui/sidebar.tsx` + `nav-main.tsx` and lock `SidebarTrigger` selector before writing Phase 3 script. `newMobileBrowser(deviceName)` helper must live in `scripts/s177_lib.js`, NOT by modifying `s167_lib.js`.

**Policy decisions captured as PD-1 through PD-4** (top of plan):
- PD-1: PCF replenishment is cash-swap, not withholding event (closes Blockers 6 + 7).
- PD-2: Fund-disabled-mid-submission semantics (pending stays visible + submittable, new adds 4xx).
- PD-3: HEIC + 10 MB cap accepted for MVP.
- PD-4: Phase 1.5 is SSM-only (no UI button exists).

**Feature capabilities preserved:** all 8 gaps still in scope. Zero scope cuts. The amendments are narrower and more precise, not smaller.

**Net unit delta:** still 76 units (Phase 1 +3, Phase 0 +2, Phase 2 +0, Phase 4 -2, Phase 5 -2, Phase 6 +1, Phase 7 +0, Phase 8 -2 = net 0). Phase sizes now better-matched to actual work.

---

## End of plan
