# Plan: Frontend, Backend & Schema Audit Improvements
**Date:** 2026-02-18
**Author:** Gemini Code
**Audit & Fixes:** Claude Code (2026-02-18)

## Audit Summary

| # | Finding | Confirmed? | Priority | Status |
|---|---------|-----------|----------|--------|
| 1.1/1.3 | `anon` grants on financial views | YES | Medium | FIXED |
| 1.2 | Hardcoded credential path | YES | Low | FIXED |
| 2.1 | Hardcoded company name + space IDs | YES | Medium | FIXED |
| 2.2 | POS parser fixed column indices | YES | Medium | FIXED |
| 2.3 | `_parse_date` returns raw string | YES | **High** | FIXED |
| 2.4 | No unit tests for PCF/POS | YES | Low | Deferred |
| 3.1 | Static OrderForm categories | YES | Low | FIXED |
| 3.2 | Geolocation missing options | YES | Medium | FIXED |
| ~~4.1~~ | ~~Date spine UNIONs~~ | **NO** | N/A | Removed — pattern doesn't exist in codebase |
| ~~4.2~~ | ~~Manual matview refresh~~ | **NO** | N/A | Removed — already handled by `pg_cron` |

---

## 1. Security Hardening (Highest Priority)

### 🚨 1.1 Supabase RLS Lockdown — FIXED
*   **Findings:** Financial views granted to `anon` and `authenticated` roles without RLS on base tables.
*   **Fix applied:**
    *   Removed `anon` from all `GRANT SELECT` statements in 3 existing migration files.
    *   Created `supabase/migrations/20260218_revoke_anon_financial_views.sql` to explicitly revoke `anon` and ensure `authenticated`-only access on: `store_daily_closing`, `v_system_daily_totals`, `v_all_channel_daily`, `v_ops_weekly`, `foodpanda_store_mapping`.
*   **Audit note:** Low practical risk since anon key is not exposed in any public frontend, but fixed as defense-in-depth.

### 🔐 1.2 Credential Management — FIXED
*   **Findings:** Hardcoded service account path in multiple API files.
*   **Fix applied:**
    *   Created `hrms/utils/bei_config.py` with `get_service_account_path()` that checks `GOOGLE_SERVICE_ACCOUNT_FILE` env var first.
    *   Updated `hrms/api/google_chat.py`, `hrms/api/procurement.py`, `hrms/utils/biometric_alerts.py` to use the centralized function.

---

## 2. Backend & Architectural Improvements

### 🛠️ 2.1 Decouple Hardcoded Constants — FIXED
*   **Findings:** "Bebang Enterprise Inc." in 40+ production files. Google Chat Space IDs hardcoded in 12+ locations across 5 different spaces.
*   **Fix applied:**
    *   Created `hrms/utils/bei_config.py` with:
        *   `get_company()` — reads from `frappe.defaults.get_global_default("company")` with fallback.
        *   `get_chat_space(default_space)` — checks `BEI Settings` DocType first, falls back to constant.
        *   Space constants: `SPACE_NOTIFICATIONS`, `SPACE_ERP_AUTOMATION`, `SPACE_ACCOUNTING`, `SPACE_ADMIN_IT`, `SPACE_OPS`.
    *   Updated all production files in `hrms/api/` and `hrms/hr/doctype/` to use `get_company()` and `get_chat_space()`.
    *   Eliminated redundant double-fallback patterns (e.g., `frappe.defaults.get_defaults().get("company") or "Bebang Enterprise Inc."`).

### 🔍 2.2 POS Parser Resilience — FIXED
*   **Findings:** `parse_sales_summary` in `hrms/utils/pos_parser.py` used `row.iloc[0]` through `row.iloc[22]` — fixed column index access.
*   **Fix applied:**
    *   Refactored to use `pd.read_excel(header=9)` and access columns by name: `row.get("Gross Sales")`, `row.get("Net Sales")`, etc.
    *   Matches the pattern already used by the other 4 parsers in the same file.
*   **Audit note:** `_extract_metadata()` still uses `iloc` for rows 0-7, but these are key-value metadata pairs (not tabular data), so positional access is appropriate.

### 🟡 2.3 Data Utility Robustness — FIXED
*   **Findings:** `_parse_date` returned raw unparseable string `str(value)` instead of `None`.
*   **Fix applied:** Changed `pos_parser.py:85` from `return str(value) if value else None` to `return None`.
*   **Confirmed:** `_safe_float` already handles accounting formats correctly — no change needed.

### 🧪 2.4 Automated Testing — DEFERRED
*   **Findings:** No unit tests for PCF business logic or POS parsing.
*   **Status:** Deferred — nice-to-have, not blocking any production issue.
*   **Recommended files when prioritized:**
    *   `hrms/tests/test_pcf.py` for Petty Cash Fund logic
    *   `hrms/tests/test_pos_parser.py` using sample MOSAIC Excel exports

---

## 3. Frontend & UX Enhancements

### ⚙️ 3.1 Dynamic Configuration — FIXED
*   **Findings:** Order categories in `OrderForm.vue` were hardcoded: `["All", "Frozen", "Chilled", "Dry", "Packaging"]`.
*   **Fix applied:** Replaced with a `computed` property that derives categories from the fetched items' `item_group` field. New categories appear automatically when items with new groups are added in Frappe.

### 📍 3.2 Geolocation & Reliability — FIXED
*   **Findings:** `CheckInPanel.vue` called `getCurrentPosition` without options.
*   **Fix applied:** Added `{ enableHighAccuracy: true, timeout: 10000, maximumAge: 0 }` options to the geolocation call.

---

## Files Changed

### New files
- `hrms/utils/bei_config.py` — centralized config (spaces, company, credentials)
- `supabase/migrations/20260218_revoke_anon_financial_views.sql` — revoke anon access

### Modified files (security)
- `supabase/migrations/20260214_store_daily_closing.sql`
- `supabase/migrations/20260215_fix_view_aliases_add_foodpanda.sql`
- `supabase/migrations/20260217_fix_views_add_status_filters.sql`

### Modified files (space IDs centralized)
- `hrms/api/google_chat.py`
- `hrms/api/dispatch.py`
- `hrms/api/enrichment.py`
- `hrms/api/expense.py`
- `hrms/api/inventory.py`
- `hrms/api/pcf.py`
- `hrms/api/permits.py`
- `hrms/api/procurement.py`
- `hrms/hr/doctype/bei_pcf_batch/bei_pcf_batch.py`
- `hrms/utils/biometric_alerts.py`
- `hrms/tasks.py`

### Modified files (company name centralized)
- `hrms/api/billing.py`
- `hrms/api/commissary.py`
- `hrms/api/expense.py`
- `hrms/api/inventory.py`
- `hrms/api/pcf.py`
- `hrms/api/picking.py`
- `hrms/api/procurement.py`
- `hrms/api/recruitment.py`
- `hrms/api/store.py`
- `hrms/api/warehouse.py`
- `hrms/hr/doctype/bei_billing_schedule/bei_billing_schedule.py`
- `hrms/hr/doctype/bei_goods_receipt/bei_goods_receipt.py`
- `hrms/hr/doctype/bei_invoice/bei_invoice.py`
- `hrms/hr/doctype/bei_payment_request/bei_payment_request.py`
- `hrms/hr/doctype/bei_pcf_batch/bei_pcf_batch.py`
- `hrms/hr/doctype/bei_purchase_order/bei_purchase_order.py`

### Modified files (parser/frontend)
- `hrms/utils/pos_parser.py` — `_parse_date` fix + header-based column lookup
- `frontend/src/components/CheckInPanel.vue` — geolocation options
- `frontend/src/views/store_ops/OrderForm.vue` — dynamic categories
