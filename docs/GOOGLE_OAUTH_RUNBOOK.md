# Google OAuth Runbook (Tasks ↔ Frappe HR)

## Summary

This document captures the production incident where **Google Chat + Google Drive would not “connect”** for users (e.g. `sam@bebang.ph`), even after approving permissions, and the exact fix to prevent recurrence.

## Incident Timeline (What Broke, Twice)

1) **Refresh flow failed** (`invalid_grant`) because Password fields were being read incorrectly (masked token).

2) **Token storage failed** (`Most probably your password is too long.`) because storing OAuth tokens in Frappe **Password fields** can hit a DB length limit (implementation-dependent via `__Auth.value`).

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

## Fix #1 (Implemented): Masked Password fields → invalid_grant

**Legacy approach:** `doc.get_password()` / `doc.set_password()` (or password helpers) for Password fields.

This fixes masked-token reads, but we later hit a second production issue below.

## Root Cause #2 (Confirmed): “Most probably your password is too long.”

Frappe Error Log showed repeated:

- `Google OAuth Token Storage Error` → `Error: Most probably your password is too long.`
- `Google Chat Token Error` / `Google Drive Token Error` → same message

This happens because Frappe `Password` fields are stored in `__Auth.value` and can hit a length constraint for large OAuth tokens.

## Fix #2 (Implemented): Store tokens in encrypted Long Text fields

We changed `User OAuth Token` to store tokens in **Long Text** fields instead of Password fields:

- `access_token`: `Password` → `Long Text`
- `refresh_token`: `Password` → `Long Text`

And we store values **encrypted** using Frappe’s `encrypt()` / `decrypt()` helpers, so secrets are not stored as plaintext.

Migration behavior:
- If a user already has legacy Password-field tokens, we **migrate on read** (best-effort) into the new encrypted Long Text column.

## Files / Locations (Source of Truth)

- `hrms/utils/google_oauth.py`
  - Token storage (encrypted Long Text) + refresh flow
- `hrms/hr/doctype/user_oauth_token/user_oauth_token.json`
  - Fieldtype changes (`Password` → `Long Text`)
- `hrms/api/oauth_tokens.py`
  - `disconnect_google` (revoke + delete)

## Operational Runbook Checks (Fast Triage)

When “Connect” loops / spaces fail to load:

1) **Check Frappe Error Log first** (this is always the truth).

2) If you see:
   - **`invalid_grant`** → likely revoked token OR masked-token bug OR OAuth client mismatch  
   - **`Most probably your password is too long.`** → token storage is failing (field length), so Chat/Drive will never work

3) Recovery:
   - Use `force=1` reconnect (Tasks → `/api/auth/google/start?...&force=1`) which calls `disconnect_google` best-effort
   - Re-consent with upgraded scopes

## Google Chat: DMs / Private Chats show as IDs (e.g. `AAQA...`)

### Symptom

The Google Chat Space dropdown shows entries like:
- `AAQAMVRXohc`
- `AAQAx13IzBc`

instead of human-friendly participant names.

### Root Cause (Confirmed by Frappe Error Log)

For some DM/group chat spaces, `spaces.list` does not provide a usable `displayName`.
We attempted to derive a label via Chat membership listing, but production logs showed:

- `Google Chat Memberships Error ... memberships.list failed: 404 <h1>Not Found</h1>`

Meaning the `/v1/{space}/memberships` endpoint returned HTML 404 in this deployment.

### Fix (Implemented)

Backend now tries:
1) `GET /v1/{space}/memberships`
2) If **404**, fallback to legacy `GET /v1/{space}/members`

and derives labels from membership `member.displayName` when available.

### Limitation (Confirmed by Production Logs)

In our current Google Chat tenant/API behavior, member listing for **DIRECT_MESSAGE** and many unnamed **GROUP_CHAT** spaces is unreliable:
- `memberships` endpoint can return **404**
- adding `fields=` or `readMask=` has produced **400 INVALID_ARGUMENT**

Result: for many DMs/group chats Google does not provide enough data to derive a human-friendly label.

### Product Decision (Implemented)

To avoid showing users opaque IDs in the dropdown:
- **Filter out all `DIRECT_MESSAGE` spaces**
- **Filter out `GROUP_CHAT` spaces whose `displayName` is missing or ID-like**

Named group chats (e.g. “Sam - Ching - Chimes”) and normal spaces remain selectable.

### If it still shows IDs

Check Frappe Error Log for:
- `Google Chat Memberships Error`

Look for `403` (scope issue), `404` (endpoint mismatch), or `401` (token problems).

## Guardrails / How We Prevent This Forever

### 1) Coding rules (mandatory)

- **Do not store OAuth tokens in Password fields** for this project (risk of length constraints).
- Store tokens in **Long Text**, encrypted via `encrypt()` / `decrypt()`.

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


