# Sprint S140 — Warehouse Setup + Full Inventory Re-sync

```yaml
sprint: S140
branch: — (data-only sprint, no code changes)
status: PLANNED
plan_file: docs/plans/2026-03-28-sprint-140-warehouse-setup-inventory-resync.md
depends_on: S139
registry_row: "| S140 | Sprint 140 | — (data-only, no code) | — | PLANNED — Warehouse setup + full 46-store inventory re-sync via /frappe-bulk-edits. |"
completed_date:
execution_summary:
```

---

## Why This Exists

S139 inventory sync testing revealed two critical problems:
1. **The shadow sync code reads column A (empty) instead of column B (item codes)** — the Google Sheets have item codes in column B, not column A. Every previous sync produced zero data from store sheets.
2. **BKI warehouses don't exist in Frappe** — S138 changed code constants (`store.py`) but never created the actual BKI company or warehouses in Frappe.
3. **4 stores are wrongly tagged as BKI** in the sync registry — NAIA, SM Sta. Rosa, SM Taytay, and Greenhills Ortigas are BEI stores.

The database is currently clean (all inventory wiped via `/frappe-bulk-edits` Recipe 1 on 2026-03-28).

## Approach

**No automated syncs.** This sprint uses a manual, verified pipeline:
1. Disable all syncs to prevent stale data from re-entering
2. Download Google Sheets locally via `/extract-data`
3. Process and validate extracted data
4. `/fact-check-bei-erp` before upload
5. Upload via `/frappe-bulk-edits` (SSM → Docker → Frappe)
6. `/fact-check-bei-erp` after upload
7. Re-enable syncs only after fact-check passes

---

## GATE 0: Warehouse List Review (BLOCKER — Sam Must Approve Before Execution)

**Sam must review and confirm this warehouse list before ANY execution begins.**

### BKI Warehouses (Bebang Kitchen Inc.) — 6 total

| # | Warehouse Name | Type | Notes |
|---|---------------|------|-------|
| 1 | Shaw BLVD | Commissary / Main Warehouse | BKI headquarters |
| 2 | 3MD Logistics - Camangyanan | 3PL Cold Storage | External storage |
| 3 | Pinnacle Cold Storage Solutions | 3PL Cold Storage | External storage |
| 4 | Jentec Storage Inc. | 3PL Storage | External storage |
| 5 | Royal Cold Storage - Taytay (RCS) | 3PL Cold Storage | External storage |
| 6 | Commissary | Production facility | If separate from Shaw BLVD |

### BEI Stores (Bebang Enterprise Inc.) — 46 total

All 46 stores in the shadow sync registry are BEI, including:
- NAIA T3 (currently wrongly tagged BKI in registry)
- SM Sta. Rosa (currently wrongly tagged BKI in registry)
- SM Taytay (currently wrongly tagged BKI in registry)
- Greenhills Ortigas (currently wrongly tagged BKI in registry)

### Questions for Sam:
1. Is "Commissary" a separate warehouse from "Shaw BLVD" or the same location?
2. Are there any other BKI warehouses missing from this list?
3. Should Estancia (exists in Frappe as BEI but not in sync registry) be added?
4. Confirm: NAIA, SM Sta. Rosa, SM Taytay, Greenhills are all BEI stores, correct?

**HARD BLOCKER:** Do not proceed past Gate 0 until Sam confirms the warehouse list.

---

## Phase A: Disable All Inventory Syncs (2 units)

Prevent any sync from running during the re-sync window.

| Task | Action | Skill |
|------|--------|-------|
| A1 | Disable cron for `enqueue_scheduled_store_inventory_shadow_sync` in hooks.py | Manual comment-out or set flag |
| A2 | Disable cron for `enqueue_scheduled_store_demand_snapshot_sync` | Same |
| A3 | Disable watchdog `watch_store_inventory_shadow_sync_health` | Same |
| A4 | Verify sheets-receiver inventory sync won't trigger (checksum-gated, safe if no sheet changes) | Check config |

**HARD BLOCKER:** Syncs must be disabled BEFORE any data operations. If the 7 AM PHT cron fires during upload, it will create duplicate/conflicting Stock Reconciliations.

**Approach options (present to Sam):**
- Option 1: Comment out the 3 cron entries in `hooks.py`, deploy, re-add after
- Option 2: Add a `SYNC_DISABLED=1` flag check at the top of the enqueue function (no deploy needed if set via site config)
- Option 3: Execute during 2-4 AM PHT window (before 7 AM cron), finish before it fires

---

## Phase B: Create BKI Warehouses in Frappe (3 units)

| Task | Action | Skill |
|------|--------|-------|
| B1 | Create BKI company in Frappe (if not exists) | `/frappe-bulk-edits` |
| B2 | Create BKI warehouses (Shaw BLVD, 3MD, Pinnacle, Jentec, RCS, Commissary) | `/frappe-bulk-edits` |
| B3 | Create Temporary Opening account for BKI (required for Stock Reconciliation) | `/frappe-bulk-edits` |

**Note:** B1 may already be done from S138. Verify first.

---

## Phase C: Fix Sync Registry (1 unit)

| Task | Action |
|------|--------|
| C1 | Update `hrms/fixtures/store_inventory_shadow_sync/store_inventory_shadow_sync_registry.csv` — change warehouse_docname for NAIA, SM Sta. Rosa, SM Taytay, Greenhills from BKI to BEI suffix |

---

## Phase D: Extract Inventory Data from Google Sheets (5 units)

| Task | Action | Skill |
|------|--------|-------|
| D1 | Download all 46 store Google Sheets `3. INVENTORY` tab locally | `/extract-data` via Google Sheets API |
| D2 | Parse each sheet: column B = item codes, find ENCODE column (varies per sheet — must discover per-sheet) | Python processing |
| D3 | Validate item codes exist in Frappe Item master | Cross-reference check |
| D4 | Resolve warehouse names (store_code → Frappe warehouse docname) | Registry lookup |
| D5 | Write consolidated payload to `tmp/s140_inventory_payload.json` | Output file |

**CRITICAL LESSON:** Do NOT assume all sheets have the same format. The ENCODE column position varies. Check each sheet individually. Column A is ALWAYS empty (buttons/images). Item codes are in column B. The ENCODE (total qty) column must be discovered per sheet by finding the header row.

**Column discovery approach:**
1. Read row 6-7 to find header
2. Look for "ENCODE" or "Total" column header
3. Extract item_code from column B, qty from the discovered ENCODE column
4. Skip rows where item_code doesn't match known Item codes in Frappe

---

## Phase E: Fact-Check Before Upload (2 units)

| Task | Action | Skill |
|------|--------|-------|
| E1 | `/fact-check-bei-erp` — verify extracted item counts match Google Sheet row counts per store | Programmatic Layer 1 |
| E2 | Spot-check 5 stores: compare extracted qty values against Google Sheet cell values | Manual verification |

**Gate:** If >5% of items fail validation, STOP and investigate before uploading.

---

## Phase F: Upload to Frappe (4 units)

| Task | Action | Skill |
|------|--------|-------|
| F1 | Upload BKI warehouse inventory (6 warehouses) via `/frappe-bulk-edits` | SSM → Docker → Stock Reconciliation |
| F2 | Upload BEI store inventory (46 stores) via `/frappe-bulk-edits` | SSM → Docker → Stock Reconciliation |
| F3 | Commit per-warehouse (frappe.db.commit() after each SR submit) | Already in code from S138 PR #386 |
| F4 | Verify zero errors in upload output | Check stdout |

**Batch approach:** Upload in batches of 10 stores per SSM command to avoid timeout. 5 batches total.

---

## Phase G: Fact-Check After Upload (3 units)

| Task | Action | Skill |
|------|--------|-------|
| G1 | `/fact-check-bei-erp` — for each of 46 stores, compare Frappe Bin qty vs Google Sheet ENCODE qty | Programmatic Layer 1 |
| G2 | Verify BKI warehouse Bins match source data | Same |
| G3 | Generate verification report: `tmp/s140_verification_report.md` with per-store pass/fail | Report |

**Gate:** ALL 46 stores must have matching item counts (Frappe Bins vs Google Sheet). Any mismatch = investigate and fix before proceeding.

---

## Phase H: Re-enable Syncs + Closeout (2 units)

| Task | Action |
|------|--------|
| H1 | Re-enable the 3 cron entries disabled in Phase A |
| H2 | Update plan status to COMPLETED, update SPRINT_REGISTRY.md |

**HARD BLOCKER:** Do NOT re-enable syncs until Phase G fact-check passes with 100% match.

---

## Total: 22 units across 8 phases

| Phase | Units | Description |
|-------|-------|-------------|
| Gate 0 | 0 | Sam reviews warehouse list (BLOCKER) |
| A | 2 | Disable syncs |
| B | 3 | Create BKI warehouses |
| C | 1 | Fix registry |
| D | 5 | Extract from Google Sheets |
| E | 2 | Fact-check before upload |
| F | 4 | Upload to Frappe |
| G | 3 | Fact-check after upload |
| H | 2 | Re-enable syncs + closeout |

---

## Requirements Regression Checklist

- [ ] Are all syncs disabled before any data operations? (Phase A)
- [ ] Has Sam confirmed the warehouse list? (Gate 0)
- [ ] Is column B (not A) being read for item codes from Google Sheets?
- [ ] Is the ENCODE column discovered per-sheet (not hardcoded)?
- [ ] Are NAIA, SM Sta. Rosa, SM Taytay, Greenhills tagged as BEI (not BKI)?
- [ ] Does every uploaded item_code exist in Frappe Item master?
- [ ] Is fact-check run BEFORE upload (Phase E) and AFTER upload (Phase G)?
- [ ] Are syncs re-enabled ONLY after fact-check passes?

---

## Autonomous Execution Contract

- completion_condition:
  - Gate 0 warehouse list approved by Sam
  - All 46 stores + BKI warehouses have inventory in Frappe
  - Post-upload fact-check passes 100%
  - Syncs re-enabled
  - Plan + registry updated to COMPLETED
- stop_only_for:
  - Gate 0: Sam must approve warehouse list
  - Phase A: Sam must approve sync disable approach
  - Phase E/G: >5% fact-check failures require investigation
- continue_without_pause_through:
  - B, C, D, F (data operations once approved)
- blocker_policy:
  - missing Item in Frappe -> skip item, log to exceptions
  - Google Sheet API error -> retry 3x, then flag store
  - SSM timeout -> split into smaller batches
- signoff_authority: single-owner (Sam)

---

## Design Rationale (For Cold-Start Agents)

**Why manual pipeline instead of automated sync?**
The automated shadow sync (`store_inventory_shadow_sync.py`) reads column A of the Google Sheets, which is empty. The item codes are in column B. Fixing the sync code would require a code change + deploy + re-test cycle. The manual pipeline (download → process → upload) bypasses this bug entirely and gives us full control over validation.

**Why disable syncs?**
If the 7 AM PHT cron fires while we're uploading, it will create competing Stock Reconciliations. The sheets-receiver's inventory sync (Ian's sheet) could also push stale data. Both must be paused.

**Why `/frappe-bulk-edits` instead of the sync API?**
The sync API (`erp_sync.sync_inventory`) has the column A bug. Direct Frappe insertion via SSM is the proven path (tested today with 5 stores, 231 items, zero failures).

**Why fact-check twice?**
Pre-upload fact-check catches extraction errors (wrong column, bad parsing). Post-upload fact-check catches Frappe insertion errors (missing Items, batch creation failures, valuation rate issues). Both are needed because the error modes are different.
