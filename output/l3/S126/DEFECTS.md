# S126 Defects

## DEFECT: All 22 production suggestions lack active BOMs
- **Severity:** MAJOR
- **Type:** COLLATERAL (discovered during S126, not in S126 scope)
- **Scenario:** S126-08 (Bulk Work Order creation)
- **Error:** All 22 production suggestions return `has_bom=None` — no items have active default BOMs configured
- **Impact:** The "Create All Suggested" button is correctly hidden (feature works), but the commissary supervisor cannot create ANY work orders because no items have BOMs
- **Root Cause:** BOM records not created/activated for commissary FG items in Frappe
- **Suggested Fix:** Create and activate default BOMs for all 20 FG items (FG001-FG020) in Frappe
- **First Seen:** 2026-03-26 14:45 PHT
- **Blocks:** Work order creation workflow entirely

## DEFECT: TOP REASON shows "Unknown" instead of actual reason names
- **Severity:** MINOR
- **Type:** IN-SCOPE (S126 fix — A3 fallback working but reason labels not populated)
- **Scenario:** S126-03 (Wastage TOP REASON)
- **Error:** The "Unknown" fallback triggers because `reason_label` and `reason_code` are both missing from some wastage entries
- **Impact:** Cosmetic — shows "Unknown" instead of the actual reason text
- **Root Cause:** Some wastage entries were created with reason codes that don't have display labels configured
- **Suggested Fix:** Ensure all reason codes in `get_wastage_reasons()` have display labels
- **First Seen:** 2026-03-26 14:45 PHT
- **Blocks:** Nothing — cosmetic only
