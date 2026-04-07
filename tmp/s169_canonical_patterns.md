# S169 T0.7 — Canonical Pattern Verification

**Date:** 2026-04-07
**Purpose:** Confirm reference patterns referenced by the S169 plan still
exist at the expected line numbers. Plan claimed:
- `_get_supabase_service_key` / `_supabase_headers` in `hrms/api/sales_dashboard.py:168-199`
- `frappe.request.get_data(as_text=True)` in `hrms/api/esignature.py:55-60`

## Sales dashboard Supabase helper

**File:** `F:\Dropbox\Projects\BEI-ERP\hrms\api\sales_dashboard.py`

| Symbol | Line | Plan claim | Match? |
|---|---|---|---|
| `_get_supabase_service_key()` def | 176 | "168-199" | YES (within range) |
| `_supabase_headers()` def | 185 | "168-199" | YES (within range) |
| `_supabase_get()` def starts | 196 | "168-199" | YES (within range) |
| `_get_supabase_url()` def | (above 170, ends ~173) | implicit | YES |

Verbatim shape (lines 176-193):

```python
def _get_supabase_service_key() -> str:
    return (
        os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
        or _conf_get("supabase_service_role_key")
        or _conf_get("SUPABASE_SERVICE_ROLE_KEY")
        or ""
    )


def _supabase_headers() -> dict[str, str]:
    key = _get_supabase_service_key()
    if not key:
        raise RuntimeError("SUPABASE_SERVICE_ROLE_KEY is not configured")
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }
```

**Reference shape for `hrms/utils/supabase.py` (Phase 1):** copy this 3-tier
fallback (env -> site_config snake -> site_config UPPER) and the exact
header dict. Do NOT introduce a new lookup pattern.

## Webhook JSON parse pattern

**File:** `F:\Dropbox\Projects\BEI-ERP\hrms\api\esignature.py`

| Symbol | Line | Plan claim | Match? |
|---|---|---|---|
| `frappe.request.get_data(as_text=True)` | 56 | "55-60" | YES (within range) |
| `json.loads(raw_body)` | 58 | "55-60" | YES |
| `frappe.throw(_("Invalid JSON payload"))` | 60 | "55-60" | YES |

Verbatim shape (lines 55-60):

```python
# --- Parse payload ---
raw_body = frappe.request.get_data(as_text=True)
try:
    payload = json.loads(raw_body)
except json.JSONDecodeError:
    frappe.throw(_("Invalid JSON payload"))
```

**Reference shape for `hrms/api/mosaic_webhook.py` (Phase 3):** copy this exact
parse-and-throw pattern verbatim. Plan compliance — no deviation.

Bonus context (lines 50-53 of esignature.py — HMAC-style secret check, useful
ONLY if T0.5 webhook signing probe later flips to Path A):

```python
if not hmac.compare_digest(received_secret, webhook_secret):
    frappe.throw(_("Invalid webhook secret"), frappe.AuthenticationError)
elif webhook_secret and not received_secret:
    frappe.throw(_("Missing X-Documenso-Secret header"), frappe.AuthenticationError)
```

## T0.7 result

**PASS.** Both reference files match the plan's claims (the line numbers
shifted by ~8 lines but both symbols are still well within the cited windows).
No refactor has occurred since the plan was written. Phase 1 / Phase 3 may
proceed against these canonical shapes.
