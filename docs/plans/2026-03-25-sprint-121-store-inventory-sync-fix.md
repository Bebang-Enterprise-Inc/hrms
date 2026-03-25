---
canonical_sprint_id: S121
display: Sprint 121
status: GO
branch: s121-store-inventory-sync-fix
lane: single
created_date: 2026-03-25
completed_date:
deployed_at:
backend_pr:
frontend_pr:
l3_result:
execution_summary:
depends_on:
---

# S121 — Fix Store Inventory Sync: Wrong Qty from Historical Fallback

**Goal:** Fix the store inventory shadow sync so it mirrors the CURRENT stock on hand from store Google Sheets, not inflated historical daily balances. Then force a full re-sync of all 46 stores and validate that Frappe `tabBin` shows correct numbers.

**Origin:** Investigation on 2026-03-25 found Festival Mall shows 21,663 LECHE FLAN x 12 (FG001-A) in Frappe — actual store sheet says 12 pieces. Root cause traced to `_resolve_current_qty()` in `hrms/utils/store_inventory_shadow_sync.py` falling back to historical daily END values when ENCODE and TOTAL columns are empty.

**Severity:** CRITICAL — all inventory data in Frappe for 46 stores is potentially unreliable.

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

### Known limitations

- Can't force store managers to fill ENCODE column — ops team needs to communicate this requirement
- Force re-sync may hit Frappe rate limits — monitor during execution
- Python Playwright broken on this machine — use Node.js for any browser testing

---

## Scope

### Phase A: Fix the Bug (4 units)

| Task | Type | File | Description | Units |
|------|------|------|-------------|-------|
| A1 | FIX | `hrms/utils/store_inventory_shadow_sync.py` | In `_resolve_current_qty()` (line 520-576): Remove the `historical_end` fallback path (lines 543-564). When ENCODE and TOTAL are both None, skip directly to WHOLE/LOOSE check, then to `blank_zero_policy`. Replace `historical_end` with a new classification `historical_end_skipped` that logs the item as an exception but does NOT return a qty. **HARD BLOCKER:** Do NOT use daily BEG/IN/OUT/END values as stock quantities — they are daily movement records, not current on-hand. | 2 |
| A2 | FIX | `hrms/utils/store_inventory_shadow_sync.py` | Add a log warning when historical_end is skipped: `frappe.logger().warning(f"Skipping {code} at {store_code}: ENCODE and TOTAL empty, historical END values are unreliable")`. This helps identify which items/stores need ENCODE column updates. | 1 |
| A3 | FIX | `hrms/services/sheets_receiver/config.py` | Fix Shaw BLVD: either remove `"SHAW"` from `INVENTORY_SUMMARY_WAREHOUSE_MAP` (if the warehouse is permanently closed) or re-enable the warehouse in Frappe (if still active). **Decision needed from Sam.** | 1 |

### Phase B: Audit Current Data (5 units)

| Task | Type | Description | Units |
|------|------|-------------|-------|
| B1 | BUILD | Write a script to audit ALL `tabBin` entries: for each store warehouse, compare the bin qty against a reasonable maximum (e.g., >5,000 units per item per store = suspicious). Output a CSV of all suspicious bins with: warehouse, item_code, qty, last_modified. Save to `output/inventory_audit/suspicious_bins.csv`. | 2 |
| B2 | BUILD | For a sample of 5 suspicious items (including FG001-A at Festival Mall), verify the current Google Sheet ENCODE value vs the Frappe bin qty. Document the gap. Save to `output/inventory_audit/sample_verification.csv`. | 2 |
| B3 | VERIFY | Check how many items across all 46 stores have empty ENCODE and TOTAL columns. This tells us how many items will STOP syncing after the fix. Save count to `output/inventory_audit/empty_encode_count.json`. | 1 |

### Phase C: Deploy + Force Re-Sync (5 units)

| Task | Type | Description | Units |
|------|------|-------------|-------|
| C1 | BUILD | Commit fix, create PR, merge, trigger deploy. Wait for completion. | 2 |
| C2 | BUILD | Force a full re-sync of all 46 stores with `force=True`. Monitor for errors. This will re-read all store sheets with the corrected `_resolve_current_qty()` and overwrite bad bin values. | 2 |
| C3 | VERIFY | After re-sync completes, re-check the 5 sample items from B2. Verify bins now show correct values (ENCODE value or 0 if ENCODE is empty). Save to `output/inventory_audit/post_fix_verification.csv`. | 1 |

### Phase D: Validate + Closeout (4 units)

| Task | Type | Description | Units |
|------|------|-------------|-------|
| D1 | VERIFY | Check FG001-A at Festival Mall: bin qty should be 0 (ENCODE is empty) or a small number, NOT 21,663. | 1 |
| D2 | VERIFY | Check total bin count before vs after: total bins, bins with stock, total qty. Expect total qty to DROP significantly (inflated numbers removed). | 1 |
| D3 | VERIFY | Verify the scheduled 10-minute sync still runs without errors. Check Frappe scheduler logs for the next 2 sync cycles. | 1 |
| D4 | BUILD | Closeout: update plan YAML status, update SPRINT_REGISTRY.md, `git add -f docs/plans/ output/inventory_audit/`, push to production. | 1 |

**Total: 18 units.**

---

## L3 Workflow Scenarios

| User | Action | Expected Outcome | Failure Means |
|------|--------|-------------------|---------------|
| System | Check FG001-A bin at Festival Mall after force re-sync | qty = 0 or small number (NOT 21,663) | A1 fix didn't work |
| System | Check FG001-A bin at Megaworld Paseo after force re-sync | qty = 0 or small number (NOT 19,572) | A1 fix didn't work |
| System | Run `_resolve_current_qty()` on a row with empty ENCODE+TOTAL | Returns classification `historical_end_skipped`, NOT a qty | Fallback still active |
| System | Check scheduled sync runs successfully after deploy | Frappe scheduler logs show `Complete` status | Code broke the sync |
| System | Check Ian's warehouse sync still works (SUMMARY 2026) | 625+ rows synced successfully, Shaw BLVD handled per A3 decision | A3 broke Ian sync |
| System | Count bins with qty > 5000 per store warehouse after re-sync | Count should be near zero (vs potentially hundreds before) | Force re-sync didn't run |

Evidence files required before closeout:
```
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
- [ ] Does Shaw BLVD handling match Sam's decision (remove vs re-enable)?
- [ ] Were ALL 46 stores force re-synced after deploy?
- [ ] Does FG001-A at Festival Mall show a reasonable qty (not 21,663)?

---

## Autonomous Execution Contract

- **completion_condition:**
  - `historical_end` fallback removed from `_resolve_current_qty()`
  - All 46 stores force re-synced with corrected code
  - FG001-A at Festival Mall shows reasonable qty
  - No regression on Ian's warehouse sync
  - Post-fix verification shows inflated bins corrected
  - Plan YAML status = COMPLETED, pushed to production
  - SPRINT_REGISTRY.md updated

- **stop_only_for:**
  - Missing credentials/access to production
  - Shaw BLVD decision (remove vs re-enable) — needs Sam's input
  - Force re-sync causes Frappe errors that can't be fixed programmatically

- **continue_without_pause_through:**
  - code fix → audit → deploy → force re-sync → verify → closeout

- **blocker_policy:**
  - programmatic → fix and continue
  - Frappe SR submission error during re-sync → log, skip item, continue
  - Shaw BLVD → pause for Sam's decision
  - business-data → pause

- **signoff_authority:** single-owner (Sam Karazi, CEO)

---

## Remote-Truth Baseline

| Repo | Branch | HEAD SHA |
|------|--------|---------|
| hrms | production | `84166ac2b` |

---

## Agent Boot Sequence

1. Read this plan fully — including the Requirements Regression Checklist.
2. **Create sprint branch:** `git fetch origin production && git checkout -b s121-store-inventory-sync-fix origin/production`
3. Read `hrms/utils/store_inventory_shadow_sync.py` lines 520-576 — the `_resolve_current_qty()` function to fix.
4. Read `hrms/services/sheets_receiver/transforms.py` lines 16-22 — Ian's warehouse map (Shaw BLVD entry).
5. Read `tmp/inventory_sync_bug_report.md` — full investigation report.
6. Read `tmp/frappe_stock_recon_research.md` — how Stock Reconciliation works in Frappe.

## Execution Authority

This sprint is intended for autonomous end-to-end execution.
Do not stop for progress-only updates.
Only pause for items listed in the Autonomous Execution Contract `stop_only_for` section.

## Execution Workflow
- Test Python changes: `/local-frappe`
- Deploy backend: create hrms PR → merge → trigger deploy workflow (ID: 226200303)
- Force re-sync: call `run_store_inventory_shadow_sync(force=True)` via Frappe bench execute
- Validate: query `tabBin` via Frappe API
