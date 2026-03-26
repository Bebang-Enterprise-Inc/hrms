# S126 Defects

## DEFECT: All 22 production suggestions lack active BOMs
- **Severity:** MAJOR
- **Type:** COLLATERAL (discovered during S126, not in S126 scope)
- **Scenario:** S126-08 (Bulk Work Order creation)
- **Error:** All 22 production suggestions return `has_bom=None` — no items have active default BOMs
- **Impact:** "Create All Suggested" button correctly hidden, but the commissary supervisor cannot create ANY work orders
- **Root Cause:** BOM records not created/activated for commissary FG items in Frappe
- **Suggested Fix:** Create and activate default BOMs for all 20 FG items (FG001-FG020)
- **First Seen:** 2026-03-26 14:45 PHT
- **Blocks:** Work order creation workflow entirely

## DEFECT: log_wastage() rejects expired batches as invalid
- **Severity:** CRITICAL
- **Type:** IN-SCOPE (S126 bulk write-off depends on this)
- **Scenario:** S126-09R (Bulk Expiry Write-Off)
- **Error:** `log_wastage(item_code="FG006", qty=1, reason_code="expired", batch_no="BATCH-FG006-2026-02-04")` returns `{"success": false, "error": "Select a valid batch for FG006."}`
- **Impact:** Bulk expiry write-off UI works perfectly (checkboxes, confirm dialog, button) but backend rejects the batches. No expired batches can be written off.
- **Root Cause:** `log_wastage()` batch validation in `commissary_quality.py` doesn't accept expired batches — it likely checks for batches with positive SLE qty, but expired batches may have been moved or the validation uses FEFO logic that skips expired entries
- **Suggested Fix:** Allow `log_wastage()` to accept expired batches when `reason_code="expired"` — the whole point of wastage is to write off these items
- **First Seen:** 2026-03-26 15:20 PHT
- **Blocks:** All expiry write-off workflows (single and bulk)
- **API Proof:** `curl -X POST "https://hq.bebang.ph/api/method/hrms.api.commissary.log_wastage" -d '{"item_code":"FG006","qty":1,"reason_code":"expired","batch_no":"BATCH-FG006-2026-02-04"}' → {"success": false, "error": "Select a valid batch for FG006."}`

## DEFECT: Single production submit may miss shift tag under fast submission
- **Severity:** MINOR
- **Type:** IN-SCOPE (S126 shift auto-tag)
- **Scenario:** S126-05R (Single production with shift)
- **Error:** SE MAT-STE-2026-00317 remarks = "Production output | Batch: No batch" — missing SHIFT: tag
- **Impact:** If user opens dialog and submits before `useCurrentShift()` hook resolves (~1-2s after page load), shift is undefined and not appended to remarks
- **Root Cause:** Race condition — `shift?.shift_code` is undefined while SWR hook is still fetching
- **Suggested Fix:** Disable submit button until `useCurrentShift()` has loaded, or pass shift as a fallback based on client time
- **First Seen:** 2026-03-26 15:10 PHT
- **Blocks:** Nothing — cosmetic; shift tagging works for bulk (00318, 00319 confirmed with SHIFT: AM)

## DEFECT: TOP REASON shows "Unknown" instead of reason name
- **Severity:** MINOR
- **Type:** IN-SCOPE (S126 fix — A3 fallback working correctly)
- **Scenario:** S126-03 (Wastage TOP REASON)
- **Error:** "Unknown" displayed — reason_label and reason_code are both missing from some wastage entries
- **Impact:** Cosmetic only
- **Root Cause:** Some wastage entries created with reason codes that don't have display labels
- **Suggested Fix:** Ensure all reason codes have display labels in `get_wastage_reasons()`
- **First Seen:** 2026-03-26 14:45 PHT
- **Blocks:** Nothing
