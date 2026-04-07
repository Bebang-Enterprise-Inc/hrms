# S163 — Scenario 7 Retest (after PR #467 hotfix)

**Date:** 2026-04-07
**Hotfix:** PR #467 — `resolve_group_order_item` now passes `action=` positional to `check_scm_permission` (was `operation=` kwarg).
**Result: PASS**

## Test execution

- **Auth:** sam@bebang.ph session via `POST /api/method/login` (200).
- **Order used:** `BEI-ORD-2026-00240` (pre-existing from prior L3 run; state: GRP-FROZEN-MANGO seq=1, status=Auto).
- **Pre-state modified:** `2026-04-06 23:38:13.717973`.

### API call

`POST https://hq.bebang.ph/api/method/hrms.api.store.resolve_group_order_item`

```json
{
  "order_name": "BEI-ORD-2026-00240",
  "group_order_seq": 1,
  "resolution": [
    {"member_item": "RM010-A", "source_warehouse": "3MD Logistics - Camangyanan - BKI", "qty": 3},
    {"member_item": "RM030",   "source_warehouse": "3MD Logistics - Camangyanan - BKI", "qty": 2}
  ],
  "expected_modified": "2026-04-06 23:38:13.717973"
}
```

### Response — HTTP 200

```json
{"message":{"success":true,"order_name":"BEI-ORD-2026-00240","group_order_seq":1,"modified":"2026-04-07 08:35:05.609728","sibling_count":2}}
```

No 500. No `check_scm_permission() got an unexpected keyword argument 'operation'`. Hotfix confirmed live.

## Post-state verification

`GET /api/resource/BEI Store Order/BEI-ORD-2026-00240` items child table:

| item_code | group_order_seq | group_resolution_status | qty_requested |
|-----------|-----------------|--------------------------|---------------|
| RM010-A   | 1 | Manual | 3.0 |
| RM030     | 1 | Manual | 2.0 |

- 2 rows under seq=1 (sibling_count=2 confirmed) ✓
- Both `Manual` ✓
- Old `GRP-FROZEN-MANGO` Auto row gone — multi-row swap worked ✓
- Member items match request ✓

## Scenario 8 (MR creation) — NOT ATTEMPTED

Skipped to keep this run focused on the S7 hotfix verification per task scope. The order is now in a Manual-resolved state and ready for downstream approval/MR testing in a subsequent run. No additional approvals were issued; workflow_state of `BEI-ORD-2026-00240` remains as it was (no advancement triggered).

## UI verification — NOT ATTEMPTED

API-level retest was sufficient to confirm the kwarg fix (the bug was in the Python endpoint, not the React UI). UI was already validated in the prior L3 run up to the point of the API failure. No new frontend code was deployed in PR #467.

## Orders touched

- `BEI-ORD-2026-00240` — modified (Auto→Manual, RM010-A 3 + RM030 2). **Cleanup needed.**

## NEW ORDERS CREATED

None. Used existing test order from prior L3 run.

## New bugs found

None. Hotfix is clean.

## Evidence files

- `F:\Dropbox\Projects\BEI-ERP\output\l3\s163\state_verification.json` (S7_RETEST entry appended)
- `F:\Dropbox\Projects\BEI-ERP\output\l3\s163\api_mutations.json` (resolve call appended)
- `F:\Dropbox\Projects\BEI-ERP\output\l3\s163\s7_retest_report.md` (this file)
