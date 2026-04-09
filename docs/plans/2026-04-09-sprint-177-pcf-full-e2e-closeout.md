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

S167 REDO proved the PCF happy path works end-to-end in browser. But S167's scope was the happy path. There are **7 real-user paths** that S167 did not exercise. A real BEI crew member rolling out this feature will hit these paths on day one. This sprint closes each gap with browser or SSM evidence, fixes any bugs found, and gives Sam a factual green-light decision for full rollout (45 stores + all dept custodians).

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
- [ ] Every new Journal Entry created in Phase 1 has `party_type` + `party` on ALL rows (DM-1).
- [ ] Every multi-doc mutation uses `frappe.db.savepoint()` (DM-2).
- [ ] Every Payment-related feature addresses EWT + VAT treatment (DM-3).
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

Every scenario below specifies exact user, exact action, exact outcome, exact failure meaning.

### Phase 0 — Preconditions

| User | Action | Expected Outcome | Failure Means |
|---|---|---|---|
| sam | `scripts/s177r_phase0_setup.js`: run s167r_phase0_1.js equivalent + realign test emps via SSM | 3 dept funds created + enabled + employees aligned | S167 Phase 0.1 regressed or employees weren't restored by earlier rollback |

### Phase 1 — Replenishment flow

| # | User | Action | Expected Outcome | Failure Means |
|---|---|---|---|---|
| 1.1 | test.staff | Add 3 store expenses (Mercury Drug ₱250, 7-Eleven ₱150, Globe ₱299) via `/dashboard/store-ops/pcf/add` form + "Add to Pending" clicks | 3 expenses pending, 200 OK each | store add regressed |
| 1.2 | test.supervisor | Click Submit Batch on `/dashboard/store-ops/pcf/pending` | batch created, `status=Submitted`, total 699 | submit_batch_now regressed |
| 1.3 | test.finance | Navigate `/review` → click fund → click batch → click Run AI Classification | 3 items classified with resolved Account names (not naked codes) | DEFECT-009/029 regression |
| 1.4 | test.finance | Click Approve with COA | batch status Approved, 200 OK | approve path regressed |
| 1.5 | test.finance | **(SSM)** Call `request_replenishment(batch_name)` via browser's request button OR SSM | Journal Entry created with party_type + party on cash account row; source account debited, custodian bank credited | DM-1 failure (no party) OR missing source account OR JE not created |
| 1.6 | SSM probe | Verify JE has `accounts[].party = custodian`, `accounts[].party_type = "Employee"`, `reference_type`/`reference_name` pointing to batch | all rows compliant | DM-1/DM-6 broken |
| 1.7 | SSM probe | Verify `pending_total` on fund dropped by ₱699 after replenishment | fund balance restored | replenishment didn't credit fund |

### Phase 2 — Receipt upload stress

| # | User | Action | Expected Outcome | Failure Means |
|---|---|---|---|---|
| 2.1 | test.staff | Upload 2 MB JPG via `<input type=file>` → add expense | 200 OK, no 413 | downscale broken |
| 2.2 | test.staff | Upload 5 MB JPG | 200 OK after canvas downscale | DEFECT-023 regression |
| 2.3 | test.staff | Upload 8 MB JPG | 200 OK OR graceful "file too large" error with actionable message | no silent hang |
| 2.4 | test.staff | Upload .HEIC file | either transparent conversion OR clear "HEIC not supported, convert to JPG" error | silent failure = FAIL |

### Phase 3 — Mobile viewport

| # | User | Viewport | Action | Expected Outcome |
|---|---|---|---|---|
| 3.1 | test.staff | iPhone 13 Pro (390×844) | Login → navigate → open sidebar hamburger → PCF → Add entry → fill form → submit | full flow succeeds without layout breakage |
| 3.2 | test.supervisor | iPhone 13 Pro | Inline edit 7-Eleven dialog → amount field → save | edit dialog fits in viewport, Save button reachable |
| 3.3 | test.finance | Pixel 7 (412×915) | Review queue → fund drilldown → batch review → approve with COA | full path, COA input cells usable, Approve button not offscreen |
| 3.4 | test.staff | iPhone 13 Pro | Upload 3 MB camera JPG via file input | same result as Phase 2.2 |

### Phase 4 — Chat threshold notification

| # | User | Action | Expected Outcome | Failure Means |
|---|---|---|---|---|
| 4.1 | test.hr | Add expenses totaling ≥ 60% of HR fund (e.g., 5 × ₱700 = ₱3,500 ≥ ₱3,000) | pending_total crosses threshold | threshold math wrong |
| 4.2 | SSM probe | Read `frappe.log_error` or custom log for threshold notification attempt | log entry "threshold_reached notification sent" | notification never fired |
| 4.3 | manual + Chat API | Check actual Google Chat space for the delivered message OR `hrms/api/google_chat.py` call trace | real message posted, not just a log | webhook client broken |

### Phase 5 — Edge cases

| # | Scenario | Expected |
|---|---|---|
| 5.1 | Custodian adds expense → cancels before submitting batch | expense deleted via `remove_pending_expense`, pending_total decremented |
| 5.2 | Custodian submits batch → before accountant reviews, accountant rejects → custodian edits one expense → resubmits | new batch created, old batch stays Rejected, pending expenses flow through |
| 5.3 | Admin disables fund while custodian has 2 pending expenses | existing pending expenses stay visible to custodian; new `add_expense_to_pending` returns 4xx; batch submit still allowed? **Policy TBD — flag to Sam if unclear** |
| 5.4 | Accountant opens a Draft batch (never submitted) and tries to approve | either UI blocks or backend returns validation error |

### Phase 6 — Concurrent users

| # | Scenario | Expected |
|---|---|---|
| 6.1 | 2 Playwright contexts: test.staff adds expense A at t=0, test.supervisor adds expense B at t=0.1s | both succeed, `pending_total = A + B`, no race |
| 6.2 | Both submit batch simultaneously | one wins, other gets a clean "batch already in progress" error (not a 500) |
| 6.3 | test.supervisor edits 7-Eleven 150→180 while test.staff adds Globe 299 | both succeed, final pending matches 180+299 + any pre-existing |

### Phase 7 — Month-end auto-submit cron

| # | Action | Expected |
|---|---|---|
| 7.1 | SSM: set HR fund `month_end_auto_submit=1`, add 1 expense, monkey-patch `frappe.utils.nowdate()` to return last-day-of-month, call the daily scheduler hook manually | auto-submitted batch created for the expense |
| 7.2 | SSM: verify the scheduler entry exists in `hooks.py` and the function is registered | config-level correctness |

### Phase 8 — DEFECT-029 Dockerfile bootstrap

| # | Action | Expected |
|---|---|---|
| 8.1 | Edit `frappe_docker_build/images/bench/Dockerfile` (or entrypoint script) to read `OPENAI_API_KEY` env and jq-patch `site_config.json` on container start | new Dockerfile builds cleanly |
| 8.2 | Build new image locally, run container with env var, verify `site_config.json` has key | idempotent, safe |
| 8.3 | Document the Doppler integration so the env var is passed to the container at deploy time | ECS/K8s env mapping updated |

### Phase 9 — Rollback + closeout

| # | Action |
|---|---|
| 9.1 | Delete S177 batches/expenses/funds via `scripts/s177r_phase9_rollback.py` |
| 9.2 | Restore employee depts |
| 9.3 | Verify 0 orphans via orphan-check script |
| 9.4 | Update plan YAML `status: COMPLETED`, `completed_date`, `execution_summary` |
| 9.5 | Update SPRINT_REGISTRY.md row with PR number + status |
| 9.6 | `git add -f` evidence files, commit, push |
| 9.7 | `gh pr create` against production, share PR number, STOP (per PR-Handoff rule) |

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
    - hrms/api/pcf.py (only request_replenishment + _create_replenishment_journal_entry + add Sentry context)
    - frappe_docker_build/images/bench/Dockerfile (Phase 8)
    - scripts/s177r_*.js + scripts/s177r_*.py (new)
    - output/l3/s177/* (new)
    - docs/plans/2026-04-09-sprint-177-pcf-full-e2e-closeout.md
    - docs/plans/SPRINT_REGISTRY.md (S177 row + Next Sprint Reservation)
protected_surfaces:
  - hrms/api/pcf.py::classify_batch_items (owned by S167 PR #513, do not touch)
  - hrms/api/pcf.py::_resolve_coa_code_to_account (owned by S167 PR #510+#513)
  - bei-tasks/components/pcf/* (owned by S167 PRs #357/#358/#359/#360/#361)
  - bei-tasks/components/layout/nav-main.tsx PCF sidebar groups (owned by S167 #367+#370)
  - bei-tasks/app/dashboard/accounting/pcf/review/fund/[fund_name]/page.tsx (owned by S167 #367)
  - bei-tasks/components/pcf/pcf-legacy-redirect.tsx (owned by S167 #367)
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
  scenarios: 28  # sum of L3 Workflow Scenarios table rows
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
  - output/l3/s177/form_submissions.json entries ≥ 22 (matching L3 Workflow Scenarios row count minus SSM-only entries)
  - output/l3/s177/api_mutations.json 200 OK responses ≥ expected count
  - orphan audit output showing 0 BEI PCF Batch Item + 0 dangling pcf_batch
```

---

## Scope Size Warning

Current estimate: **76 units across 10 phases**. This is within the 80-unit hard ceiling but close enough that:

- If any phase (especially Phase 1 or Phase 8) exceeds its budget by >30%, the agent must stop and notify Sam before proceeding.
- If Phase 1 (replenishment) uncovers DM-1/DM-2/DM-3 violations that require substantial hrms/api/pcf.py refactoring, that becomes its own sprint (S178) and S177 stops at "DEFECT logged, fix deferred".

---

## Risks + Known Unknowns

1. **`request_replenishment` may not be wired to a UI button.** If not, Phase 1.5 becomes SSM-only, which is still valid but can't be called "browser-proved".
2. **Google Chat threshold notification may not exist in prod code at all.** If `hrms/api/pcf.py` has no `_send_threshold_notification()` call path, Gap 4 becomes a BUILD sprint, not a test sprint. Log as DEFECT-030 and defer.
3. **Month-end auto-submit cron may not be registered in `hooks.py`.** Similar — log as DEFECT-031 and defer.
4. **Dockerfile bootstrap may conflict with existing entrypoint.** Needs careful test in a local container before pushing.
5. **Concurrent-user race may be masked by single-region network latency.** If 2 contexts from the same machine can't reproduce the race, document as "not-reproducible-in-test-harness" and move on.

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

## End of plan
