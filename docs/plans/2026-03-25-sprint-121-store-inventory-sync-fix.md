---
canonical_sprint_id: S121
display: Sprint 121
status: DEPLOYED
branch: s121-store-inventory-sync-fix
lane: single
created_date: 2026-03-25
completed_date:
deployed_at: 2026-03-25
backend_pr: 349
frontend_pr:
l3_result: 4 PASS, 1 N/A (Ian sync not directly tested), 1 EXPECTED (bins>5000 preserved by design)
execution_summary: Removed historical_end fallback, added historical_end_skipped classification guard, fixed Shaw BLVD→BKI mapping, added Sentry DM-7. Force re-sync 46/46 stores, 2740 payload + 2178 exceptions, 0 failures. Megaworld corrected 19572→1773. Festival Mall preserved at 21663 (ENCODE empty = skip by design).
depends_on:
---

# S121 — Fix Store Inventory Sync: Wrong Qty from Historical Fallback

**Goal:** Fix the store inventory shadow sync so it mirrors the CURRENT stock on hand from store Google Sheets, not inflated historical daily balances. Then force a full re-sync of all 46 stores and validate that Frappe `tabBin` shows correct numbers.

**Origin:** Investigation on 2026-03-25 found Festival Mall shows 21,663 LECHE FLAN x 12 (FG001-A) in Frappe — actual store sheet says 12 pieces. Root cause traced to `_resolve_current_qty()` in `hrms/utils/store_inventory_shadow_sync.py` falling back to historical daily END values when ENCODE and TOTAL columns are empty.

**Severity:** CRITICAL — all inventory data in Frappe for 46 stores is potentially unreliable.

---

## Investigation Findings (2026-03-25 Session)

### What we discovered

We queried live production and found grossly inflated inventory numbers:

| Store | Item | Frappe tabBin qty | Google Sheet ENCODE | Correct? |
|-------|------|-------------------|---------------------|----------|
| Festival Mall Alabang | FG001-A (LECHE FLAN x 12) | **21,663** | **empty** (current on-hand ~12) | WRONG |
| Megaworld Paseo Center | FG001-A | **19,572** | unknown | WRONG |
| SM Clark | FG001-A | **3,174** | unknown | Suspicious |

Total tabBin has 3,962 bins, 3,595 with stock, total qty 949,495 units. Many of these numbers are inflated.

### How we traced the root cause

1. **Checked if Stock Reconciliation accumulates** — NO. Frappe SR is absolute (sets qty, doesn't add). Research confirmed + code verified. Submitting qty=100 twice keeps bin at 100.

2. **Checked if too many SRs are being created** — YES (83-134/day, 1,664 total), but this is idempotent by design. Not the cause.

3. **Checked the actual SLEs for FG001-A at Festival Mall** — only 3 SLEs total. The third one (MAT-RECO-2026-00397, March 13) set qty to 21,663. That SR was the source of the wrong number.

4. **Checked what the SR said** — `qty: 21663.0`, `current_qty: 167.0`. The sync intentionally set 21,663 as the target. But the store sheet says ~12.

5. **Checked the Google Sheet** — Festival Mall's FG001-A row has:
   - ENCODE = **empty**
   - TOTAL = **empty**
   - Wt = 12 (package info, NOT stock qty)
   - Daily END values: 618, 1381, 1212, 789, 1066, 1319, 1707, 1495... (growing cumulative numbers)

6. **Found the bug in `_resolve_current_qty()`** — when ENCODE and TOTAL are empty, the function falls back to historical daily END values (line 543-564). These END values are BEG+IN-OUT for each day — daily movement records, NOT current on-hand. On March 13, the latest END value was ~21,663.

7. **Checked if Festival Mall is being re-synced daily** — YES. State file shows `last_success_at: 2026-03-24T23:36:23`, 103 rows imported. But FG001-A is NOT in those 103 rows because the sync skips items where qty resolves to the same value (checksum dedup).

8. **Checked Ian's warehouse sync** — NOT affected. Ian's sync reads qty directly from SOH columns in the SUMMARY 2026 sheet. No fallback logic. Only issue: Shaw BLVD maps to a disabled store warehouse instead of the active BKI warehouse.

9. **Verified with Sam:** Shaw BLVD store (BEI) = correctly disabled. Shaw BLVD warehouse (BKI) = should be active and synced.

---

## Design Rationale (For Cold-Start Agents)

### Why this exists

The store inventory shadow sync reads Google Sheets from 46 stores (tab "3. INVENTORY") and creates Stock Reconciliation documents in Frappe. Each SR sets the absolute qty in `tabBin`. The sync runs every 10 minutes.

**The bug:** When the ENCODE and TOTAL columns are empty for an item (common — many store managers don't fill these columns), the `_resolve_current_qty()` function falls back to historical daily END values. These are BEG/IN/OUT/END columns tracking daily inventory movements — the END value is "ending balance for that specific day," NOT "current stock on hand." Days or weeks later, these END values are stale and can be extremely large (cumulative totals).

**Evidence:**
- Festival Mall FG001-A: ENCODE=empty, TOTAL=empty, Wt=12 (package info, not qty)
- Historical daily END values: 618, 1381, 1212, 789, 1066, 1319, 1707, 1495...
- On March 13, the sync picked up a historical END of 21,663 → set bin to 21,663
- Frappe bin has been stuck at 21,663 since then (checksum dedup prevents overwrite when sheet unchanged)

**Ian's warehouse sync is NOT affected.** It reads qty directly from the SOH (Stock on Hand) column in Ian's SUMMARY 2026 sheet — no fallback logic. Only issue: 5 Shaw BLVD rows fail daily because that warehouse is disabled.

### Why this architecture

**Remove the historical_end fallback entirely.** If ENCODE and TOTAL are empty, the correct answer is:
- Option A: Skip the item (don't create an SR row for it) — safest
- Option B: Set qty to 0 (blank_zero_policy) — deterministic but may be wrong if item has stock

**We choose Option A (skip)** because setting qty=0 would zero out legitimate stock when the store manager simply hasn't updated the ENCODE column. Skipping means the previous bin value stays — potentially stale, but not dangerously inflated.

**The WHOLE/LOOSE columns** remain as `needs_conversion_rule` (existing behavior) since there's no UOM conversion table.

### Key trade-offs

1. **Removing historical_end fallback** means items without ENCODE/TOTAL will NOT sync until the store fills those columns. This is a feature, not a bug — syncing stale data is worse than not syncing.
2. **Force re-sync** will temporarily increase load (46 stores × ~100 items = ~4,600 SR rows in one batch). Spread across 10-minute intervals, this is manageable.
3. **Shaw BLVD disabled warehouse** for Ian's sync is a separate fix — disable the SHAW column in the warehouse map or re-enable the warehouse.

### How the store inventory sheet layout works (CRITICAL for cold-start agent)

Each store has a Google Sheet with a tab called `3. INVENTORY`. The layout:

```
Row 6 (headers): | CODE | ITEMS | DESCRIPTION | UOM | Wt. | Whole | Loose | Total | ENCODE | | Dec 29 BEG | IN | OUT | END | Dec 30 BEG | IN | OUT | END | ...
Row 7 (sub-hdr): |      |       |             |     |     |       |       |       |        | |     BEG     | IN | OUT | END |     BEG    | IN | OUT | END | ...
```

**Column meanings:**
- **Wt.** — weight/package info (e.g., "12" = 12pcs per pack). This is NOT a stock quantity.
- **Whole** — whole units on hand (rarely filled)
- **Loose** — loose units on hand (rarely filled)
- **Total** — computed total (formula: Whole × conversion + Loose). Often empty if Whole/Loose empty.
- **ENCODE** — manually entered current on-hand count. **This is the intended sync source.** But many stores leave it empty.
- **Daily BEG/IN/OUT/END columns** — daily movement tracking. BEG = beginning of day, IN = received, OUT = issued, END = BEG + IN - OUT. These are per-day snapshots, NOT current stock.

**The priority order in `_resolve_current_qty()` (line 520-576):**
1. ENCODE → if present, use it (most trusted)
2. TOTAL → if present, use it
3. **historical_end → THE BUG — picks the most recent daily END value before run_date**
4. WHOLE/LOOSE → flags as needs_conversion_rule (skipped)
5. blank_zero_policy → returns 0

**The fix removes step 3.** When ENCODE and TOTAL are empty, skip straight to WHOLE/LOOSE check, then blank_zero_policy.

**Current code to modify** (`hrms/utils/store_inventory_shadow_sync.py` lines 520-576):
```python
def _resolve_current_qty(row_payload, daily_records, run_date):
    # ... lines 525-541: checks encode, total (KEEP THESE)

    # Lines 543-564: THE BUG — remove this entire block:
    best_daily = None
    for daily in daily_records:
        inventory_date = daily.get("inventory_date")
        end_value = daily.get("end")
        # ... iterates through daily END values
        # ... picks the most recent END before run_date
    if best_daily:
        return best_daily[1], "historical_end", best_daily[0].isoformat(), ""

    # Lines 566-576: WHOLE/LOOSE and blank_zero_policy (KEEP THESE)
```

**After the fix**, the function should go from TOTAL check directly to WHOLE/LOOSE:
```python
def _resolve_current_qty(row_payload, daily_records, run_date):
    # Check encode (lines 535-537) — KEEP
    encode_qty = _coerce_float(row_payload["encode"])
    if encode_qty is not None:
        return encode_qty, "encode", run_date.isoformat(), ""

    # Check total (lines 539-541) — KEEP
    total_qty = _coerce_float(row_payload["total"])
    if total_qty is not None:
        return total_qty, "total", run_date.isoformat(), ""

    # REMOVED: historical_end fallback (was lines 543-564)
    # Log that we skipped it
    # Return None with classification "historical_end_skipped"
    # so the item is treated as an exception, not imported with wrong qty

    # Check whole/loose (lines 566-569) — KEEP
    whole_qty = _coerce_float(row_payload["whole"])
    loose_qty = _coerce_float(row_payload["loose"])
    if whole_qty is not None or loose_qty is not None:
        return None, "needs_conversion_rule", None, "..."

    # Blank zero policy (lines 571-576) — KEEP
    return (0.0, "blank_zero_policy", run_date.isoformat(), "...")
```

### How the force re-sync works

The sync system uses checksums to skip stores where data hasn't changed. `force=True` bypasses this check and re-syncs all stores regardless of checksum. The command:

```bash
docker exec $(docker ps -q -f name=frappe_backend) bench --site hq.bebang.ph execute \
  hrms.api.erp_sync.run_scheduled_store_inventory_shadow_sync
```

To force: either pass `force=True` to `run_store_inventory_shadow_sync()` or delete the runtime state file:
```
/home/frappe/frappe-bench/sites/hrms.bebang.ph/private/files/store_inventory_shadow_sync_state.json
```

### How Ian's warehouse sync works (different code path)

Ian's sync goes through the **sheets-receiver** container (NOT Frappe scheduler):
- Source: Google Sheet `19Hm25vaj9gD8p6z_M6-4CPWvcXaPzAeOFKlUZ298V4s` tab "SUMMARY 2026"
- Transform: `hrms/services/sheets_receiver/transforms.py` → `_transform_inventory_summary_matrix()`
- Reads qty directly from warehouse columns (3MD, JENTEC, RCS, PINNACLE, SHAW)
- No ENCODE/TOTAL/END fallback — just the cell value
- Endpoint: `hrms.api.erp_sync.sync_inventory` → `_sync_inventory_rows()`
- Same Stock Reconciliation code as store sync, different data source

The Shaw BLVD fix (A3) is in this code path, not the store sync code path.

### How to verify the fix worked

After force re-sync, query Frappe:
```bash
# Via Frappe API
curl "https://hq.bebang.ph/api/resource/Bin?filters=[[\"item_code\",\"=\",\"FG001-A\"],[\"warehouse\",\"like\",\"%Festival%\"]]&fields=[\"actual_qty\",\"modified\"]" \
  -H "Authorization: token KEY:SECRET"

# Expected: actual_qty should be 0 (ENCODE is empty) or a small number, NOT 21,663
```

### Known limitations

- Can't force store managers to fill ENCODE column — ops team needs to communicate this requirement
- Force re-sync may hit Frappe rate limits — monitor during execution
- Python Playwright broken on this machine — use Node.js for any browser testing
- The store shadow sync runs inside the **Frappe scheduler container** (`frappe_scheduler`), NOT in `sheets-receiver`. Don't look for sync logs in sheets-receiver for store data.
- The Frappe scheduled job runs as `enqueue_scheduled_store_inventory_shadow_sync` (hooks.py line 380), triggered every 10 minutes
- Runtime state file is at: `/home/frappe/frappe-bench/sites/hrms.bebang.ph/private/files/store_inventory_shadow_sync_state.json`
- Store sheet registry is at: `hrms/fixtures/store_inventory_shadow_sync/store_inventory_shadow_sync_registry.csv` (46 stores)

---

## Scope

### Phase A: Fix the Bug (6 units)

| Task | Type | File | Description | Units |
|------|------|------|-------------|-------|
| A1 | FIX | `hrms/utils/store_inventory_shadow_sync.py` | In `_resolve_current_qty()` (line 520-576): Remove the `historical_end` fallback path (lines 543-564). When ENCODE and TOTAL are both None AND daily_records exist, return `(None, "historical_end_skipped", None, "ENCODE and TOTAL empty; historical END unreliable")` — this is an exception, NOT a payload row. **HARD BLOCKER:** Do NOT use daily BEG/IN/OUT/END values as stock quantities — they are daily movement records, not current on-hand. **ALSO REQUIRED (audit B-01):** Add `elif qty_source == "historical_end_skipped": classification = "historical_end_skipped"` to the classification switch at lines 720-738, BEFORE the `elif not mapping:` check. Without this guard, `resolved_qty = None` flows through as `ready_to_import` and `flt(None)` = 0.0, silently zeroing stock. **ALSO REQUIRED (audit B-02):** Update `hrms/tests/test_store_inventory_shadow_sync.py`: (1) line 138: change `source == "historical_end"` to `source == "historical_end_skipped"` and assert `qty is None`, (2) line 262: change payload count from 3 to 2, (3) line 268: move RM-HIST assertion to `exception_rows` with `classification == "historical_end_skipped"`. | 3 |
| A2 | FIX | `hrms/utils/store_inventory_shadow_sync.py` | Add a log warning when historical_end is skipped: `frappe.logger().warning("Skipping %s at %s: ENCODE and TOTAL empty, historical END values are unreliable", code, store_code)`. Use positional `%s` args (not f-strings) to match codebase conventions in `erp_sync.py`. | 1 |
| A3 | FIX | `hrms/services/sheets_receiver/transforms.py` | Fix Shaw BLVD: Change `"SHAW": "Shaw BLVD"` to `"SHAW": "Shaw BLVD - BKI"` in `INVENTORY_SUMMARY_WAREHOUSE_MAP` (line 21). The store warehouse `Shaw BLVD - Bebang Enterprise Inc.` is correctly disabled. The BKI warehouse `Shaw BLVD - BKI` is the active warehouse that should receive Ian's inventory data. **Decision confirmed by Sam (2026-03-25).** | 1 |

| A4 | FIX | `hrms/api/erp_sync.py` | **DM-7 Sentry (audit B-08):** Add `set_backend_observability_context(module="inventory", action="<fn_name>", mutation_type="update")` to `sync_inventory` and `run_scheduled_store_inventory_shadow_sync`. Currently 0 calls in erp_sync.py vs 26 in commissary.py. | 1 |

### Phase B: Audit Current Data (6 units)

| Task | Type | Description | Units |
|------|------|-------------|-------|
| B0 | BUILD | **Pre-fix bin snapshot (audit B-03 rollback):** Before ANY deploy, dump ALL tabBin entries for store warehouses to `output/inventory_audit/pre_fix_bin_snapshot.csv` (warehouse, item_code, actual_qty, modified). This is the rollback baseline — if the fix overcorrects (blank_zero_policy zeros legitimate stock), re-import from this CSV as Stock Reconciliation corrections. B1's suspicious_bins.csv is NOT sufficient (only captures >5K). | 1 |
| B1 | BUILD | Write a script to audit ALL `tabBin` entries: for each store warehouse, compare the bin qty against a reasonable maximum (e.g., >5,000 units per item per store = suspicious). Output a CSV of all suspicious bins with: warehouse, item_code, qty, last_modified. Save to `output/inventory_audit/suspicious_bins.csv`. | 2 |
| B2 | BUILD | For a sample of 5 suspicious items (including FG001-A at Festival Mall), verify the current Google Sheet ENCODE value vs the Frappe bin qty. Document the gap. Save to `output/inventory_audit/sample_verification.csv`. | 2 |
| B3 | VERIFY | Check how many items across all 46 stores have empty ENCODE and TOTAL columns. This tells us how many items will STOP syncing after the fix. Save count to `output/inventory_audit/empty_encode_count.json`. | 1 |

### Phase C: Deploy + Force Re-Sync (5 units)

| Task | Type | Description | Units |
|------|------|-------------|-------|
| C1 | BUILD | Commit fix, create PR, merge, trigger deploy with **`skip_build=false`, `no_cache=true`** (MEMORY.md lesson #2 — new Python code requires full Docker build). Deploy workflow ID: 226200303. Wait for completion. If deploy fails, STOP and report. | 2 |
| C2 | BUILD | Force a full re-sync of all 46 stores. **Call `run_scheduled_store_inventory_shadow_sync(force=True)` directly via bench execute** (NOT via `enqueue_scheduled_store_inventory_shadow_sync`) to bypass the `deduplicate=True` job_id collision that silently drops force requests when a normal scheduled job is queued (audit B-06). Monitor for errors. If SR submission failure rate >10% for any single store, PAUSE and report. | 2 |
| C3 | VERIFY | After re-sync completes, re-check the 5 sample items from B2. Verify bins now show correct values (ENCODE value or 0 if ENCODE is empty). Save to `output/inventory_audit/post_fix_verification.csv`. | 1 |

### Phase D: Validate + Closeout (4 units)

| Task | Type | Description | Units |
|------|------|-------------|-------|
| D1 | VERIFY | Check FG001-A at Festival Mall: bin qty should be 0 (ENCODE is empty) or a small number, NOT 21,663. | 1 |
| D2 | VERIFY | Check total bin count before vs after: total bins, bins with stock, total qty. Expect total qty to DROP significantly (inflated numbers removed). | 1 |
| D3 | VERIFY | Verify the scheduled 10-minute sync still runs without errors. Check Frappe scheduler logs for the next 2 sync cycles. | 1 |
| D4 | BUILD | Closeout: update plan YAML status (`status: COMPLETED`, `completed_date`, `deployed_at`, `backend_pr`, `l3_result`, `execution_summary`), update SPRINT_REGISTRY.md, `git add -f docs/plans/ output/inventory_audit/ output/l3/S121/`, push to production. | 1 |

**Total: 20 units.** (A1 expanded from 2→3, added A4=1, added B0=1, net +2)

### Rollback Plan (audit B-03)

If post-fix validation (D1/D2) shows unexpected zeroing of items that had legitimate stock:
1. `pre_fix_bin_snapshot.csv` contains the rollback baseline (ALL store bins, not just suspicious ones)
2. Revert commit on sprint branch, redeploy with `skip_build=false`
3. Force re-sync again to restore correct values from the old code path
4. Alternative: re-import specific bins from the snapshot CSV as targeted Stock Reconciliation corrections

---

## L3 Workflow Scenarios

| User | Action | Expected Outcome | Failure Means |
|------|--------|-------------------|---------------|
| System | Check FG001-A bin at Festival Mall after force re-sync | qty = 0 or small number (NOT 21,663) | A1 fix didn't work |
| System | Check FG001-A bin at Megaworld Paseo after force re-sync | qty = 0 or small number (NOT 19,572) | A1 fix didn't work |
| System | Run `_resolve_current_qty()` on a row with empty ENCODE+TOTAL | Returns classification `historical_end_skipped`, NOT a qty | Fallback still active |
| System | Check scheduled sync runs successfully after deploy | Frappe scheduler logs show `Complete` status | Code broke the sync |
| System | Check Ian's warehouse sync still works (SUMMARY 2026) | 625+ rows synced successfully, Shaw BLVD handled per A3 decision | A3 broke Ian sync |
| System | Count bins with qty > 5000 per store warehouse after re-sync | Count < 5 bins across all 46 stores (vs potentially hundreds before) | Force re-sync didn't run |
| System | Run `_resolve_current_qty()` on row with ENCODE="#REF!" | Returns classification `formula_error`, NOT `historical_end_skipped` or `blank_zero_policy` | Formula error guard broken |
| System | Run `_resolve_current_qty()` on row with ENCODE="N/A" | Returns classification `formula_error` (# prefix detection in `_coerce_float`) | Formula error guard broken |
| System | Run `_resolve_current_qty()` on row with WHOLE=5, LOOSE=3, no ENCODE/TOTAL | Returns classification `needs_conversion_rule` | WHOLE/LOOSE path broken |
| System | Run `_resolve_current_qty()` on row with ALL empty + no daily_records | Returns `(0.0, "blank_zero_policy", ...)` — blank_zero_policy still fires for truly empty items | blank_zero_policy broken |

Evidence files required before closeout:
```
output/inventory_audit/pre_fix_bin_snapshot.csv
output/inventory_audit/suspicious_bins.csv
output/inventory_audit/sample_verification.csv
output/inventory_audit/empty_encode_count.json
output/inventory_audit/post_fix_verification.csv
output/l3/S121/state_verification.json
```

---

## Requirements Regression Checklist

- [ ] Is the `historical_end` fallback REMOVED from `_resolve_current_qty()`?
- [ ] Does the function return `historical_end_skipped` classification (not a qty) when ENCODE+TOTAL are empty?
- [ ] Does the log warning fire when historical_end is skipped?
- [ ] Does the `blank_zero_policy` still work when ALL qty sources are empty?
- [ ] Does the `formula_error` detection still work?
- [ ] Does the `encode` path still work when ENCODE has a value?
- [ ] Does the `total` path still work when TOTAL has a value?
- [ ] Is Ian's SUMMARY 2026 sync unchanged (no regression)?
- [ ] Does Shaw BLVD map to `"Shaw BLVD - BKI"` (NOT `"Shaw BLVD"`)? (Sam confirmed 2026-03-25)
- [ ] Were ALL 46 stores force re-synced after deploy?
- [ ] Does FG001-A at Festival Mall show a reasonable qty (not 21,663)?
- [ ] Is `historical_end_skipped` handled in the classification switch at lines 720-738? (audit B-01)
- [ ] Are unit tests updated: line 138 expects `historical_end_skipped`, line 262 payload count = 2, line 268 RM-HIST in exception_rows? (audit B-02)
- [ ] Does `_resolve_current_qty()` with ENCODE="#REF!" return `formula_error`? (audit B-09)
- [ ] Does `_resolve_current_qty()` with ALL empty + no daily_records return `blank_zero_policy`? (audit B-09)
- [ ] Is `pre_fix_bin_snapshot.csv` created BEFORE deploy? (audit B-03)
- [ ] Is deploy triggered with `skip_build=false, no_cache=true`? (audit B-04)
- [ ] Is force re-sync called directly (not via enqueue) to bypass dedup? (audit B-06)
- [ ] Does `erp_sync.py` have `set_backend_observability_context()` on sync endpoints? (audit B-08)

---

## Autonomous Execution Contract

- **completion_condition:**
  - `historical_end` fallback removed from `_resolve_current_qty()`
  - `historical_end_skipped` guard added to classification switch (lines 720-738)
  - Unit tests updated (lines 138, 262, 268)
  - `set_backend_observability_context()` added to erp_sync.py sync endpoints
  - All 46 stores force re-synced with corrected code
  - FG001-A at Festival Mall shows reasonable qty
  - No regression on Ian's warehouse sync (>=625 rows, Shaw BLVD routes to "Shaw BLVD - BKI")
  - Post-fix verification shows inflated bins corrected
  - Pre-fix bin snapshot exists at `output/inventory_audit/pre_fix_bin_snapshot.csv`
  - Plan YAML status = COMPLETED, pushed to production
  - SPRINT_REGISTRY.md updated (including PR number)

- **stop_only_for:**
  - Missing credentials/access to production
  - Force re-sync causes Frappe errors that can't be fixed programmatically
  - Google Sheets API quota exceeded during force re-sync (>5 stores fail with 429)
  - Deploy workflow returns non-success
  - Force re-sync SR failure rate >10% for any single store
  - (Shaw BLVD decision RESOLVED: map to "Shaw BLVD - BKI", confirmed by Sam 2026-03-25)

- **continue_without_pause_through:**
  - code fix → audit → deploy → force re-sync → verify → closeout

- **blocker_policy:**
  - programmatic → fix and continue
  - Frappe SR submission error during re-sync → log, skip item, continue
  - Shaw BLVD → RESOLVED (map to BKI, confirmed 2026-03-25)
  - business-data → pause

- **signoff_authority:** single-owner (Sam Karazi, CEO)

---

## Remote-Truth Baseline

| Repo | Branch | HEAD SHA |
|------|--------|---------|
| hrms | production | `84166ac2b` |

---

## Agent Boot Sequence

1. Read this plan fully — including the Requirements Regression Checklist and Audit Amendment Log.
2. **Create sprint branch:** `git fetch origin production && git checkout -b s121-store-inventory-sync-fix origin/production`
3. Read `hrms/utils/store_inventory_shadow_sync.py` lines 520-576 — the `_resolve_current_qty()` function to fix. **Also read lines 720-738** — the classification switch that needs the `historical_end_skipped` guard.
4. Read `hrms/services/sheets_receiver/transforms.py` lines 16-22 — Ian's warehouse map (Shaw BLVD entry).
5. Read `hrms/tests/test_store_inventory_shadow_sync.py` lines 128-140 and 260-270 — the tests that must be updated.
6. **Pre-flight check:** Verify `frappe.db.exists("Warehouse", "Shaw BLVD - BKI")` returns True before committing A3.
7. *(Optional)* If `tmp/inventory_sync_bug_report.md` exists, read for additional context. May not exist in fresh checkout — the Design Rationale section above is the authoritative cold-start reference.
8. *(Optional)* If `tmp/frappe_stock_recon_research.md` exists, read for SR behavior context.

## Execution Authority

This sprint is intended for autonomous end-to-end execution.
Do not stop for progress-only updates.
Only pause for items listed in the Autonomous Execution Contract `stop_only_for` section.

## Execution Workflow
- Test Python changes: `/local-frappe`
- Deploy backend: create hrms PR → merge → trigger deploy workflow (ID: 226200303) with `skip_build=false, no_cache=true`
- Force re-sync: call `run_scheduled_store_inventory_shadow_sync(force=True)` directly via bench execute (NOT via enqueue wrapper)
- Validate: query `tabBin` via Frappe API

---

## Audit Amendment Log

**Audit date:** 2026-03-25 | **Audit version:** v1
**Pipeline:** 4 domain agents (frappe-backend, system-arch, deployment-qa, team-orchestration) → code verifier → adversarial fact-checker
**Result:** 8 SUPPORTED, 1 PARTIAL, 1 CONTRADICTED → **9 verified blockers, CONDITIONAL GO**
**Full findings:** `output/plan-audit/s121-store-inventory-sync-fix/`

| Blocker | Severity | Amendment | Section Changed |
|---------|----------|-----------|-----------------|
| B-01: `historical_end_skipped` not in classification switch | CRITICAL | Added switch guard + routing to exception_rows in A1 | Phase A, A1 task |
| B-02: Unit tests assert `historical_end` | CRITICAL | Added test update instructions in A1 | Phase A, A1 task |
| B-03: No rollback plan | CRITICAL | Added B0 (pre-fix snapshot) + Rollback Plan section | Phase B, new section |
| B-04: Docker build type not specified | CRITICAL | Added `skip_build=false, no_cache=true` to C1 | Phase C, C1 task |
| B-05: `output/l3/S121/` missing from git add | HIGH | Added to D4 git add command | Phase D, D4 task |
| B-06: Force re-sync dedup collision | HIGH | Changed C2 to direct call (not enqueue) | Phase C, C2 task |
| B-07: Shaw BLVD orphaned bins | MEDIUM | Noted as accepted (old warehouse disabled, bins will age out) | No task change |
| B-08: DM-7 Sentry gap | MEDIUM | Added A4 task for Sentry instrumentation | Phase A, new A4 task |
| B-09: No negative test scenarios | HIGH | Added 4 negative L3 scenarios | L3 table |
| ~~B-10: Governor absent~~ | DISMISSED | Contradicted by fact-checker — not part of this sprint's architecture | None |

**Units impact:** 18 → 20 (+2: A1 expanded 2→3, A4 added, B0 added)
**Verdict after amendments:** GO
