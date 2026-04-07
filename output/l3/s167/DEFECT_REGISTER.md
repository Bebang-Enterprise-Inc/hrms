
## 0.1_HR
- **time:** 2026-04-07T05:19:56.686Z
- **error:** no matching dept found for /^HR and Admin$|^HR and Admin - BEI$/i
- **hypothesis:** 

## 0.1_SupplyChain
- **time:** 2026-04-07T05:19:57.266Z
- **error:** no matching dept found for /^Supply Chain - BEI$|^Supply Chain$/i
- **hypothesis:** 

## DEFECT-004 — PCF-TEST-STORE-BGC fund references non-existent warehouse

- **Scenario:** Phase 0.2 (staff, supv), Phase 1 entire phase
- **Severity:** MEDIUM — blocks store PCF L3 testing in this sprint
- **Root cause:** Fund `PCF-TEST-STORE-BGC - BEI` has `store = "TEST-STORE-BGC - BEI"` but no `Warehouse` DocType with that name exists. The PCF resolver's `_get_store_for_employee` → `_resolve_store_name` returns None because `frappe.db.exists("Warehouse", ...)` is false for all tried suffixes.
- **Impact:** test.staff and test.supervisor (both on branch=TEST-STORE-BGC) cannot resolve any PCF fund, blocking Phase 1 store expense lifecycle (6 scenarios).
- **Fix:** Create the missing warehouse `TEST-STORE-BGC - BEI` under company `Bebang Enterprise Inc.` (sam currently lacks DocType Warehouse create permission via REST — requires either (a) role permission adjustment, (b) SSM direct insert, or (c) pointing the PCF fund at an existing warehouse).
- **S167 action:** Phase 1 (store lifecycle) marked BLOCKED in L3 report. Phases 2–5 continue with dept accounts.

## DEFECT-005 — update_pcf_settings silently ignores is_enabled

- **Scenario:** Phase 0 post-create fund enablement
- **Severity:** MEDIUM — blocks any programmatic enable/disable via the API
- **Root cause:** `POST /api/pcf {action:"update_pcf_settings", pcf_fund:"PCF-X", is_enabled:1}` returns success but the fund's `is_enabled` stays 0. Either the action handler doesn't map `is_enabled` to the DocType field, or the validated params filter strips it.
- **Impact:** new dept funds created via `create_pcf_fund` start with `is_enabled=0` and there is no UI/API path to enable them short of direct DocType mutation.
- **Workaround used in S167:** `PUT /api/frappe/api/resource/BEI Petty Cash Fund/{name}` with `{is_enabled:1}` — works (admin-only).
- **Fix recommendation:** Audit `update_pcf_settings` handler in `hrms/api/pcf.py` to ensure `is_enabled` is accepted + set on the doc.
