# R1 Leave Ledger Retest — EMP-LEAVE-003

## Scenario

- **Leave Application:** HR-LAP-2026-00118
- **Test run:** 4/7/2026, 9:42:48 PM
- **Prior status:** DEFECT-PASS (ledger was empty post-approval)
- **Fix applied:** S170 Phase 1 — Leave Ledger backfill script

## Verdict: PASS — PASS_POST_FIX

API returned 1 ledger row(s) for HR-LAP-2026-00118. Browser list: 1 rows visible, no_result=true. S170 Phase 1 fix verified working.

---

## Evidence Summary

### Step 1 — Leave Application

| Field | Value |
|-------|-------|
| Status | Approved |
| docstatus | 1 |
| total_leave_days | 1 |
| Employee | TEST-CREW-001 |
| API response code | 200 |

Screenshot: screenshots/EMP-LEAVE-003-retest_desk_leaveapp.png

### Step 2 — Leave Ledger Entry List (Browser)

| Field | Value |
|-------|-------|
| URL | https://hq.bebang.ph/app/leave-ledger-entry?transaction_name=HR-LAP-2026-00118 |
| list_row_count | 1 |
| no_result_visible | true |

Screenshot: screenshots/EMP-LEAVE-003-retest_desk_ledger.png

### Step 3 — API Cross-Check

- **Endpoint:** `/api/resource/Leave Ledger Entry?filters=[["transaction_name","=","HR-LAP-2026-00118"]]`
- **Response rows:** 1

  - ln52p77bho: employee=TEST-CREW-001, leaves=-1, type=Leave Application

### Step 4 — Leave Balance

- **Employee:** TEST-CREW-001
- **Total ledger entries for employee:** 5

---

## Conclusion

S170 Phase 1 backfill fix is **verified working**. The Leave Ledger Entry now exists for HR-LAP-2026-00118 in both browser and API. EMP-LEAVE-003 is re-classified as **PASS_POST_FIX**.
