# ADR-0003: OAuth Token Storage - Encrypted payloads in User OAuth Token DocType

**Status:** Accepted  
**Date:** 2026-02-26

## Context

1. Google OAuth integrations need token persistence for refresh and API calls.
2. Token fields in User OAuth Token DocType are defined as `Long Text`, not `Password`.
3. Existing utility code encrypts/decrypts token values with Frappe helpers.

## Decision

Store OAuth access/refresh tokens in User OAuth Token records using application-layer encryption via `encrypt()`/`decrypt()`.

## Consequences

1. Token confidentiality depends on Frappe key management and secure secret handling.
2. Legacy Password-field token migration remains supported.
3. Authorization boundaries remain enforced through DocType permissions (`System Manager`).

## Evidence

1. `hrms/hr/doctype/user_oauth_token/user_oauth_token.json`
2. `hrms/utils/google_oauth.py`
3. `hrms/api/google_login.py`
4. `docs/GOOGLE_OAUTH_RUNBOOK.md`

