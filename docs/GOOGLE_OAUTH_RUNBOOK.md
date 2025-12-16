# Google OAuth Runbook (Tasks ↔ Frappe HR)

## Summary

This document captures the production incident where **Google Chat + Google Drive would not “connect”** for users (e.g. `sam@bebang.ph`), even after approving permissions, and the exact fix to prevent recurrence.

## Symptoms

- Tasks UI shows **“Google Chat not connected”** / **“Connect Google Drive”** repeatedly.
- Frappe endpoints return `needs_auth: true` with message:
  - **“Your Google authorization has expired or been revoked. Please sign in with Google again.”**
- Frappe Error Logs show repeated token refresh failures:
  - `method = "Google Token Refresh Failed"`
  - `error = "... error=invalid_grant ..."`

## Root Cause (Confirmed)

Frappe stores OAuth tokens in a **Password field** in `User OAuth Token`.

In Frappe, reading a Password field via normal attribute access (e.g. `doc.refresh_token`) returns a **masked value**, not the real secret.  
We were sending this masked value to Google’s token endpoint (`grant_type=refresh_token`), resulting in:

- `error = "invalid_grant"`

## Fix (Implemented)

In `hrms/utils/google_oauth.py`:

- **Store tokens using `doc.set_password(fieldname, value)`**
  - `access_token`
  - `refresh_token`
- **Read tokens using `doc.get_password(fieldname)`**
  - Use this when refreshing access tokens and when returning tokens for downstream API calls.

This ensures the refresh flow uses the real refresh token, not the masked placeholder.

## Guardrails / How We Prevent This Forever

### 1) Coding rules (mandatory)

- **Never** read Password fields directly:
  - ❌ `doc.refresh_token`
  - ❌ `doc.access_token`
- Always:
  - ✅ `doc.get_password("refresh_token")`
  - ✅ `doc.get_password("access_token")`
- Always store secrets with:
  - ✅ `doc.set_password("refresh_token", token)`
  - ✅ `doc.set_password("access_token", token)`

### 2) Operational runbook checks

When “Connect” loops:

1. Check `Error Log` entries (most recent):
   - filter `method="Google Token Refresh Failed"`
2. If `error=invalid_grant`:
   - This usually means:
     - refresh token truly revoked, OR
     - token retrieval/storage bug (masked token), OR
     - OAuth client mismatch.
3. Force a clean reconnect:
   - Call `hrms.api.oauth_tokens.disconnect_google` (revoke + delete doc)
   - Start OAuth again with `prompt=consent select_account`

### 3) Observability (recommended)

Keep “Google Token Refresh Failed” logging in place with:
- status
- `error`
- `error_description`
- short response body snippet (no secrets)

## Related Endpoints / Files

- **Frappe**
  - `hrms/utils/google_oauth.py` (token storage + refresh)
  - `hrms/api/google_chat.py` / `hrms/api/google_drive.py`
  - `hrms/api/oauth_tokens.py` (`disconnect_google`)
  - `User OAuth Token` DocType

- **Tasks**
  - `/api/auth/google/start` supports `force=1` to disconnect first (best-effort)
  - Hooks call Chat/Drive via `/api/frappe/...` proxy


