# Worker ALERTING Report — Sprint 03 (GAP-046)

## Mission Outcome

All requested GAP-046 items were implemented in this branch:

1. Actionable Google Chat failure alerting with traceable context was added to G-046 async invoice creation failures.
2. Forced-failure stage hook is now explicit/testable and drives deterministic payload output.
3. Unit tests + verification script were added for payload structure and alert emission behavior.
4. Relevant tests were executed (exact commands and outputs below).
5. `docs/plans/sprint-03-integration-backbone.md` Execution Evidence Ledger row for GAP-046 was updated in this worktree.

## Code Changes

- `hrms/api/commissary.py`
  - Added GAP-046 alert emission wrapper `_emit_g046_failure_alert`.
  - `_create_intercompany_invoices_async` now:
    - resolves optional forced-failure stage (`get_force_failure_stage(store_info)`),
    - supports deterministic forced failure by stage (`maybe_raise_forced_failure`),
    - captures stage-aware failure context,
    - builds deterministic payload (`build_failure_alert_payload`),
    - emits Google Chat + log payload via `_emit_g046_failure_alert`.
  - Success logs changed to `frappe.logger("commissary").info(...)` instead of `frappe.log_error(...)`.
  - `_get_store_type_and_customer` now uses lazy import for `_get_store_customer`.

- `hrms/api/g046_alerting.py` (new)
  - Added deterministic payload schema helpers:
    - `build_failure_alert_payload`
    - `serialize_alert_payload`
    - `build_failure_alert_message`
    - `emit_failure_alert` (injected side effects for easy testing)
    - `get_force_failure_stage`
    - `maybe_raise_forced_failure`

- `tests/unit/test_gap046_alerting.py` (new)
  - Added 5 unit tests:
    - deterministic payload key structure
    - deterministic serialization
    - forced-failure stage extraction
    - stage-sensitive forced failure raising
    - alert emission side-effects (log + chat payload text)

- `scripts/testing/verify_gap046_alerting.py` (new)
  - Added standalone verification script that:
    - validates deterministic serialization,
    - validates forced failure raising,
    - validates emitted alert behavior,
    - validates commissary wiring for force-failure + payload + emission calls.

- `docs/plans/sprint-03-integration-backbone.md` (updated/created in worktree)
  - Added Execution Evidence Ledger row for GAP-046 with command evidence and status.

## Deterministic Alert Payload (Implemented)

Payload fields are fixed and deterministic in structure:

- `schema_version`
- `event`
- `gap_id`
- `flow_id`
- `severity`
- `trace_id`
- `stock_entry_name`
- `stage`
- `forced_failure`
- `forced_failure_stage`
- `documents`
- `store`
- `companies`
- `error`
- `actions`

## Exact Verification Commands and Results

1. Command:

```bash
python -m pytest tests/unit/test_gap046_alerting.py -q
```

Result:

```text
.....                                                                    [100%]
5 passed in 0.03s
```

2. Command:

```bash
python scripts/testing/verify_gap046_alerting.py
```

Result:

```text
GAP-046 alerting verification passed
{"actions":["Validate BKI/BEI internal customer-supplier mapping.","Retry _create_intercompany_invoices_async for this Stock Entry.","Verify both Sales Invoice and Purchase Invoice are submitted."],"companies":{"source_company":"Bebang Kitchen Inc.","target_company":"Bebang Enterprise Inc."},"documents":{"purchase_invoice":"","sales_invoice":"ACC-SINV-VERIFY-0001"},"error":{"message":"forced test error","type":"RuntimeError"},"event":"intercompany_invoice_failure","flow_id":"G-046","forced_failure":true,"forced_failure_stage":"purchase_invoice_create","gap_id":"GAP-046","schema_version":"1.0","severity":"high","stage":"purchase_invoice_create","stock_entry_name":"STE-VERIFY-0001","store":{"customer":"CUST-VERIFY","department":"Store Ops","store_type":"Managed Franchise","warehouse_name":"TEST-STORE - BEI"},"trace_id":"G046::STE-VERIFY-0001"}
```

## Notes

- `docs/` is ignored by repo `.gitignore`, so `docs/plans/sprint-03-integration-backbone.md` is updated in working tree but appears as ignored (`!!`) in `git status --ignored`.
