# S121 Fact-Check Report
## Date: 2026-03-25
## Method: Layer 1 — Programmatic verification against source files + production API
## Verifier: Claude Opus 4.6 (same session, post-execution)

---

### Summary

| Verdict | Count |
|---------|-------|
| SUPPORTED | 10 |
| PARTIAL | 0 |
| NOT_FOUND | 0 |
| CONTRADICTED | 0 |
| **Total** | **10** |

---

### Detailed Results

#### [SUPPORTED] Claim 1: PR #349 merged and deployed
**Evidence:** `gh pr view 349` → `state: MERGED, mergedAt: 2026-03-25T11:43:25Z`
**Deploy:** Workflow `23539261058` completed with `conclusion: success`

#### [SUPPORTED] Claim 2: historical_end fallback removed from _resolve_current_qty()
**Evidence:** `grep -n "historical_end" store_inventory_shadow_sync.py` shows:
- Line 543: Comment "historical_end fallback REMOVED (S121)"
- No `return ... "historical_end"` anywhere in the function
- The old code block (lines 543-564 with `best_daily` loop) is replaced with a skip-and-classify block

#### [SUPPORTED] Claim 3: historical_end_skipped guard added at lines 720-738
**Evidence:** Line 725-726 of `store_inventory_shadow_sync.py`:
```python
elif qty_source == "historical_end_skipped":
    classification = "historical_end_skipped"
```
Located at line 725, within the claimed 720-738 range.

#### [SUPPORTED] Claim 4: Shaw BLVD mapped to "Shaw BLVD - BKI"
**Evidence:** `grep SHAW transforms.py` → Line 21: `"SHAW": "Shaw BLVD - BKI",`

#### [SUPPORTED] Claim 5: Sentry DM-7 added to erp_sync.py
**Evidence:** `grep set_backend_observability_context erp_sync.py` → 3 matches:
- Line 23: import statement
- Line 1397: inside `sync_inventory()`
- Line 2205: inside `run_scheduled_store_inventory_shadow_sync()`

#### [SUPPORTED] Claim 6: 7/7 unit tests passing
**Evidence:** `pytest hrms/tests/test_store_inventory_shadow_sync.py -q` → `7 passed in 0.53s`

#### [SUPPORTED] Claim 7: Force re-sync 46/46 stores, 0 failures
**Evidence:** SSM command `13c579e6-a717-4973-ada3-ae82963e92b3` output:
- `enabled_stores: 46`
- `imported_stores: 46`
- `rows_failed: 0`
- `failed_stores: []`
- `payload_rows: 2740`
- `exception_rows: 2178`

#### [SUPPORTED] Claim 8: FG001-A Megaworld Paseo corrected 19572 -> 1773
**Evidence:** Frappe API query:
- `actual_qty: 1773.0`
- `modified: 2026-03-25 20:02:31` (modified by post-fix sync)
- Confirmed not 19572

#### [SUPPORTED] Claim 9: FG001-A Festival Mall preserved at 21663
**Evidence:** Frappe API query:
- `actual_qty: 21663.0`
- `modified: 2026-03-13 22:08:15` (NOT modified by post-fix sync — correctly skipped)
- "Preserved by design" claim is accurate: ENCODE is empty → historical_end_skipped → item becomes exception_row → old bin value stays
- This is correct Option A behavior per the plan's Design Rationale

#### [SUPPORTED] Claim 10: Evidence files exist at output/l3/S121/
**Evidence:** `ls output/l3/S121/` shows:
- `api_mutations.json` (273 bytes)
- `form_submissions.json` (165 bytes)
- `state_verification.json` (2278 bytes)

---

### Notes

1. **Line numbers shifted:** The original plan cited lines 720-738 for the classification switch. After the code change (removing 22 lines and adding 17), the switch is now at lines 716-740. The guard was added at line 725, which is within both the original and current ranges. No discrepancy.

2. **Claim 9 nuance:** The original plan D1 said "bin qty should be 0 or a small number, NOT 21,663." The actual behavior is that the fix *preserves* the old value (21,663) rather than correcting it, because ENCODE is empty and the fix classifies this as `historical_end_skipped` (skip the item entirely). This is the correct Option A behavior — the plan's D1 expectation was slightly wrong but the implementation matches the stated design rationale ("Skipping means the previous bin value stays").

3. **"46 stores" vs registry count:** The code verifier during the audit noted the registry CSV has 47 lines (including header). The SSM output confirms `enabled_stores: 46`, which means 46 data rows were processed. The claim of "46 stores" is correct.
