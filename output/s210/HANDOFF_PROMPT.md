# S210 CONTINUATION HANDOFF

Paste the block below as your next prompt after `/compact`. The agent continues S210 from Phase 2.

---

## PROMPT TO PASTE AFTER COMPACT

Continue executing Sprint S210 (Tier A Receipt-Based Payment Infrastructure) from Phase 2. Everything you need is below — no prior conversation context required.

### Your identity and workspace

- Working directory: `F:\Dropbox\Projects\BEI-ERP`
- Platform: Windows 11, bash shell (use Unix-style paths in commands: `F:/Dropbox/...`)
- You are Claude, acting as the S210 execution agent. Sam Karazi (CEO, sam@bebang.ph) is the user and sole signoff.

### The plan — READ THIS FILE FIRST AND FULLY

```
F:\Dropbox\Projects\BEI-ERP\docs\plans\2026-04-20-sprint-210-tier-a-receipt-payment-infrastructure.md
```

That plan is cold-start ready: Design Rationale, Requirements Regression Checklist, Phase tables with MUST_MODIFY/MUST_CONTAIN assertions, L3 scenarios, Autonomous Execution Contract. Everything you need for execution decisions is in it.

### Current state

- Git branch: `s210-tier-a-receipt-payment-infrastructure` (2 commits: Phase 0 + Phase 1)
- Plan status: GO (declared in YAML, to be flipped to COMPLETED at Phase 6)
- Canonical scope: `none` (CEO-clarified — Google Workspace only; no Frappe mutations)
- Phases 0 + 1: ✅ DONE
- Phases 2, 3, 4, 5, 6: ⏳ PENDING — this is your work
- Budget remaining: ~48 work units across 5 phases

### Sheets already live (from Phase 1)

- **Sheet A** `BEI 3MD Receiving Log 2026`: `1dambmiLzSMWOQun7MCymK4nHpuqrarFCAOK0G9-6oIU`
- **Sheet B** `BEI Pinnacle Receiving Log 2026`: `10fqnvF_uDl5ky3MkvXUmWvZ1fYat_p6XFGmVFc3vqrw`
- Owner: `commissary.team@bebang.ph`
- BEI editors: ian, cayla, sam, jay, luwi (all @bebang.ph)
- 5 tabs each: `Receipts` (18-col schema), `Open_POs_*_Only`, `Suppliers_Visible`, `Materials`, `_Instructions`
- External editor (3MD contact for Sheet A, Pinnacle contact for Sheet B): pending from Ian/Jay

Full sheet ID inventory: `output/s210/SHEET_IDS.json`

### Other baseline artifacts from Phase 0

- `output/s210/PROCUREMENT_APPSHEET_BASELINE.json` — 23-tab schema of Procurement AppSheet (sheet ID `1QWdoZlT7XWLppfVKpJ2VRXhbMkYtE5TbUwg4lMbO03Q`, owned by sam@bebang.ph, read-only for us)
- `output/s210/LIBRARY_AUDIT.md`
- `output/s210/S210_SURFACE_OWNERSHIP.csv`
- `output/s210/S210_PROTECTED_SURFACES.csv`
- `output/s210/state/S210_REMOTE_TRUTH_BASELINE.json`
- `output/s210/state/S210_ACTIVE_RUN_COORDINATION.json`
- `output/s210/verify_phase_0.py` (returns 0 = PASS)
- `output/s210/verify_canonical_preflight.log` (1 pre-existing unrelated violation noted)

### Credentials

- Service account: `credentials/task-manager-service.json`
- Domain-wide delegation: YES (can impersonate any @bebang.ph user)
- Default impersonate for this sprint: `commissary.team@bebang.ph` (sheet owner)
- Sheets + Drive + Gmail + Chat APIs all work with this service account
- Chat space IDs (for onEdit notifications):
  - SCM: `spaces/AAQArCi8zjE`
  - Procurement App Notifications: `spaces/AAQAYAYwPPk`

### Remaining phases — work units budget

| Phase | Scope | Units |
|---|---|---:|
| 2 | Sheet C (`BEI Receiving Master 2026` — BEI-internal only, 9 tabs) + Sheet D (`BEI Shaw Transitional Receiving` — BEI-only, same 18-col schema) | 9 |
| 3 | Apps Script bound to Sheet C: `validateReceipt`, `handleNewReceipt_3MD`, `handleNewReceipt_Pinnacle`, `postChatNotification`, `ageVarianceQueue` + installable triggers on A/B + hourly cron + 06:00 cron | 12 |
| 4 | Google Form `BEI Supplier SI Upload` + per-supplier pre-filled URL generator + `handleSiUpload` onFormSubmit trigger + match logic | 10 |
| 5 | `sendCeoDailyEmail()` (07:00 PHT cron to sam + ian), Dashboard formulas, `refreshMasters()` (06:00 cron pulling from Procurement AppSheet), `verify_phase_5.py` | 8 |
| 6 | `ONBOARDING_3PL_COMMS.md`, E2E test (3MD dummy, Pinnacle dummy, supplier SI upload), `verify_phase_6.py`, plan YAML flip to COMPLETED, SPRINT_REGISTRY.md update, PR creation | 9 |

Every task in each phase has MUST_MODIFY / MUST_CONTAIN assertions in the plan — obey them. Write `output/s210/verify_phase_N.py` per phase, run it, require exit 0 before advancing.

### Non-negotiables (from plan's Requirements Regression Checklist + CEO decisions)

1. **Infrastructure is 4 separate Google Sheets** (A/B/C/D) — NEVER combine 3MD + Pinnacle tabs into one sheet. Access isolation is the whole point.
2. **Sheet C is BEI-internal only** — no external party gets ANY access, not even view.
3. **RCSI is phased out** — do not reference, do not build, do not list in any file you create.
4. **OR is NOT required** under EoPT Act — the flow must not treat OR as a payment gate or required document.
5. **No AppSheet** — this is Apps Script + Sheets + Forms only. CEO rejected AppSheet for this infrastructure.
6. **No Frappe code** — this sprint does not modify `hrms/api/*.py`, `hrms/hr/doctype/*`, or `bei-tasks/**`. Google Workspace only.
7. **Approval chain unchanged** — Luwi → Mae for all RFPs; CEO for > ₱1M. Automation produces RFP DRAFTS; humans still approve.
8. **Payment respects supplier Payment Terms** — the flow schedules payment for `Delivery Date + Supplier.Payment_Terms`. It does not pay on delivery.
9. **Bryan/Shaw not primary path** — 3MD is primary (Shaw storage moving to 3MD); Pinnacle secondary. The plan's Sheet D (Shaw transitional) is short-lived.
10. **Supplier SI upload is parallel stream** — supplier PDF upload is for compliance + speed, not for payment gating. DR → RFP is ERS-style receipt-based; SI match is post-facto reconciliation; variances non-blocking.

### Critical git rules (HARD LEARNED this session)

1. **Always check branch before committing.** Run `git branch --show-current` immediately before every `git commit`. If it prints `production`, STOP — switch to `s210-tier-a-receipt-payment-infrastructure` first.
2. **Hook blocks `git cherry-pick`** on this repo. Use `git reset --soft origin/production` + stash + branch switch if you need to move commits. Do not use cherry-pick.
3. **Never push to production.** Only push to `s210-tier-a-receipt-payment-infrastructure` branch.
4. **`git add -f` is required** — `docs/plans/` may be gitignored in places; force-add.
5. **Use `GH_TOKEN="" gh pr create ...`** for PR creation (keyring auth, not env PAT).
6. **Stash exists:** `git stash list` will show `s209-files-aside` — leave it alone; it's S209's files set aside during our branch recovery. Not S210's problem.

### Exact first action

```bash
cd F:/Dropbox/Projects/BEI-ERP
git branch --show-current
# MUST print: s210-tier-a-receipt-payment-infrastructure
# If it prints anything else, switch:
#   git checkout s210-tier-a-receipt-payment-infrastructure

# Verify Phase 0 + 1 artifacts
python output/s210/verify_phase_0.py
# MUST exit 0

cat output/s210/SHEET_IDS.json
# MUST contain sheet_a_id + sheet_b_id

# Proceed to Phase 2 per the plan doc
```

### Phase 2 specifics (to save you a plan re-read)

Create 2 more sheets with these structures:

**Sheet C: `BEI Receiving Master 2026`** (BEI-only, NO external access)
- Owner: commissary.team@bebang.ph
- Editors: sam, ian, cayla, luwi, mae, denise, jay (all @bebang.ph)
- 9 tabs: `01_Dashboard`, `02_All_Receipts_Consolidated`, `03_Supplier_SI_Uploads`, `04_Match_Queue`, `05_Variance_Queue`, `06_Pending_GR`, `07_Full_Suppliers_Master`, `08_Full_Open_POs`, `09_Audit_Log`
- Dashboard formulas (cells B3:B10) must be real formulas, not literals — for today's receipts/3PL, SI match rate, stale DR count, Pending GR depth
- Seed `07_Full_Suppliers_Master` + `08_Full_Open_POs` from Procurement AppSheet sheet id `1QWdoZlT7XWLppfVKpJ2VRXhbMkYtE5TbUwg4lMbO03Q` (read its `Suppliers` + `Purchase Order` + `PO Items` tabs)

**Sheet D: `BEI Shaw Transitional Receiving`** (BEI-only)
- Owner: commissary.team@bebang.ph
- Same 18-col Receipts schema as Sheet A/B (see plan or existing Sheet A structure)
- Internal BEI editors only, no external

Store both IDs in `output/s210/SHEET_IDS.json` under keys `sheet_c_id` and `sheet_d_id`.

Write `output/s210/verify_phase_2.py` that asserts:
- Both sheet IDs are present in SHEET_IDS.json
- Sheet C has exactly 9 tabs with the expected names (use Sheets API to list)
- Sheet C `01_Dashboard` row 3 column B has a formula (starts with `=`)
- Sheet C `07_Full_Suppliers_Master` has > 50 rows (populated from source)

Commit Phase 2 to the s210 branch with `git add -f output/s210/ scripts/google_apps/` and a message like `S210 Phase 2: Sheet C (master) + Sheet D (Shaw)`.

### Source-of-truth file references

When you need design detail:
- Plan: `docs/plans/2026-04-20-sprint-210-tier-a-receipt-payment-infrastructure.md`
- Architecture: `CEO/CashFlow/_3pl_analysis/SOLUTION_DESIGN_2026-04-18.md`
- Findings: `CEO/CashFlow/_3pl_analysis/FINDINGS_CONSOLIDATED_2026-04-18.md`
- Last Monday's 3PL update: `CEO/CashFlow/_3pl_analysis/PLAN_UPDATE_2026-04-20.md`
- Procurement skill (3MD/Pinnacle/EoPT context): `.claude/skills/procurement-bei-erp` if invocable, else `CEO/CashFlow/intercompany_gl/` Ashish memo files

### Single-owner signoff model

Sam Karazi (CEO) is sole finance approver — CFO seat vacant since 2026-04-15. When you reach Phase 6 closeout, the signoff artifact is Sam's PR merge on `s210-*`. Don't expect/require multi-approver chains.

### Autonomous execution contract

Execute through all remaining phases end-to-end. Only stop for:
- Missing credentials you cannot obtain
- Destructive action requiring Sam's explicit consent
- Business-policy question not answerable from the plan
- 3× same technical failure — then research + continue

Do NOT stop for:
- Progress-only updates
- Routine decisions where defaults are defensible
- Canonical preflight (scope = none)

### Verify before declaring Phase N complete

Every phase requires `python output/s210/verify_phase_N.py` to exit 0. The script uses filesystem checks (grep + file existence + row counts), not prose checklists. If it fails, fix the gap before advancing. Do NOT self-report "done" without the verifier passing.

### What success looks like at Phase 6

1. Plan YAML: `status: GO` → `status: COMPLETED`, `completed_date` + `execution_summary` filled
2. `SPRINT_REGISTRY.md` S210 row: PLANNED → COMPLETED with all 4 sheet IDs captured in the description
3. `output/s210/RUN_STATUS.json` and `output/s210/RUN_SUMMARY.md` reflect final state
4. `output/s210/ONBOARDING_3PL_COMMS.md` is a 1-page doc Ian + Jay use when onboarding the 3MD + Pinnacle editors
5. `output/l3/s210/SUMMARY.md` attests all 8 L3 scenarios pass
6. All commits pushed to `s210-tier-a-receipt-payment-infrastructure`
7. PR created via `GH_TOKEN="" gh pr create` and URL captured in `output/s210/PR_URL.txt`
8. `git branch --show-current` still prints `s210-tier-a-receipt-payment-infrastructure` (never drifted to production)

Start now. Read the plan first, then Phase 2.

---

## END OF HANDOFF PROMPT

Save this file at `F:\Dropbox\Projects\BEI-ERP\output\s210\HANDOFF_PROMPT.md` (already there). After `/compact`, copy the block above (between "PROMPT TO PASTE AFTER COMPACT" and "END OF HANDOFF PROMPT") and paste as the next message.
