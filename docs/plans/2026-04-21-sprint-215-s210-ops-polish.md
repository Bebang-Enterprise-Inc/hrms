---
sprint_id: S215
sprint_display: Sprint 215
branch: s215-s210-ops-polish
pr: TBD
status: GO
created_date: 2026-04-21
completed_date: TBD
execution_summary: TBD
canonical_scope: none
canonical_scope_rationale: |
  Google Workspace operational polish only — Sheets API, Apps Script API,
  Cloud Scheduler. No Frappe API calls, no tabCompany/tabWarehouse/tabCustomer/tabSupplier
  mutations, no Sales Invoice / PO / GR / RFP creation. Extends S210's
  infrastructure without touching canonical master data.
depends_on: [S210]
repos_touched: [hrms (Apps Script deliverables + docs only; NO Frappe code)]
---

# Sprint 215 — S210 Operational Polish (Materials catalog, PO-line cascade, Timestamp auto-fill, QR poster)

**Registry row (evidence of lock):**
```
| `S215` | Sprint 215 | `s215-s210-ops-polish` (hrms — Google Workspace: Sheets API + Apps Script API + Cloud Scheduler; no Frappe / bei-tasks code) | TBD | PLANNED 2026-04-21 — **S210 Operational Gap Fixes**. ... | `docs/plans/2026-04-21-sprint-215-s210-ops-polish.md` |
```

**Signoff model:** single-owner (Sam Karazi, CEO).

**This plan produces Apps Script code + Sheets API scripts + DOCX/PDF deliverables only. It does NOT touch Frappe Python/JS.**

---

## Design Rationale (For Cold-Start Agents)

### Why this exists

S210 shipped the Receipt-Based Payment Infrastructure across 16 phases (see `docs/plans/2026-04-20-sprint-210-tier-a-receipt-payment-infrastructure.md`). Post-deployment review on 2026-04-21 surfaced gaps in the 3PL-facing experience:

1. Sheet A/B/D `Materials` tab is empty — it was created with column headers but `refreshMasters` never populates it. 3PL dropdowns for Material Code currently point to an empty range.
2. `Open_POs_*_Only` carries PO-header data (PO number, supplier, total, balance) but not PO-line items. This means the Material Code dropdown cannot cascade — the 3PL sees all materials regardless of selected PO, or (today) sees nothing.
3. Timestamp column (A) is manual. The `_Instructions` tab tells the 3PL to type it; the handler skips rows where it's blank. No cell protection. Phase 8's move from Apps Script triggers to Cloud Scheduler dropped the `onEdit` handler that could have auto-stamped.
4. `refreshMasters` Cloud Scheduler job fires at 06:00 PHT daily but we haven't verified it has actually fired since deploy. If Procurement AppSheet data changed or wasn't readable, filtered subsets may be empty.
5. Cayla has the rollout playbook but no pre-generated QR poster for the dock. A single QR per 3PL (pointing to the form URL) would reduce supplier upload friction.

### Why this architecture

**Materials in Sheet C only (not Sheets A/B/D).** CEO directive 2026-04-21: "Is it ok to give suppliers like 3PL visibility on all our material? Maybe we make it hidden to everyone who is not Bebang.ph email?" The answer is no — exposing BEI's full SKU catalog to 3MD + Pinnacle is a competitive-information leak. 3MD and Pinnacle are separate companies; they should only see the subset of materials on POs routed to them.

**PO-line cascade in Sheets A/B/D.** The 3PL sheet only needs to see materials actually being delivered to that warehouse, which comes from the line items of POs routed to it. `Open_POs_*_Only` already filters PO headers by destination — we add a parallel `PO_Lines_*_Only` tab (lightweight filtered subset of the full PO Items table) that carries (PO Number, Material Code, Material Description, UoM, Ordered Qty, Balance) rows for that 3PL. The Receipts `Material Code` dropdown uses an INDIRECT formula against the selected PO's line items.

**Container-bound onEdit simple triggers for Timestamp.** Apps Script "simple triggers" (`onEdit` defined in a container-bound script) run under the editor's own OAuth, not the service account. No consent prompt, no domain-wide-delegation limitation — works immediately for any editor. Each of Sheets A/B/D gets its own 20-line bound script with a single `onEdit(e)` function that writes `new Date()` to column A whenever any other cell in the row is edited.

**Column A protection.** After auto-stamping, lock column A for non-BEI editors via protected range (like we did for the Open_POs_*_Only tabs in Phase 1). BEI staff retain write access in case of a correction.

**QR poster.** Single generic URL = single QR per warehouse. Print A5, laminate, post at receiving station. No per-supplier URLs, no license issues with the chart.googleapis.com or qrserver.com generator.

### Key trade-offs

| Decision | Alternative considered | Why chosen |
|---|---|---|
| Materials tab removed from A/B/D (replaced by PO-line cascade) | Keep empty Materials tab for reference | Removing eliminates confusion + blocks catalog leak. PO-line cascade gives the 3PL the correct subset at entry time. |
| `refreshMasters` pulls PO Items from Procurement AppSheet | Pull one-shot + static | PO Items change as POs are issued/closed. Daily refresh matches the existing Suppliers + PO pattern. |
| Container-bound scripts (one per Sheet A/B/D) | Add onEdit to master standalone project | Master script cannot register onEdit on arbitrary spreadsheets without installable triggers (which need OAuth consent). Bound scripts work without consent. |
| QR per-3PL vs one global QR | Per-supplier QR stickers | The form URL is identical for all — one QR suffices. Printing 3 (one per warehouse) only helps for onsite posting. |

### Known limitations + mitigations

| Limitation | Mitigation |
|---|---|
| PO Items tab schema in Procurement AppSheet not fully captured during S210 Phase 0 | Phase 0 of this sprint re-audits the tab and captures the exact column names + row count before Phase 2 depends on them. |
| Container-bound scripts created via API with `parentId=<spreadsheetId>` may require sam@bebang.ph impersonation (same fallback used for master script in S210 Phase 3) | Plan uses sam@bebang.ph by default. If creation fails for commissary.team, fallback to sam is pre-wired. |
| Simple onEdit triggers don't fire on edits made by the Apps Script API or another service (only on human UI edits) | Acceptable — pollAll reads rows regardless of who added them; the auto-timestamp is a UX convenience for human editors. |
| Cloud Scheduler `s210-refresh-masters-06` runs under sam@bebang.ph (web-app deployer); if sam's account hits a Google quota, refresh is blocked | Phase 0 force-runs via `?fn=refreshMasters` and verifies output. If systematically failing, escalate to Sam before proceeding. |

### Source references

- `F:\Dropbox\Projects\BEI-ERP\docs\plans\2026-04-20-sprint-210-tier-a-receipt-payment-infrastructure.md` — parent plan
- `F:\Dropbox\Projects\BEI-ERP\scripts\google_apps\s210_master_handler.gs` — current `refreshMasters` logic + HEADER_COLS + `_writeFilteredPOs`
- `F:\Dropbox\Projects\BEI-ERP\output\s210\SHEET_IDS.json` — all live resource IDs
- `F:\Dropbox\Projects\BEI-ERP\output\s210\PROCUREMENT_APPSHEET_BASELINE.json` — 23-tab schema of Procurement AppSheet (captured 2026-04-20)
- `F:\Dropbox\Projects\BEI-ERP\output\s210\CLOUD_SCHEDULER.json` — scheduler job config

---

## Ground-Truth Lock

**Evidence sources (concrete paths, verified to exist):**

| Path | What it proves |
|---|---|
| `F:\Dropbox\Projects\BEI-ERP\output\s210\PROCUREMENT_APPSHEET_BASELINE.json` | Procurement AppSheet tab inventory (Home, Users, Item List, Suppliers, Purchase Requisitions, Purchase Order, and ~17 more) |
| `F:\Dropbox\Projects\BEI-ERP\output\s210\SHEET_IDS.json` | Sheet A/B/C/D IDs, Apps Script project ID, form ID, web-app deployment ID |
| `F:\Dropbox\Projects\BEI-ERP\output\s210\CLOUD_SCHEDULER.json` | 4 Scheduler jobs live in `asia-southeast1` |
| `F:\Dropbox\Projects\BEI-ERP\scripts\google_apps\s210_master_handler.gs` | Canonical Apps Script source including `refreshMasters`, `_refreshPerSheetFilteredTabs`, `_writeFilteredPOs` |
| Procurement AppSheet ID `1QWdoZlT7XWLppfVKpJ2VRXhbMkYtE5TbUwg4lMbO03Q` | Source sheet owned by sam@bebang.ph; has `Item List`, `Purchase Order`, and `PO Items` (to be confirmed in Phase 0) |

**Count method:**
- Metric: `item count` — basis: rows in Procurement AppSheet `Item List` tab. Method: `COUNTA(Item List!A:A) - 1` (header row).
- Metric: `PO-line count` — basis: rows in Procurement AppSheet `PO Items` tab. Method: same pattern. Phase 0 records the exact count.
- Metric: `Open PO-line count for 3MD` — basis: rows where the parent PO's destination contains "3MD". Method: filter after pulling.

**Authoritative sections:** Phase tables with MUST_MODIFY/MUST_CONTAIN assertions. Design Rationale and Ground-Truth Lock are traceability.

**Normalization rule:** any amendment changing counts, labels, tasks, or sequences must update the authoritative phase tables in the same edit.

**Unresolved value policy:** `[UNVERIFIED — requires resolution]` for operator-facing unknowns. Never guess.

---

## Requirements Regression Checklist

Executing agent MUST verify each before claiming a phase complete.

1. `[ ]` Is the Materials tab on Sheets A/B/D deleted or explicitly left empty? (Design Rationale: no 3PL catalog exposure.)
2. `[ ]` Is the full Item List catalog seeded into Sheet C only (as a new tab `10_Full_Materials_Master`)?
3. `[ ]` Does `refreshMasters` now pull 3 tabs from Procurement AppSheet: Suppliers + Purchase Order + Item List + PO Items? (Was: only Suppliers + Purchase Order.)
4. `[ ]` Is the Material Code dropdown in Receipts tab cascaded from `PO_Lines_*_Only` filtered by the currently selected PO?
5. `[ ]` Is the Timestamp column auto-stamped by a container-bound `onEdit` simple trigger on each of Sheets A, B, D?
6. `[ ]` Is column A (Timestamp) protected from editing by non-BEI editors (3MD / Pinnacle contacts) on each of Sheets A, B, D?
7. `[ ]` Has Cloud Scheduler job `s210-refresh-masters-06` run at least once since deploy AND successfully populated `08_Full_Open_POs`?
8. `[ ]` Is the `_Instructions` tab text updated to say "Timestamp auto-fills when you start typing — don't enter it manually"?
9. `[ ]` Does the plan close cleanly: YAML status = COMPLETED, SPRINT_REGISTRY row flipped, PR #### captured, all MUST_MODIFY/MUST_CONTAIN assertions verified?

---

## Anti-Rewind / Concurrent-Run Protection Contract

- **ownership_matrix:**
  - `scripts/google_apps/s210_master_handler.gs` → sole owner: this sprint (S215). Modifies `refreshMasters`, `_refreshPerSheetFilteredTabs`, `_writeFilteredPOs`. Adds `_writeMaterialsToSheetC`, `_writePoLinesPerSheet`.
  - `output/s215/` → sole owner: this sprint. Writes ALL Phase 0-5 baseline, migration, and verification artifacts here.
  - `output/s210/ONBOARDING_3PL_COMMS.md` → UPDATE allowed (noting Materials tab removed + Timestamp auto-fill). Same document; owned by S210 historically, edit allowed.
- **protected_surfaces:**
  - S210 web-app URL (`AKfycbw...`) — must remain unchanged post-redeploy.
  - S210 Cloud Scheduler jobs (4 total) — must remain ENABLED.
  - Sheet C tabs 01-09 structure — do not add/remove tabs 01-09; Phase 1 adds tab 10.
  - S210 onFormSubmit handler (`handleSiUpload`) — preserve PO → supplier derivation logic introduced in Phase 14 + fuzzy normalization from Phase 15.
- **remote_truth_baseline:**
  - repo: `Bebang-Enterprise-Inc/hrms`
  - release_branch: `production`
  - release_head_sha: recorded in `output/s215/state/S215_REMOTE_TRUTH_BASELINE.json` at Phase 0
  - live_evidence_basis: Apps Script version 7 deployed, ping + pollAll both OK as of 2026-04-21
- **active_run_coordination:**
  - artifact: `output/s215/state/S215_ACTIVE_RUN_COORDINATION.json`
  - rule: Phase 0 claims the master script + Sheet C; any parallel S210 agent must wait or hold off on `refreshMasters` changes.

---

## Phase Budget Contract

- **phase_unit_budget:**
  - Phase 0 (baseline + preflight) → 4 units
  - Phase 1 (Materials seeding into Sheet C) → 6 units
  - Phase 2 (PO Items pull + per-3PL filtering) → 8 units
  - Phase 3 (Material Code cascade dropdown) → 5 units
  - Phase 4 (Timestamp auto-fill + column lock) → 7 units
  - Phase 5 (QR poster + _Instructions update) → 3 units
  - Phase 6 (closeout) → 4 units
- **Total: 37 units** (well under 80 ceiling)
- **hard_limit:** 15 per phase (no phase approaches)
- **preferred_split_threshold:** 12 per phase (no phase approaches)

---

## Autonomous Execution Contract

```yaml
completion_condition:
  - Materials catalog seeded into Sheet C tab 10_Full_Materials_Master (>= 50 rows)
  - Procurement AppSheet PO Items tab successfully pulled; PO-line counts recorded
  - PO_Lines_3MD_Only, PO_Lines_Pinnacle_Only, PO_Lines_Shaw_Only tabs populated on A/B/D
  - Material Code dropdown in each Receipts tab cascades via INDIRECT from selected PO's line items
  - Container-bound Apps Script with onEdit exists on each of Sheets A, B, D (verified via script listing)
  - Column A protected range set on each of Sheets A, B, D with only @bebang.ph editors
  - Cloud Scheduler s210-refresh-masters-06 has fired at least once post-deploy AND pollAll shows non-zero receipts routable through the pipeline
  - QR poster (A5) generated for each warehouse, saved as output/s215/qr_posters/*.pdf, uploaded to Drive Training folder
  - _Instructions tab updated on Sheets A, B, D with new Timestamp wording + no-catalog-exposure notice
  - Plan YAML status: GO -> COMPLETED with completed_date + execution_summary
  - SPRINT_REGISTRY S215 row: PLANNED -> COMPLETED + PR link
  - PR created with all commits on s215-s210-ops-polish branch
stop_only_for:
  - Procurement AppSheet PO Items tab inaccessible or has unexpected schema → present options
  - Container-bound script creation blocked by Apps Script API (needs separate publisher setup) → present options
  - Sam's account hits Google quota preventing Cloud Scheduler execution → escalate
  - Destructive action on production sheets needing explicit consent → pause and ask
  - Business-policy decision (e.g. who gets Materials visibility beyond @bebang.ph) → pause
continue_without_pause_through:
  - baseline_preflight
  - materials_seeding
  - po_items_pull
  - cascade_dropdown
  - onedit_triggers_and_protection
  - qr_poster_generation
  - closeout
  - pr_creation
blocker_policy:
  - programmatic Apps Script error -> fix and continue
  - permission denial on a sheet write -> retry once, escalate if persists
  - Cloud Scheduler execution fail x3 -> debug + research, then continue
  - business-data/policy -> pause
signoff_authority: single-owner (Sam Karazi, CEO — single finance approver while CFO seat vacant)
canonical_closeout_artifacts:
  - output/s215/RUN_STATUS.json
  - output/s215/RUN_SUMMARY.md
  - output/s215/verify_phase_6.py (passes all prior phase verifiers)
  - output/s215/qr_posters/ (3 PDFs)
  - docs/plans/2026-04-21-sprint-215-s210-ops-polish.md (YAML flipped to COMPLETED)
  - docs/plans/SPRINT_REGISTRY.md (S215 row flipped to COMPLETED with PR link)
```

---

## Zero-Skip Enforcement

Every task MUST be implemented. No exceptions. If a task cannot be completed, the agent STOPS and asks Sam.

**Forbidden:**
- Skipping a task silently
- Marking partial work as "done"
- Replacing a task with a simpler version without user approval
- Saying "deferred to next sprint"
- Combining tasks and dropping features in the merge
- Implementing happy path only, skipping edge cases

**Phase completion contract:** after each phase, the executing agent runs the phase verifier:

```
python output/s215/verify_phase_N.py
```

If exit != 0, FIX before advancing. Verifier must use filesystem evidence (file existence, row counts via Sheets API, `grep` against `.gs`) — not prose checklists.

---

## Phases

### Phase 0 — Baseline + Preflight (4 units)

Goal: capture pre-change state, verify Procurement AppSheet access, lock the exact PO Items + Item List schema before any write.

| # | Task | MUST_MODIFY / MUST_CONTAIN | Unit |
|---|---|---|---|
| 0.1 | Capture baseline: current row counts in Procurement AppSheet `Item List`, `Purchase Order`, `PO Items` tabs. Save to `output/s215/PROCUREMENT_BASELINE_S215.json`. Include column headers for each. | MUST_MODIFY: `output/s215/PROCUREMENT_BASELINE_S215.json` CONTAINS `item_list_row_count` + `po_items_row_count` + `po_items_headers` | 1 |
| 0.2 | Capture Sheet C tab 08_Full_Open_POs current row count + sample. If empty (refreshMasters hasn't fired successfully), record that and plan to force-run in Phase 0.4. | MUST_MODIFY: `output/s215/SHEET_C_BASELINE.json` with `open_pos_rowcount` | 1 |
| 0.3 | Capture Sheet A/B/D `_Instructions` + `Materials` + `Open_POs_*_Only` current state: row counts, cell contents. | MUST_MODIFY: `output/s215/THREEPL_SHEETS_BASELINE.json` | 1 |
| 0.4 | If 08_Full_Open_POs has 0 rows, force-run `refreshMasters` via the web-app (`GET /exec?fn=refreshMasters&key=<TOKEN>`) and re-check. Record response in `output/s215/refreshMasters_response.json`. | MUST_MODIFY: `output/s215/refreshMasters_response.json` CONTAINS `"ok":true` | 1 |
| 0.5 | Verify: `python output/s215/verify_phase_0.py` exits 0 | exits 0 | — |

### Phase 1 — Materials seeding to Sheet C (6 units)

Goal: pull full Item List catalog from Procurement AppSheet into Sheet C as a new tab `10_Full_Materials_Master`. BEI-internal only.

| # | Task | MUST_MODIFY / MUST_CONTAIN | Unit |
|---|---|---|---|
| 1.1 | Create Sheet C tab `10_Full_Materials_Master` with headers: `Item Code, Item Name, UoM, Category, VAT, Unit Price, Packaging, Added By, Status` (adjust based on Phase 0.1 column audit). | MUST: tab `10_Full_Materials_Master` exists on Sheet C | 1 |
| 1.2 | Extend `refreshMasters` in `s210_master_handler.gs` to pull Procurement AppSheet `Item List` tab. Add `_writeMaterialsToSheetC(masterSs)` function (same replace-in-place semantics as `07_Full_Suppliers_Master`). | MUST_MODIFY: `scripts/google_apps/s210_master_handler.gs` CONTAINS function `_writeMaterialsToSheetC` | 2 |
| 1.3 | Redeploy updated `.gs` via `phase10_redeploy.py` → new version number → deployment update. | MUST: `output/s215/deployment_v8.log` captures version and URL | 1 |
| 1.4 | Force-run `refreshMasters` and verify `10_Full_Materials_Master` populated (≥ 50 rows). | MUST: Sheet C tab `10_Full_Materials_Master` row count ≥ 50 | 1 |
| 1.5 | Delete the (empty) Materials tab from Sheets A, B, D — or protect it and add a comment in row 2 saying "Reserved for PO-filtered line items — see `Open_POs_*_Only` and Material Code dropdown on Receipts". | MUST: Sheet A + B + D Materials tab either removed OR row 2 has the placeholder note | 1 |

### Phase 2 — PO Items pull + per-3PL filtering (8 units)

Goal: pull PO Items from Procurement AppSheet into a new Sheet C tab, then write a per-3PL filtered subset to Sheets A/B/D as `PO_Lines_*_Only` tabs.

| # | Task | MUST_MODIFY / MUST_CONTAIN | Unit |
|---|---|---|---|
| 2.1 | Add Sheet C tab `11_Full_PO_Lines` with headers: `PO Number, Line #, Material Code, Material Description, UoM, Ordered Qty, Balance, Unit Price, Destination 3PL`. Source: Procurement AppSheet `PO Items` (schema from Phase 0.1). | MUST: tab `11_Full_PO_Lines` exists on Sheet C | 2 |
| 2.2 | Extend `refreshMasters` with `_writePoLinesToSheetC()` — pulls PO Items, joins to Open POs for Destination 3PL. Replace-in-place daily. | MUST_MODIFY: `.gs` CONTAINS function `_writePoLinesToSheetC` | 2 |
| 2.3 | Add Sheets A/B/D new tab `PO_Lines_3MD_Only` / `PO_Lines_Pinnacle_Only` / `PO_Lines_Shaw_Only` (whatever the naming convention allows). Same 9-col header as `11_Full_PO_Lines`. | MUST: new tab exists on each of A, B, D | 1 |
| 2.4 | Add `_writeFilteredPoLines(ss, tabName, poLinesData, destFilter)` helper in `.gs`. Filter `11_Full_PO_Lines` by Destination 3PL substring match, write per-sheet. Protected from external editor. | MUST_MODIFY: `.gs` CONTAINS function `_writeFilteredPoLines` | 2 |
| 2.5 | Redeploy + force-run `refreshMasters` + verify each `PO_Lines_*_Only` has > 0 rows (assuming Procurement AppSheet has routed POs). | MUST: A's `PO_Lines_3MD_Only` + B's `PO_Lines_Pinnacle_Only` populated | 1 |

### Phase 3 — Material Code cascade dropdown (5 units)

Goal: in each Receipts tab, the Material Code column dropdown shows only materials from the line items of the PO selected in the same row.

| # | Task | MUST_MODIFY / MUST_CONTAIN | Unit |
|---|---|---|---|
| 3.1 | Create a named range per sheet for each PO's line-item Material Codes. Use `INDIRECT` with a helper column (e.g. Receipts column Z) that resolves the PO number to a range reference like `PO_Lines_3MD_Only!C2:C999` filtered. | MUST: Receipts row 2 has `INDIRECT` data validation on Material Code (column F) | 2 |
| 3.2 | Apply the data validation to all new rows via `Range.setDataValidation()` (Apps Script) or Sheets API `batchUpdate` with `setDataValidation`. | MUST: Apps Script API call success response in `output/s215/cascade_setup.log` | 2 |
| 3.3 | Re-test dropdown manually: select a PO, confirm Material Code list is filtered. If INDIRECT approach doesn't work across arbitrary rows (common Sheets limitation), fall back to an onEdit trigger (part of Phase 4) that rewrites the validation per row. | MUST: `output/s215/cascade_test_evidence.md` documents approach chosen | 1 |

### Phase 4 — Timestamp auto-fill + column lock (7 units)

Goal: 3PL typing any cell in a new row auto-stamps column A with `new Date()`. Column A protected so only BEI editors can override.

| # | Task | MUST_MODIFY / MUST_CONTAIN | Unit |
|---|---|---|---|
| 4.1 | For each of Sheets A, B, D: create a container-bound Apps Script project via Apps Script API with `parentId=<sheetId>`. Source: `scripts/google_apps/s215_onedit_timestamp.gs`. | MUST_MODIFY: `scripts/google_apps/s215_onedit_timestamp.gs` exists | 1 |
| 4.2 | The bound script contains a simple `onEdit(e)` function: if edit is on Receipts tab, row > 1, column A is blank, set column A to `new Date()`. Also include `onOpen(e)` custom menu for BEI staff to "Clear my test row timestamp" (optional). | MUST_CONTAIN: `function onEdit(e)` + `new Date()` assignment | 2 |
| 4.3 | Per sheet, save the script ID + deployment status to `output/s215/bound_scripts.json`. If creation via API fails, fall back to manual deploy via Apps Script editor (document clearly). | MUST_MODIFY: `output/s215/bound_scripts.json` CONTAINS 3 script entries | 2 |
| 4.4 | Apply protected range on column A of each Receipts tab: allow only @bebang.ph editors. Use Sheets API `addProtectedRange`. | MUST: each of Sheets A/B/D Receipts column A has a protected range with `editors.users` containing only @bebang.ph addresses | 1 |
| 4.5 | Update `_Instructions` tab text: "Timestamp auto-fills when you start typing — don't enter it manually." Remove "REQUIRED — row is skipped if blank". Re-push via Sheets API. | MUST: `_Instructions` tab A-col contains "auto-fills" | 1 |

### Phase 5 — QR poster + onboarding update (3 units)

Goal: generate 3 printable A5 QR posters (one per warehouse pointing to the form URL), upload to Drive for Cayla to print.

| # | Task | MUST_MODIFY / MUST_CONTAIN | Unit |
|---|---|---|---|
| 5.1 | Generate 3 QR posters via `qrserver.com` + DOCX layout (A5, large QR, warehouse name, "Upload your SI here — fastest path to payment"). Save as `output/s215/qr_posters/3MD.pdf`, `Pinnacle.pdf`, `Shaw.pdf` (render DOCX→PDF for print). | MUST: 3 PDFs in `output/s215/qr_posters/` | 2 |
| 5.2 | Upload the 3 PDFs + 3 DOCX to Drive Training folder (id `1zTUtXk4SfWekqv1bNbPybZZKCheIcPru`). Update `output/s215/qr_posters/MANIFEST.json` with links. | MUST: `output/s215/qr_posters/MANIFEST.json` contains 3 Drive URLs | 1 |

### Phase 6 — Closeout (4 units)

| # | Task | MUST_MODIFY / MUST_CONTAIN | Unit |
|---|---|---|---|
| 6.1 | Write `output/s215/verify_phase_6.py` that runs all prior phase verifiers + checks: (a) `10_Full_Materials_Master` ≥ 50 rows, (b) `PO_Lines_*_Only` tabs populated on A/B, (c) 3 bound scripts registered with onEdit, (d) column A protected on A/B/D, (e) 3 QR PDFs exist, (f) plan YAML = COMPLETED, (g) registry row = COMPLETED. | MUST: `verify_phase_6.py` exits 0 | 2 |
| 6.2 | Update plan YAML: `status: GO → COMPLETED`, fill `completed_date`, write `execution_summary` summarizing phase outcomes + live verification. | MUST: plan YAML `status: COMPLETED` | 1 |
| 6.3 | Update `docs/plans/SPRINT_REGISTRY.md` S215 row: `PLANNED → COMPLETED` with PR link. `git add -f` both files. | MUST: registry row contains `COMPLETED` | 1 |
| 6.4 | Create PR via `GH_TOKEN="" gh pr create` on branch `s215-s210-ops-polish` targeting `production`. PR URL captured in `output/s215/PR_URL.txt`. | MUST: `output/s215/PR_URL.txt` exists with valid URL | — |

---

## Agent Boot Sequence

1. Read this plan fully (all sections including Design Rationale + Requirements Regression Checklist).
2. **Create sprint branch:** `git fetch origin production && git checkout -b s215-s210-ops-polish origin/production`. NEVER write code on production.
3. Read `docs/plans/SPRINT_REGISTRY.md` for cross-sprint context + confirm no collision on S215.
4. Read S210 parent plan (`docs/plans/2026-04-20-sprint-210-tier-a-receipt-payment-infrastructure.md`) for architecture context.
5. Read `output/s210/SHEET_IDS.json` + `output/s210/CLOUD_SCHEDULER.json` to confirm live resource IDs.
6. Read `scripts/google_apps/s210_master_handler.gs` to understand current refreshMasters + `_writeFilteredPOs` patterns (you'll be extending them).
7. Confirm credentials file exists: `F:\Dropbox\Projects\BEI-ERP\credentials\task-manager-service.json`.
8. Begin Phase 0.

---

## Execution Authority

This sprint is intended for autonomous end-to-end execution. Do not stop for progress-only updates. Only pause for items listed in the Autonomous Execution Contract `stop_only_for` section.

---

## Execution Workflow

- Test `.gs` changes: redeploy via `phase10_redeploy.py` (already in `output/s210/`) → ping + pollAll → visual check Sheet C
- No Python unit tests (Apps Script not locally runnable)
- No `/local-frappe` (no Frappe code)
- Deploy: Apps Script API `projects.versions.create` + `projects.deployments.update`
- Closeout: Phase 6 tasks

---

## Not in scope

- Frappe code changes (canonical_scope = none)
- Employee Master changes
- Store/Company/Warehouse mutations
- Billing / AP workflow changes
- New Cloud Scheduler jobs (the existing 4 cover this sprint's needs)
- Training video recording
