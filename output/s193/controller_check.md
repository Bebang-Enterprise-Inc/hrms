# S193 Phase 0a — Controller + Frontend Error Surface Check

**Date:** 2026-04-14

## Task 0a.1 — Supplier controller (`hrms/hr/doctype/bei_supplier/bei_supplier.py`)

The `BEISupplier.validate()` method runs three checks:
1. `validate_supplier_code()` — auto-generates if empty, else strip+upper
2. `validate_required_documents()` — **soft warning** (`frappe.msgprint` with `indicator="orange"`) when status is `Active` but BIR/SEC missing. Does NOT block insert/save.
3. `validate_invoice_exception_control()` — gates `missing_supplier_invoice_*` fields only

**Conclusion:** Status field accepts all 4 enum values (`Active`, `Inactive`, `Blacklisted`, `Pending Verification`) on `insert()` and `save()`. No state machine, no approval hook in the controller — the approval workflow is enforced at the API layer via `submit_supplier_edit_for_approval` (procurement.py:570), not in the DocType controller.

**Test fixture implication:** Phase 2 tests can create suppliers directly in any of the 4 statuses using `frappe.get_doc({...}).insert(ignore_permissions=True)`. No bypass needed.

## Task 0a.2 — Frontend error surface (`bei-tasks/lib/frappe-api.ts`)

`parseFrappeError(error)` at line 165 extracts the Frappe error message in this priority:
1. `_server_messages[0].message` (primary path — where `frappe.throw(_("..."))` lands)
2. `_error_message`
3. `exception` (last segment after `:`)
4. `Error.message`

**Conclusion:** When `_assert_supplier_active` fires `frappe.throw(_("Cannot create Purchase Order: Supplier {0} is Blacklisted..."), frappe.ValidationError)`, the response `_server_messages` payload will contain the formatted message, which `parseFrappeError` will return verbatim. Any page using `fetchAPI` → `parseFrappeError` (all procurement pages do) will render the message cleanly.

Spot-check: `bei-tasks/hooks/use-procurement.ts:242` calls `parseFrappeError(error)` in the default `fetchAPI` helper. All PO/Invoice/Payment Request creation flows go through this helper. ✓

**No S194 TODO needed** — existing plumbing handles the new error cleanly.

## Gate: PASS

- [x] Supplier DocType controller permits direct status set for all 4 enum values
- [x] `parseFrappeError` extracts Frappe ValidationError message
- [x] One create-page flow confirmed to surface the extracted message via fetchAPI
