# S126 Defects

## DEFECT: Wastage for expired batches fails with "Serial and Batch Bundle already created"
- **Severity:** CRITICAL
- **Type:** IN-SCOPE (S126 bulk write-off depends on this)
- **Scenario:** S126-09 (Bulk Expiry Write-Off)
- **Error:** `log_wastage()` batch validation fix works (batch accepted), but SE submission fails: "Serial and Batch Bundle cae59ad8b12fadf616cd has already created. Please remove the values from the serial no or batch no fields."
- **Impact:** No expired batches can be written off — both single and bulk write-off are blocked
- **Root Cause:** Frappe v15 Serial and Batch Bundle system creates one-to-one bundle records. If a batch was previously involved in a transaction, the bundle already exists and a new Material Issue SE for the same batch fails because Frappe tries to create a duplicate bundle.
- **Suggested Fix:** Before creating the Material Issue SE, check for existing Batch Bundle and reuse it, OR use `frappe.flags.ignore_serial_batch_bundle_validation = True` during wastage write-off
- **First Seen:** 2026-03-26 15:45 PHT
- **Blocks:** All wastage write-off for batch-tracked items
- **API Proof:** `curl -X POST .../log_wastage -d '{"item_code":"FG006","qty":1,"reason_code":"expired","batch_no":"BATCH-FG006-2026-02-04"}' -> CharacterLengthExceededError wrapping "Serial and Batch Bundle already created"`

## DEFECT: All 22 production suggestions lack active BOMs
- **Severity:** MAJOR
- **Type:** COLLATERAL (not in S126 scope)
- **Scenario:** S126-08 (Bulk Work Order creation)
- **Error:** All 22 production suggestions return `has_bom=None`
- **Impact:** "Create All Suggested" button correctly hidden, but WO creation blocked for all items
- **Root Cause:** BOM records not configured in Frappe for commissary FG items
- **Suggested Fix:** Create and activate BOMs for FG001-FG020
- **First Seen:** 2026-03-26 14:45 PHT
- **Blocks:** Work order creation

## DEFECT: TOP REASON shows "Unknown" instead of reason name
- **Severity:** MINOR
- **Type:** IN-SCOPE
- **Scenario:** S126-03 (Wastage TOP REASON)
- **Error:** Reason labels not populated for some entries
- **Impact:** Cosmetic only — "Unknown" displayed instead of reason name
- **First Seen:** 2026-03-26 14:45 PHT
