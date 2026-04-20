---
sprint_id: S210
sprint_display: Sprint 210
branch: s210-tier-a-receipt-payment-infrastructure
pr: "https://github.com/Bebang-Enterprise-Inc/hrms/pull/649"
status: COMPLETED
created_date: 2026-04-20
completed_date: 2026-04-20
execution_summary: |
  6 phases executed end-to-end, then Phase 7 CEO UX patch same day.
  Deployed 4 Google Sheets: A (BEI 3MD Receiving Log 2026,
  id 1dambmiLzSMWOQun7MCymK4nHpuqrarFCAOK0G9-6oIU), B (BEI Pinnacle
  Receiving Log 2026, id 10fqnvF_uDl5ky3MkvXUmWvZ1fYat_p6XFGmVFc3vqrw),
  C (BEI Receiving Master 2026, 9 tabs, id 1_Ir5O5AW7hOjcvCTXsP06cF3sai9hcefDFrBOTRHOh0),
  D (BEI Shaw Transitional Receiving, id 1mbJiLW9M9e-AmrXSRRTtbRP-xKI16ah5rakOt6qv2As).
  Apps Script project deployed (id 1lsvOlv1rGEvXl_1zms4SURlsLUZk7CxRhg2NyBDrDHh4fDjuioFZhi2S).
  Seeded masters from Procurement AppSheet: 98 suppliers + 652 open POs.
  Phase 6 E2E tests 3/3 PASS (pre-patch).
  PHASE 7 CEO COURSE CORRECTIONS (2026-04-20 PM): (1) Sheets A/B/D Receipts
  tab reduced from 18 to 16 cols — "SI Photo" + "Delivery Photo" removed
  because 3PLs will not paste image/drive links in a spreadsheet; (2)
  Supplier SI Upload form rebuilt via Apps Script FormApp (native file
  upload button) instead of Forms REST API (which does not support file
  upload). Old REST-API form with Drive-link-paste text field was deleted.
  .gs updated: COL_* indexes shifted, validateReceipt no longer requires
  siPhoto, handleNewReceipt writes empty placeholders into consolidated's
  SI Photo + Delivery Photo cols. Manifest expanded with drive/forms/gmail
  scopes + executionApi.access=DOMAIN. Helper function
  s210_rebuildSupplierForm pushed to script project — requires one-click
  manual run in Apps Script editor (Apps Script API scripts.run not
  available to our service account without publisher-approved deployment).
  Full resume automation in output/s210/phase7_resume.py polls audit log
  and finalises SUPPLIER_URLS.csv + SI_UPLOAD_FORM_ID.json once Sam clicks
  Run. Plan + registry + RUN_STATUS patched to reflect reality.
  External coordination still pending: Martin (3MD) editor invite (Ian),
  Pinnacle contact migration from Viber (Jay), setup() trigger install
  by Sam/commissary.team, AND the one-click Phase 7 form rebuild.
canonical_scope: none
canonical_scope_rationale: |
  Google Workspace automation only (Google Sheets + Apps Script + Google Forms).
  No Frappe API changes, no tabCompany/tabWarehouse/tabCustomer/tabSupplier mutations,
  no Sales Invoice/PO/GR/RFP creation by this sprint. Downstream Frappe records are
  created by Ashish's Procurement AppSheet (separate sprint scope) when it consumes
  the Pending GR staging tab. The canonical preflight rule is limited to sprints that
  touch Frappe master data directly, per CEO clarification 2026-04-20.
depends_on: []
repos_touched: [hrms (plan + Apps Script deliverables only; NO Frappe code)]
---

# Sprint 210 — Tier A Receipt-Based Payment Infrastructure

**Registry row (evidence of lock):**
```
| `S210` | Sprint 210 | `s210-tier-a-receipt-payment-infrastructure` (hrms — Google Workspace Apps Script + docs only; no Frappe code) | TBD | PLANNED 2026-04-20 — ... | `docs/plans/2026-04-20-sprint-210-tier-a-receipt-payment-infrastructure.md` |
```

**Signoff model:** single-owner (Sam Karazi, CEO — sole finance approver while CFO seat is vacant).

**This plan produces code + config + docs only. It does NOT touch Frappe Python/JS.** All Frappe-side changes (DR activation, Tier A auto-RFP, RFP auto-populate, approval chain) are scoped to Ashish's existing `2026-04-18-AppSheet-Consolidated-Fix-Memo.docx` and tracked separately outside the sprint numbering. S210 is the BEI-side data-capture + automation infrastructure only.

---

## Design Rationale (For Cold-Start Agents)

### Why this exists

Supplier payments are chronically late because the current process is:
`Supplier → delivers to 3PL → 3PL hands supplier paper SI → 3PL couriers paper SI to BEI procurement (days-weeks) → procurement manually types GR in AppSheet from SI → RFP → approval → payment`

As of 2026-04-17 Google Chat exchange (see `CEO/CashFlow/_3pl_analysis/FINDINGS_CONSOLIDATED_2026-04-18.md` §3 "March 26 directive"), 5 of 7 supplier invoices were stuck at "no GR" because paper SIs hadn't arrived. Suppliers like Vangie (macapuno), Right Goods South, and others were withholding new deliveries.

### Why this architecture

**Core insight (CEO-locked 2026-04-20 10:36 AM PHT, Google Chat):**
> *"Warehouse validate the received quantity DR. SI should match the DR otherwise supplier should revise. We can process the RFP automatically from the DR and have the SI as a compliance step only. We can always dispute payments with accredited suppliers for undelivered or faulty goods... I mean dispute after the payment is done, so we do not delay payments."*

This is **receipt-based payment / Evaluated Receipt Settlement (ERS)** — validated as industry-standard practice by Coupa, Ariba, Walmart, Amazon, P&G, Ford, GM, Boeing (see research at `CEO/CashFlow/_3pl_analysis/` WebSearch results 2026-04-19).

**The two independent data streams:**
1. **DR (delivery receipt)** — captured by the party at the dock (3PL staff). Triggers GR + RFP.
2. **SI (sales invoice)** — captured from the party who issued it (supplier uploads PDF directly). Used for 3-way match and BIR VAT compliance; does NOT gate payment.

Routing SI through the 3PL was backwards — the 3PL has zero incentive to move paper fast; the supplier has maximum incentive (they want to be paid).

### Why Google Sheets + Apps Script, NOT AppSheet

**CEO direction 2026-04-19:** *"AppSheet will be expensive to build by Ashish and make no sense while we are building the ERP. I need something that can be built fast for the commissary to start using tomorrow."*

- No per-user licensing (already paying for Google Workspace)
- Zero Ashish time (he stays on ERP + VAT/EWT fixes)
- Disposable by design — when Frappe ERP ships, workflows migrate cleanly, no platform lock-in
- Apps Script has all the primitives needed: onEdit triggers, scheduled crons, Gmail, Chat API, Drive

### Why FOUR sheets, not one

**CEO direction 2026-04-20 PM:** *"I do not want 3MD and Pinnacle Tabs to be in the same sheet to avoid accidents and to avoid giving them visibility on data that they should not see."*

- Sheet A: 3MD-scoped. Martin (3MD) as editor. Sees only 3MD's data.
- Sheet B: Pinnacle-scoped. Pinnacle contact as editor (onboarding handled by Ian + Jay — NOT by sprint agent). Sees only Pinnacle's data.
- Sheet C: BEI-internal master. No external access. Dashboards, variance queue, full masters.
- Sheet D: Shaw transitional. BEI-only. Phased out when Shaw→3MD storage migration completes.

### Why RCSI is not in scope

**CEO direction 2026-04-18:** *"Royale is already phased out remove it from your docs."* RCSI is not part of future-state 3PL network.

### Why OR is not required

**BIR research 2026-04-19:** Under EoPT Act (Republic Act 11976) + RR 7-2024, Sales Invoice is now the single principal document for both goods AND services. Official Receipt is demoted to supplementary, NOT valid for input VAT claim. See sources in `CEO/CashFlow/_3pl_analysis/FINDINGS_CONSOLIDATED_2026-04-18.md` WebSearch outputs.

### Known limitations and mitigations

| Limitation | Mitigation |
|---|---|
| Pinnacle still on Viber — BEI cannot reach them directly (CEO direction) | Jay + Ian own the Pinnacle editor-seat migration outside this sprint |
| SI scanned PDFs do not qualify as BIR "electronic invoices" under RR 11-2025 | PDF is sufficient for AP processing + input VAT; original paper SI must still arrive for BIR 3-year retention (not a payment gate) |
| Apps Script has daily execution quotas | We're far below quotas (~50-100 receipts/day × minimal script time) |
| Dropdown lists in Google Sheets max 500 items | Supplier Master has 98 suppliers; Materials ~200; within limits |
| External editor on Sheet A/B could edit other tabs | Protected ranges + sheet protection; also mitigated by separate-sheets design |

### Source references for every claim above

- `CEO/CashFlow/_3pl_analysis/FINDINGS_CONSOLIDATED_2026-04-18.md` — master findings
- `CEO/CashFlow/_3pl_analysis/SOLUTION_DESIGN_2026-04-18.md` — architecture spec
- `CEO/CashFlow/_3pl_analysis/PLAN_UPDATE_2026-04-20.md` — today's updates (Viber confirmation, 3MD sheet IDs, Shaw→3MD migration, access isolation)
- `CEO/CashFlow/_3pl_analysis/audit_gmail_3md_2026-04-18.md` — 3MD daily reporting cadence + Sheet IDs
- `CEO/CashFlow/_3pl_analysis/audit_commissary_SHAW_2026-04-18.md` — Shaw warehouse + March 26 directive history
- `CEO/CashFlow/_3pl_analysis/commissary_raw/INBOUND_FORM.xlsx` — existing column structure
- `CEO/CashFlow/intercompany_gl/2026-04-18-AppSheet-Consolidated-Fix-Memo.docx` — Ashish scope (Frappe side, separate from this sprint)

---

## Ground-Truth Lock

**Evidence sources (concrete paths, all verified to exist on disk):**

| Path | What it proves |
|---|---|
| `F:\Dropbox\Projects\BEI-ERP\CEO\CashFlow\_3pl_analysis\FINDINGS_CONSOLIDATED_2026-04-18.md` | Supply chain architecture; 3PL list (RCSI excluded); data flow corrections across 4 CEO course-corrections |
| `F:\Dropbox\Projects\BEI-ERP\CEO\CashFlow\_3pl_analysis\SOLUTION_DESIGN_2026-04-18.md` | 4-sheet architecture; 18-column receiving schema; automation surface inventory |
| `F:\Dropbox\Projects\BEI-ERP\CEO\CashFlow\_3pl_analysis\PLAN_UPDATE_2026-04-20.md` | Viber-as-Pinnacle-channel confirmed; CEO access-isolation directive; Shaw→3MD migration assumption |
| `F:\Dropbox\Projects\BEI-ERP\CEO\CashFlow\_3pl_analysis\audit_gmail_3md_2026-04-18.md` | 3MD daily email cadence (98% 7-day); sheet IDs `1dNh1TnLRke7RfSavvjU1S2QP3rEJyFxf8RPURwI4rzg` (DRY) and `1u582KeN8OfnrvO4LPs1zjvFkJ0LnsVIjjoHPKqoq2IQ` (COLD) |
| `F:\Downloads\BEBANG MONITORING APRIL 20 2026 DRY.xlsx` | Pinnacle's actual Inbound tab schema (10 tabs incl. Summary, New SOH, Sheet1, Inbound, Outbound, Picklist, Sheet2, 2-17); 1,788 historical Inbound rows |
| `F:\Downloads\BEBANG MONITORING APRIL 20 2026 COLD.xlsx` | Cold-chain version of above; 333 Inbound rows |
| `F:\Downloads\image - 2026-04-20T120445.195.png` | Viber screenshot confirming `Pinnacle x Bebang PH` group (15 participants) |
| `F:\Downloads\1000041114.jpeg` | Example supplier SI — handwritten carbon-paper invoice (from Viber) |

**Count method:**
- Metric: `receipts per day` — basis: one row per receipt event per 3PL per material code. Method: `COUNTA(Sheet!B:B) - 1` (header row).
- Metric: `SI match rate` — basis: count of DRs where `SI_Matched=TRUE` / total DRs in period. Method: Apps Script formula in `01_Dashboard`.
- Metric: `stale DRs` — basis: DRs older than 72h with no matching SI upload. Method: Apps Script query against `06_Match_Queue`.

**Authoritative sections:** Phase tables + MUST_MODIFY assertions in this plan are authoritative for execution. Design Rationale + Ground-Truth Lock are traceability.

**Normalization rule:** any amendment that changes a count, label, task, or sequence must update the authoritative phase tables in the same edit.

**Unresolved value policy:** operator-facing unknowns = `[UNVERIFIED — requires resolution]`, never guessed.

---

## Canonical Scope — Out of Gate (CEO-clarified 2026-04-20)

**This sprint is `canonical_scope: none`.** Per CEO direction 2026-04-20 PM, the canonical preflight rule is limited to sprints that touch Frappe warehouses, customers, companies, suppliers, or the receipts/invoice/PO/GL creation pipeline in Frappe directly. S210 is pure Google Workspace automation — no Frappe API calls, no Frappe record mutations.

**What S210 actually does:**
- Reads from Procurement AppSheet's underlying Google Sheet (for dropdown master data) — read-only
- Writes to 4 new BEI-owned Google Sheets and 1 Google Form — new resources, not canonical
- Writes Apps Script code to `scripts/google_apps/s210_*.gs` in the hrms repo — ordinary code files, no Frappe import

**What happens downstream (NOT this sprint's doing):**
- Ashish's Procurement AppSheet polls the `Pending GR` tab from Sheet C
- When AppSheet picks up a row, IT creates the GR + RFP in Frappe — that mutation is governed by Ashish's sprint, not S210
- The canonical preflight gate applies to Ashish's work, not ours

**Pre-existing violation observed during preflight run:** `BILLING_CUST_TIN_EMPTY` for `ORTIGAS GREENHILLS - BEIFRANCHISE FOOD OPC`. Unrelated to S210 scope; documented here for awareness; belongs to a separate billing-customer TIN cleanup sprint. S210 proceeds without touching it.

---

## Requirements Regression Checklist

Executing agent MUST verify each assertion before calling a phase complete.

1. `[ ]` Is the infrastructure built as FOUR separate Google Sheets (A/B/C/D), not one sheet with multiple tabs? (CEO direction 2026-04-20 PM)
2. `[ ]` Does Sheet A show ONLY 3MD data to Martin — no Pinnacle rows, no payment terms, no dashboards, no variance queue?
3. `[ ]` Does Sheet B show ONLY Pinnacle data to the Pinnacle contact — no 3MD rows, no sensitive data?
4. `[ ]` Is Sheet C (master) strictly BEI-internal — zero external access (view, edit, comment)?
5. `[ ]` Is RCSI completely excluded from the infrastructure (no RCSI tab, no RCSI supplier references, no RCSI automation)? (CEO direction 2026-04-18)
6. `[ ]` Is OR (Official Receipt) absent from the required-documents flow? (BIR EoPT Act — OR demoted 2024)
7. `[ ]` Does the Supplier SI Upload form accept PDF scans AND note that paper SI is for BIR retention only (not a payment gate)?
8. `[ ]` Does the Tier A auto-RFP flow in the Pending GR output match the Luwi → Mae → CEO(>₱1M) approval chain exactly (no auto-approval, no bypass)?
9. `[ ]` Does every dropdown in Sheet A/B use the SANITIZED `Suppliers_Visible` tab (no Payment Terms, no Tier, no bank details visible to 3PL)?
10. `[ ]` Does `Open_POs_3MD_Only` in Sheet A exclude all POs routing to Pinnacle?
11. `[ ]` Does `Open_POs_Pinnacle_Only` in Sheet B exclude all POs routing to 3MD?
12. `[ ]` Does onEdit trigger post to the SCM Chat space (space `AAQArCi8zjE`) AND Procurement App Notifications space (space `AAQAYAYwPPk`) on every new receipt? (CEO default: both)
13. `[ ]` Does the daily 7 AM CEO email go to `sam@bebang.ph` AND `ian@bebang.ph`? (CEO default)
14. `[ ]` Is the master data refresh cron reading directly from Procurement AppSheet's underlying Google Sheet (no Ashish involvement)?
15. `[ ]` Does the variance queue age DRs to human review at 72 hours when no SI has matched?
16. `[ ]` Does the Supplier SI upload Google Form generate ONE pre-filled URL per Tier A supplier (not a generic form for all)?
17. `[ ]` Does the payment flow respect each supplier's contracted Payment Terms (Net 15 / Net 30 / Net 45 / Net 60 / COD / 50-50)?
18. `[ ]` Is `canonical_scope: none` declared in the plan YAML with rationale? (CEO-clarified: Google Workspace automation is out of gate)
19. `[ ]` Is the verification script in Phase 6 written to the filesystem as `output/s210/verify_phase_<N>.py` so closeout is machine-checkable (not agent self-report)?

**HARD BLOCKER (from CEO decisions):** If any task in this plan would require 3MD or Pinnacle to see the OTHER 3PL's data, STOP and present options. Access isolation is non-negotiable.

**HARD BLOCKER:** If any task would require AppSheet seats for external users (3MD, Pinnacle, suppliers), STOP. CEO rejected AppSheet for commissary/3PL infrastructure 2026-04-19.

**HARD BLOCKER:** If any task would reintroduce Official Receipt as a required workflow step, STOP. OR is supplementary under EoPT (2024).

---

## Anti-Rewind / Concurrent-Run Protection Contract

- **Ownership matrix:** `output/s210/S210_SURFACE_OWNERSHIP.csv`
  - BEI-ERP repo: `scripts/google_apps/s210_*.gs` (exclusive to this sprint)
  - BEI-ERP repo: `docs/plans/2026-04-20-sprint-210-*.md` (this file only)
  - BEI-ERP repo: `docs/plans/SPRINT_REGISTRY.md` (append-only for S210 row + Next counter bump — safe shared edit)
  - Google Workspace: 4 new sheets owned by `commissary.team@bebang.ph` (new resources, no overlap)
  - Google Forms: 1 new "BEI Supplier SI Upload" form (new resource, no overlap)

- **Protected surfaces (adjacent shipped work that must stay untouched):**
  - `hrms/api/*.py` — DO NOT MODIFY (this sprint is Google Workspace only)
  - `hrms/hr/doctype/bei_*` — DO NOT MODIFY
  - `bei-tasks/**` — DO NOT MODIFY
  - Existing 3MD-owned Google Sheets (`1dNh1TnLRke7RfSavvjU1S2QP3rEJyFxf8RPURwI4rzg`, `1u582KeN8OfnrvO4LPs1zjvFkJ0LnsVIjjoHPKqoq2IQ`) — READ-ONLY; never write to them (they are 3MD-owned, not BEI)
  - Procurement AppSheet underlying Google Sheets — READ-ONLY for dropdown masters

- **Remote-truth baseline:**
  - `output/s210/S210_REMOTE_TRUTH_BASELINE.json` — captures starting git SHAs for hrms + bei-tasks, plus latest merged PR numbers, plus the Procurement AppSheet sheet ID version

- **Active run coordination:**
  - `output/s210/state/S210_ACTIVE_RUN_COORDINATION.json` — claim on start, release on closeout

- **Pre-touch backup:**
  - Before first run, snapshot `SPRINT_REGISTRY.md` to `output/s210/state/S210_PRETOUCH_BACKUP.json`

- **Touch preservation:**
  - `output/s210/ledgers/S210_TOUCH_PRESERVATION_LEDGER.csv` — append on every file mutation

---

## Phase Budget Contract

Hard ceiling: 15 units per phase. Preferred split threshold: 12 units.

| Phase | Name | Unit budget | Rationale |
|---|---|---:|---|
| 0 | Preflight + Library Audit + Baseline | 8 | Canonical preflight + evidence gathering + ownership lock |
| 1 | Sheet A (3MD) + Sheet B (Pinnacle) | 10 | Two sheets, identical structure, cascade dropdowns, protected ranges |
| 2 | Sheet C (Master) + Sheet D (Shaw transitional) | 9 | Internal dashboard + consolidation + queues; Shaw is minimal |
| 3 | Apps Script — validation + consolidation + Chat notifications | 12 | onEdit triggers, match logic, variance queue, Chat API |
| 4 | Supplier SI Upload Form + pre-filled URLs + match Apps Script | 10 | Google Form, per-supplier URL generator, onFormSubmit handler |
| 5 | CEO Daily Email + Dashboard formulas + verification scripts | 8 | 7 AM cron, KPI formulas, machine-verifiable closeout scripts |
| 6 | Onboarding docs + E2E test + Closeout | 9 | 1-page how-to for Martin + Pinnacle, E2E test, registry update |

**Total: 66 units** (under 80 ceiling; single-session executable).

Cross-phase dependencies:
- Phase 1 blocks Phase 2 (master pulls from A/B).
- Phase 2 blocks Phase 3 (triggers bind to Sheet C).
- Phase 3 blocks Phase 4 (SI match logic extends Phase 3's match queue).
- Phase 4 blocks Phase 5 (email KPIs include SI match rate).
- Phase 5 blocks Phase 6 (E2E test uses verification scripts).

---

## Execution Authority

This sprint is intended for autonomous end-to-end execution by a single agent in one session. Do not stop for progress-only updates. Only pause for items in `stop_only_for` below.

## Autonomous Execution Contract

```yaml
completion_condition:
  - All 4 Google Sheets (A, B, C, D) created with correct schema, permissions, protected ranges
  - Supplier SI Upload Google Form created + per-supplier URLs generated
  - Apps Script deployed + all 6 triggers wired (onEdit x2, onFormSubmit, hourly cron, daily 06:00, daily 07:00)
  - End-to-end test passes: dummy Martin-authored receipt in Sheet A → Chat notification fires → row appears in Sheet C Pending GR → Supplier SI upload matches → Dashboard updates
  - All MUST_MODIFY and MUST_CONTAIN assertions in phase tables verify
  - Machine-verifiable `output/s210/verify_phase_6.py` returns 0 (all phases green)
  - Plan YAML updated: status GO -> COMPLETED, completed_date, execution_summary
  - SPRINT_REGISTRY.md row updated to COMPLETED with sheet IDs captured
  - 1-page onboarding doc saved at `output/s210/ONBOARDING_MARTIN_PINNACLE.md` for Ian + Jay to use
  - All commits pushed to `s210-tier-a-receipt-payment-infrastructure` branch + PR created
stop_only_for:
  - Martin's email address (for Sheet A editor invite) — unresolved
  - Pinnacle contact email (for Sheet B editor invite) — unresolved (per CEO: Ian+Jay handle)
  - Procurement AppSheet underlying sheet inaccessible (cannot read master data)
  - Chat API credentials rotation (unlikely)
  - Destructive action that would break an existing in-flight sprint
  - CEO intervention requested by agent
continue_without_pause_through:
  - preflight
  - sheet creation
  - Apps Script deployment
  - form creation
  - local test
  - E2E test
  - PR creation
  - closeout
  - registry update
blocker_policy:
  - programmatic Apps Script error -> fix and continue
  - permission denial on a sheet create -> retry once, escalate if persists
  - evidence mismatch in plan -> normalize plan body AND continue
  - repeated Apps Script trigger failure x3 -> grounded research (quota check, scope check), then continue
  - Martin/Pinnacle email missing -> generate invite URL but don't send; document for Ian to action; proceed with rest
signoff_authority: single-owner (Sam Karazi, CEO)
canonical_closeout_artifacts:
  - output/s210/RUN_STATUS.json
  - output/s210/RUN_SUMMARY.md
  - output/s210/ONBOARDING_MARTIN_PINNACLE.md
  - output/s210/verify_phase_6.py
  - output/s210/state/S210_REMOTE_TRUTH_BASELINE.json
  - output/s210/state/S210_ACTIVE_RUN_COORDINATION.json
  - docs/plans/2026-04-20-sprint-210-tier-a-receipt-payment-infrastructure.md (this file; status -> COMPLETED)
  - docs/plans/SPRINT_REGISTRY.md (S210 row -> COMPLETED with sheet IDs)
```

---

## Status Reconciliation Contract

Whenever sheet IDs, trigger status, or E2E results change, update in the same work unit:

1. `output/s210/RUN_STATUS.json`
2. `output/s210/RUN_SUMMARY.md`
3. Plan YAML status block
4. `SPRINT_REGISTRY.md` S210 row
5. Touch preservation ledger if any file mutated

---

## Zero-Skip Enforcement

**NON-NEGOTIABLE:** Every task in the phase tables below MUST be implemented. If a task cannot be completed, the agent STOPS and asks the user. No silent skips. No "deferred to next sprint." No happy-path-only shortcuts.

**Forbidden agent behaviors:**
- Skipping a task without user approval
- Marking a task DONE when evidence shows partial (the verification script catches this)
- Replacing a task with a simpler version without user approval
- Combining two tasks and dropping one feature
- Creating only one of Sheet A/B/C/D and claiming "infrastructure ready"
- Shipping Apps Script without actual triggers installed (script code ≠ live triggers)

**Phase Completion Checklist — agent writes per phase:**

| Task | MUST_MODIFY / MUST_CONTAIN | Status | Evidence (file path + grep proof) | Skipped? |
|---|---|---|---|---|

**Verification script template (agent writes `output/s210/verify_phase_<N>.py` per phase):**

```python
import subprocess, sys, pathlib, json

FAILED = []

def check_file_exists(path, reason):
    if not pathlib.Path(path).exists():
        FAILED.append(f"MISSING: {path} — {reason}")

def check_contains(path, pattern, reason):
    try:
        text = pathlib.Path(path).read_text(encoding='utf-8', errors='ignore')
        if pattern not in text:
            FAILED.append(f"PATTERN MISSING: {pattern!r} in {path} — {reason}")
    except Exception as e:
        FAILED.append(f"READ ERROR: {path} — {e}")

def check_git_diff_contains(file_hint):
    try:
        out = subprocess.check_output(['git', 'diff', '--name-only', 'origin/production'], cwd='.', text=True)
        if file_hint not in out:
            FAILED.append(f"NOT IN DIFF: {file_hint}")
    except Exception as e:
        FAILED.append(f"GIT ERROR: {e}")

# ... phase-specific checks ...

if FAILED:
    for f in FAILED:
        print('[FAIL]', f)
    sys.exit(1)
print('[PASS] all assertions green')
sys.exit(0)
```

If the verification script exits non-zero, the phase is not complete. Fix failures before starting the next phase.

---

## Agent Boot Sequence

1. Read this plan fully.
2. **Create sprint branch:**
   ```bash
   cd F:/Dropbox/Projects/BEI-ERP
   git fetch origin production
   git checkout -b s210-tier-a-receipt-payment-infrastructure origin/production
   ```
   NEVER write code on production.
3. Read `docs/plans/SPRINT_REGISTRY.md` for cross-sprint context (verify S210 row is committed).
4. Read the four evidence files listed in Ground-Truth Lock above.
5. ~~Canonical preflight~~ Skipped — `canonical_scope: none`. CEO clarified 2026-04-20: the preflight rule applies to Frappe master-data sprints, not Google Workspace automation. For traceability, a one-time preflight was captured at `output/s210/verify_canonical_preflight.log` showing 1 pre-existing violation (ORTIGAS GREENHILLS TIN) unrelated to S210 scope.
6. Create directory `output/s210/` and `output/s210/state/` and `output/s210/ledgers/`.
7. Capture remote-truth baseline:
   ```bash
   git rev-parse HEAD > output/s210/state/S210_REMOTE_TRUTH_BASELINE.json.tmp
   ```
   Then write the proper JSON with repo, branch, SHA, baseline sheet IDs (3MD DRY `1dNh1TnLRke7RfSavvjU1S2QP3rEJyFxf8RPURwI4rzg`, 3MD COLD `1u582KeN8OfnrvO4LPs1zjvFkJ0LnsVIjjoHPKqoq2IQ`).
8. Write active run coordination file `output/s210/state/S210_ACTIVE_RUN_COORDINATION.json` with claim.
9. Proceed to Phase 0.

---

## Phases

### Phase 0 — Preflight + Library Audit + Baseline (8 units)

| # | Task | MUST_MODIFY / MUST_CONTAIN | Unit |
|---|---|---|---|
| 0.1 | ~~Canonical preflight~~ — SKIPPED per `canonical_scope: none` (see Canonical Scope section). Preflight log captured for traceability showing 1 pre-existing unrelated violation. | `output/s210/verify_canonical_preflight.log` exists | 0 |
| 0.2 | Read and verify access to Procurement AppSheet's underlying Google Sheet (the dropdown source for our Masters). Record sheet ID + tab names + column schemas in `output/s210/PROCUREMENT_APPSHEET_BASELINE.json` | MUST_MODIFY: `output/s210/PROCUREMENT_APPSHEET_BASELINE.json` | 2 |
| 0.3 | Library audit: scan existing Apps Script in the BEI ecosystem for reusable helpers (Chat API posting, Gmail sending, onEdit patterns). List in `output/s210/LIBRARY_AUDIT.md` | MUST_CONTAIN: at least 3 existing helper references with file paths | 2 |
| 0.4 | Write ownership matrix `output/s210/S210_SURFACE_OWNERSHIP.csv` listing every file this sprint will create/mutate | MUST_MODIFY: file created with >= 15 rows | 1 |
| 0.5 | Write protected-surface registry `output/s210/S210_PROTECTED_SURFACES.csv` — 3MD-owned sheets + Procurement AppSheet + existing hrms/api/*.py are read-only or off-limits | MUST_MODIFY: file created | 1 |
| 0.6 | Verify: `python output/s210/verify_phase_0.py` exits 0 | exits 0 | 1 |

### Phase 1 — Sheet A (3MD) + Sheet B (Pinnacle) (10 units)

| # | Task | MUST_MODIFY / MUST_CONTAIN | Unit |
|---|---|---|---|
| 1.1 | Create Sheet A `BEI 3MD Receiving Log 2026` owned by `commissary.team@bebang.ph`. Capture ID in `output/s210/SHEET_IDS.json` | MUST_MODIFY: `output/s210/SHEET_IDS.json` CONTAINS `"sheet_a_id"` | 1 |
| 1.2 | Create 5 tabs in Sheet A: `Receipts`, `Open_POs_3MD_Only`, `Suppliers_Visible`, `Materials`, `_Instructions` | Sheet A tab list MUST include exactly these 5 | 1 |
| 1.3 | Write 18-column header in `Receipts` tab per schema in SOLUTION_DESIGN_2026-04-18.md §1.2 | Column A-R = exact spec | 1 |
| 1.4 | Apply data validation: Supplier column = dropdown from `Suppliers_Visible` tab; PO Number column = dropdown from `Open_POs_3MD_Only`; Material Code = dropdown filtered by PO (via INDIRECT) | MUST_CONTAIN via Apps Script: `setDataValidation()` calls on columns E, F, G | 2 |
| 1.5 | Apply protected ranges: lock `Open_POs_3MD_Only`, `Suppliers_Visible`, `Materials`, `_Instructions` tabs from external editor (Martin) — only BEI staff can modify | Protected range count MUST = 4 | 1 |
| 1.6 | Write `_Instructions` tab — 1-page how-to for Martin (step-by-step: open URL, click Receipts tab, add row, cascade dropdowns, upload photo) | `_Instructions!A1:A30` MUST_CONTAIN at least 10 numbered steps | 1 |
| 1.7 | Repeat steps 1.1-1.6 for Sheet B `BEI Pinnacle Receiving Log 2026` with `Open_POs_Pinnacle_Only` tab | `output/s210/SHEET_IDS.json` CONTAINS `"sheet_b_id"` | 2 |
| 1.8 | Add internal editor access to Sheet A + B: Ian (`ian@bebang.ph`), Cayla (`cayla@bebang.ph`), Sam (`sam@bebang.ph`), Jay (`jay@bebang.ph`) | Sheet permissions list MUST include 4 BEI editors each | 1 |
| 1.9 | Verify: `python output/s210/verify_phase_1.py` exits 0 | exits 0 | — |

### Phase 2 — Sheet C (Master) + Sheet D (Shaw) (9 units)

| # | Task | MUST_MODIFY / MUST_CONTAIN | Unit |
|---|---|---|---|
| 2.1 | Create Sheet C `BEI Receiving Master 2026` owned by `commissary.team@bebang.ph`, editor access restricted to Sam, Ian, Cayla, Luwi, Mae, Denise, Jay — NO external | `output/s210/SHEET_IDS.json` CONTAINS `"sheet_c_id"` | 1 |
| 2.2 | Create 9 tabs in Sheet C per SOLUTION_DESIGN §1 (Sheet C structure): `01_Dashboard`, `02_All_Receipts_Consolidated`, `03_Supplier_SI_Uploads`, `04_Match_Queue`, `05_Variance_Queue`, `06_Pending_GR`, `07_Full_Suppliers_Master`, `08_Full_Open_POs`, `09_Audit_Log` | Sheet C tab list = exactly these 9 | 1 |
| 2.3 | Write schema headers in each tab | Each tab row 1 MUST have header cells | 2 |
| 2.4 | Create Sheet D `BEI Shaw Transitional Receiving` (BEI-internal only) with same 18-col receipts schema as Sheet A | `output/s210/SHEET_IDS.json` CONTAINS `"sheet_d_id"` | 1 |
| 2.5 | Write `01_Dashboard` formulas: today's receipts count per 3PL, SI match rate, stale-DR count, Pending GR depth, variance queue depth | Dashboard cells B3:B10 MUST contain formulas, not literals | 2 |
| 2.6 | Seed `07_Full_Suppliers_Master` + `08_Full_Open_POs` from Procurement AppSheet sheet (one-time initial load) | Row counts match source | 1 |
| 2.7 | Verify: `python output/s210/verify_phase_2.py` exits 0 | exits 0 | 1 |

### Phase 3 — Apps Script: validation + consolidation + Chat notifications (12 units) — AT CEILING

| # | Task | MUST_MODIFY / MUST_CONTAIN | Unit |
|---|---|---|---|
| 3.1 | Create Apps Script project bound to Sheet C; commit source as `scripts/google_apps/s210_master_handler.gs` in hrms repo | MUST_MODIFY: `scripts/google_apps/s210_master_handler.gs` exists | 1 |
| 3.2 | Implement `validateReceipt(row)` — checks PO open, supplier matches PO, material on PO, qty ≤ balance, SI# present, SI photo present | MUST_CONTAIN: function name `validateReceipt` | 2 |
| 3.3 | Implement `handleNewReceipt_3MD(e)` — triggered onEdit of Sheet A's Receipts tab; calls validateReceipt; writes to Sheet C consolidated + Pending GR | MUST_CONTAIN: function name `handleNewReceipt_3MD` | 2 |
| 3.4 | Implement `handleNewReceipt_Pinnacle(e)` — equivalent for Sheet B | MUST_CONTAIN: function name `handleNewReceipt_Pinnacle` | 1 |
| 3.5 | Implement `postChatNotification(receipt)` — posts to SCM space (`spaces/AAQArCi8zjE`) + Procurement App Notifications (`spaces/AAQAYAYwPPk`) | MUST_CONTAIN: both space IDs in script | 2 |
| 3.6 | Implement `ageVarianceQueue()` hourly cron — moves DRs without matching SI > 72h to variance queue | MUST_CONTAIN: function + installable trigger spec | 2 |
| 3.7 | Install installable triggers on Sheet A + Sheet B (onEdit) + hourly cron + daily 06:00 cron (master refresh) | `output/s210/TRIGGERS_INSTALLED.json` MUST list 4 triggers | 1 |
| 3.8 | Log every automation action to Sheet C `09_Audit_Log` (timestamp, trigger, row affected, outcome) | Audit log row count increments on every trigger fire | 1 |
| 3.9 | Verify: `python output/s210/verify_phase_3.py` exits 0 | exits 0 | — |

### Phase 4 — Supplier SI Upload Form + match logic (10 units)

| # | Task | MUST_MODIFY / MUST_CONTAIN | Unit |
|---|---|---|---|
| 4.1 | Create Google Form `BEI Supplier SI Upload` with fields: PO Number (short text), SI Number (short text), SI Date (date), Amount (number), SI PDF (file upload), Supplier Name (auto from URL), Notes (paragraph) | `output/s210/SI_UPLOAD_FORM_ID.json` captured | 2 |
| 4.2 | Write `generateSupplierUrls.gs` — pulls Tier A supplier list from `07_Full_Suppliers_Master`, generates pre-filled URL per supplier | MUST_CONTAIN: function `generateSupplierUrls` | 2 |
| 4.3 | Write Tier A supplier URLs to `output/s210/SUPPLIER_URLS.csv` (supplier name, TIN, URL, QR code link) | MUST_MODIFY: `output/s210/SUPPLIER_URLS.csv` has >= 30 rows | 1 |
| 4.4 | Implement `handleSiUpload(e)` onFormSubmit trigger — writes to Sheet C `03_Supplier_SI_Uploads`; attempts match against Sheet C `02_All_Receipts_Consolidated` by (PO#, SI#) | MUST_CONTAIN: function `handleSiUpload` | 2 |
| 4.5 | Match results: clean match → tag DR with SI_Matched=TRUE + Drive link to PDF; no match → write to `04_Match_Queue` as orphan pending resolution | Audit log MUST reflect match outcomes | 1 |
| 4.6 | Install onFormSubmit trigger on the SI Upload form | Triggers list MUST include form submit | 1 |
| 4.7 | Verify: `python output/s210/verify_phase_4.py` exits 0 | exits 0 | 1 |

### Phase 5 — CEO Daily Email + Dashboard + verification scripts (8 units)

| # | Task | MUST_MODIFY / MUST_CONTAIN | Unit |
|---|---|---|---|
| 5.1 | Implement `sendCeoDailyEmail()` function — pulls yesterday's KPIs from Dashboard; sends to `sam@bebang.ph`, `ian@bebang.ph` at 07:00 PHT | MUST_CONTAIN: both email addresses in function | 2 |
| 5.2 | Install daily 07:00 PHT trigger for CEO email | `TRIGGERS_INSTALLED.json` MUST list this trigger | 1 |
| 5.3 | Implement `refreshMasters()` function — pulls Procurement AppSheet underlying sheet daily at 06:00; rebuilds `07_Full_Suppliers_Master` + `08_Full_Open_POs`; regenerates `Suppliers_Visible` in Sheets A + B; regenerates `Open_POs_3MD_Only` and `Open_POs_Pinnacle_Only` by destination filter | MUST_CONTAIN: function `refreshMasters` | 2 |
| 5.4 | Install daily 06:00 PHT trigger for master refresh | `TRIGGERS_INSTALLED.json` MUST list this trigger | 1 |
| 5.5 | Write `output/s210/verify_phase_5.py` checking: all 6 triggers installed, Dashboard formulas non-literal, Supplier URLs CSV > 30 rows, Chat API credentials valid | exits 0 | 1 |
| 5.6 | Write `output/s210/RUN_STATUS.json` — populated from current state | MUST_MODIFY: file with `phase_5_complete: true` | 1 |

### Phase 6 — Onboarding docs + E2E test + Closeout (9 units)

| # | Task | MUST_MODIFY / MUST_CONTAIN | Unit |
|---|---|---|---|
| 6.1 | Write `output/s210/ONBOARDING_MARTIN_PINNACLE.md` — 1-page doc for Ian + Jay to use with Martin (3MD) + Pinnacle contact. Screenshots placeholder + step-by-step | MUST_CONTAIN: at least 10 numbered steps + Sheet A + Sheet B URLs | 2 |
| 6.2 | E2E test — script a dummy supplier receipt: add test row in Sheet A `Receipts` as if Martin logged it. Verify in order: (a) onEdit fires, (b) row appears in Sheet C `02_All_Receipts_Consolidated`, (c) row appears in `06_Pending_GR`, (d) Chat posts to SCM + Procurement App Notifications, (e) Dashboard KPIs update. Capture evidence in `output/l3/s210/e2e_test_3md.json` | MUST_MODIFY: evidence JSON with all 5 checks `"pass": true` | 2 |
| 6.3 | E2E test — equivalent for Pinnacle (Sheet B). Evidence in `output/l3/s210/e2e_test_pinnacle.json` | MUST_MODIFY: evidence JSON | 1 |
| 6.4 | E2E test — Supplier SI upload: submit test SI via the form; verify match against a known DR; verify SI_Matched=TRUE on the receipt row. Evidence in `output/l3/s210/e2e_test_supplier_si.json` | MUST_MODIFY: evidence JSON | 1 |
| 6.5 | Write `output/s210/verify_phase_6.py` — runs all prior phase verifiers + asserts E2E evidence files exist and all `pass: true` | exits 0 | 1 |
| 6.6 | Update this plan's YAML: `status: GO` → `status: COMPLETED`, add `completed_date`, write `execution_summary` summarizing: sheets created, triggers live, E2E results | MUST_MODIFY: plan YAML updated | 1 |
| 6.7 | Update `docs/plans/SPRINT_REGISTRY.md` S210 row — `PLANNED 2026-04-20` → `COMPLETED YYYY-MM-DD` with sheet IDs appended; force-add committed | MUST_MODIFY: registry row changed | 1 |
| 6.8 | `git add -f` + commit + push `s210-tier-a-receipt-payment-infrastructure` branch; create PR with `GH_TOKEN="" gh pr create ...` | PR URL captured in `output/s210/PR_URL.txt` | — |

---

### Phase 7 — CEO UX course-correction (2026-04-20 PM, added post-Phase-6)

Triggered by CEO directive after reviewing the bare Sheet A during Phase 6
closeout: "3pl are not going to paste a fucking image link in sheets, so
only ask for SI number no need for photos. For suppliers form I need an
upload button and not a link pasting as well, always aim for good UX.
Patch your plan so we can track what the fuck we discussed."

| # | Task | MUST_MODIFY / MUST_CONTAIN | Unit |
|---|---|---|---|
| 7.1 | Strip `SI Photo` + `Delivery Photo` columns from Sheets A, B, D `Receipts` tab (18 cols → 16 cols). Migrate existing rows. | Sheets A/B/D `Receipts` row 1 cols count = 16 | 2 |
| 7.2 | Update `s210_master_handler.gs` COL_* constants (shift post-SI Number cols by -2); remove `siPhoto` check in `validateReceipt`; in `_handleNewReceipts`, write empty-string placeholders into consolidated's SI Photo + Delivery Photo positions (consolidated schema unchanged at 22 cols) | `.gs` `const COL_SI_PHOTO` REMOVED; `const COL_TRUCKER = 10` | 2 |
| 7.3 | Delete the existing Forms-REST-API supplier form (bad UX — suppliers paste Drive link text). `drive_api.files().delete(old_form_id)` | Old form 404 | 1 |
| 7.4 | Expand manifest: add `drive`, `forms`, `gmail.send` scopes; set `executionApi.access=DOMAIN`. Re-upload to script project. | manifest size increases; new scopes present | 1 |
| 7.5 | Push helper function `s210_rebuildSupplierForm` to the script project. Helper uses `FormApp.create()` + `addFileUploadItem()` for native upload button. Helper persists result (formId, responderUri, entries) into Sheet C 09_Audit_Log under trigger=`phase7_form_rebuild`. | Script project has `s210_phase7_form_rebuild` file; helper appears in file listing | 1 |
| 7.6 | Manual step: Sam opens Apps Script editor, selects `s210_rebuildSupplierForm`, clicks Run. Documented in `output/s210/PHASE7_MANUAL_STEP.md`. | PHASE7_MANUAL_STEP.md exists with exact steps | — |
| 7.7 | `python output/s210/phase7_resume.py` (post-click) polls audit log, rewrites `SUPPLIER_URLS.csv` + `SI_UPLOAD_FORM_ID.json` + updates `SHEET_IDS.json` with new `si_upload_form_id` + `si_upload_form_uses_native_file_upload=true`. | new form id reflected; CSV has >=30 rows | 2 |
| 7.8 | Update ONBOARDING doc: remove SI Photo instruction from 3PL steps; update form field list to say "tap to upload PDF" instead of "paste Drive link" | ONBOARDING doc reflects 16-col schema + native file upload | 1 |
| 7.9 | Verify: `python output/s210/verify_phase_7.py` exits 0 | exits 0 | — |

**Known friction:** Phase 7 requires one manual click because the service
account's domain-wide delegation does not include `script.deployments`
scope. To fully automate, either (a) admin adds `script.deployments` to
DWD, or (b) publisher-approval deployment is done by a human once.

---

## L3 Workflow Scenarios

| User | Action | Expected Outcome | Failure Means |
|---|---|---|---|
| Agent (simulating Martin) | Add row to Sheet A `Receipts`: PO=<any open 3MD PO>, Supplier=<that PO's supplier>, Material=<line item from PO>, Qty=5, SI#=`TEST-S210-001`, SI photo=attached | Within 10 sec: row in Sheet C `02_All_Receipts_Consolidated`, row in `06_Pending_GR`, Chat post in SCM space, Dashboard `today's receipts` increments | onEdit trigger broken or Chat API misconfigured |
| Agent (simulating Pinnacle staff) | Add row to Sheet B `Receipts` with valid data | Same as above for Pinnacle path | Pinnacle onEdit trigger broken |
| Agent (simulating supplier) | Submit SI Upload form with PO=<matching prior DR's PO>, SI#=`TEST-S210-001`, PDF attached | Within 10 sec: row in Sheet C `03_Supplier_SI_Uploads`; DR row tagged SI_Matched=TRUE; Drive link to PDF attached | onFormSubmit broken OR match logic broken |
| Agent (simulating supplier) | Submit SI Upload form with PO that does NOT match any DR | Row in `03_Supplier_SI_Uploads` but status = Orphan; row in `04_Match_Queue` | Match logic erroneously tagging |
| Agent (simulating old DR) | Wait 72+ hours OR fast-forward timestamp; run `ageVarianceQueue()` manually | DR row moves to `05_Variance_Queue` | Aging cron broken |
| Agent (simulating invalid entry) | Add Sheet A row with supplier that doesn't match the PO's supplier | Row flagged red; exception in `05_Variance_Queue`; NO Pending GR row written | Validation bypass |
| Agent (simulating permission test) | Attempt to edit `Open_POs_3MD_Only` from a non-BEI account | Edit rejected by protected range | Protection not applied |
| Agent (reading as 3MD) | Open Sheet A while logged in as Martin (or simulate by revoking own access to other sheets) | Can see only Sheet A; cannot see Sheet B, C, D | Access isolation broken |

Evidence files:
```
output/l3/s210/e2e_test_3md.json
output/l3/s210/e2e_test_pinnacle.json
output/l3/s210/e2e_test_supplier_si.json
output/l3/s210/e2e_test_variance_aging.json
output/l3/s210/e2e_test_access_isolation.json
output/l3/s210/SUMMARY.md
```

---

## Sentry Observability (Not applicable — Google Workspace only)

This sprint does NOT modify `@frappe.whitelist()` endpoints or `bei-tasks/app/api/*/route.ts`. Sentry backend instrumentation not applicable.

For Apps Script error visibility: log all `catch` exceptions to Sheet C `09_Audit_Log` with severity tag. Optionally post Sentry-equivalent alerts to SCM Chat space for critical failures. Reference: `.claude/rules/sentry-observability.md` (DM-7) — exempt by platform (Apps Script is not in scope).

---

## Execution Workflow

- Test local Apps Script snippets: paste into script editor's REPL
- No Python unit tests (no Python code produced)
- No `/local-frappe` (no Frappe code)
- Deploy: Apps Script is deployed by saving + installable triggers (not via `/deploy-frappe`)
- E2E: manual via Phase 6 tasks 6.2-6.4 + captured JSON evidence
- Closeout: Phase 6 tasks 6.6-6.8

---

## Failure Response

- **Mode A (platform bug in Google Apps Script / Sheets):** file `[BUG]` in `output/s210/`, research Apps Script known issues, apply workaround (e.g., `Utilities.sleep(500)` for rate limits). Do not touch our code unless genuinely our issue.
- **Mode B (our code bug):** fix + push. If the fix is a pattern used elsewhere, promote to a helper function in `scripts/google_apps/s210_common.gs`.
- **Mode C (brittleness — trigger sometimes doesn't fire):** fix the installation, not retry loops. Apps Script installable triggers should fire every time.

If ≥3 library fixes happen during execution, emit `output/s210/LIBRARY_IMPROVEMENTS.md` as a closeout artifact.

---

## Signoff Model

- **mode:** single-owner
- **approver_of_record:** Sam Karazi (CEO)
- **signoff_artifact:** `output/s210/RUN_SUMMARY.md` plus Sam's PR merge on the `s210-*` branch
- **note:** CFO seat is vacant as of 2026-04-15. Sam is sole finance approver until new CFO is hired. No department-level signoff chain required for this infrastructure sprint.

---

## Certification Coverage Contract

- **certified_universe:**
  - sheets: 4 (A, B, C, D)
  - tabs: 24 across all sheets
  - triggers: 6 (2 × onEdit, 1 × onFormSubmit, 3 × time-based)
  - scenarios: 8 L3 rows above
- **closeout_zero_equations:**
  - unverified_sheets = 0
  - missing_triggers = 0
  - failed_l3_rows = 0
  - unmatched_requirements_checklist_items = 0
- **allowed_skips:**
  - 1 optional (Sentry backend instrumentation — platform-exempt by design)
- **final_readiness_basis:**
  - `output/l3/s210/SUMMARY.md` attesting all 8 L3 rows pass
  - `output/s210/verify_phase_6.py` exits 0

---

## Amendment Log

- 2026-04-20: Initial draft. Reserved as S210 in registry.
- 2026-04-20: CEO clarified canonical_scope rule applies only to Frappe master-data sprints, not Google Workspace automation. Changed `canonical_scope: in` -> `canonical_scope: none` with rationale. Removed Canonical Preflight + Canonical Binding sections. Task 0.1 marked skipped. Pre-existing `BILLING_CUST_TIN_EMPTY` violation for ORTIGAS GREENHILLS documented as unrelated.

---

## Closeout Checklist (filled by agent during Phase 6)

- [ ] Sheets A, B, C, D created and IDs captured
- [ ] All 24 tabs present with correct headers
- [ ] All 6 triggers installed and firing
- [ ] Supplier SI Upload form created with URLs for Tier A suppliers
- [ ] 8 L3 scenarios pass with evidence JSON
- [ ] `scripts/verify_canonical_structure.py` returns zero violations post-sprint
- [ ] Plan YAML status = COMPLETED
- [ ] SPRINT_REGISTRY.md S210 row = COMPLETED with sheet IDs
- [ ] Onboarding doc at `output/s210/ONBOARDING_MARTIN_PINNACLE.md`
- [ ] PR created and URL captured
- [ ] Touch preservation ledger reconciles all mutations

---

**End of plan.**
