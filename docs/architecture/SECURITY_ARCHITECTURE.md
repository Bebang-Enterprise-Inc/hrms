# Security Architecture - BEI ERP

**Last Updated:** 2026-02-26  
**Owner:** Sam Karazi  
**Next Review:** 2026-03-05  
**Status:** Active reference (v1)

## Scope

This document defines security boundaries for:

1. `my.bebang.ph` (Next.js frontend/API proxy).
2. `hq.bebang.ph` (Frappe backend).
3. Google integrations (OAuth, Chat, Drive).
4. Deployment and secrets handling.

## Trust Boundaries

1. Public client boundary:
   - Browser traffic to `my.bebang.ph` and `hq.bebang.ph`.
2. Application boundary:
   - Next.js API proxy to Frappe API calls.
3. Backend boundary:
   - Frappe services to MariaDB/Redis.
4. External integration boundary:
   - Frappe and services to Google APIs and ADMS endpoint.
5. CI/CD boundary:
   - GitHub Actions to AWS/SSM and Docker Hub using secret-scoped credentials.

## Authentication (AuthN)

Evidence:

1. OAuth login endpoint exists in `hrms/api/google_login.py`.
2. Domain enforcement for login is implemented (`bebang.ph` allowlist/default) in `hrms/api/google_login.py`.
3. Session establishment is handled via Frappe login manager after OAuth success.
4. Frontend proxy forwards `sid` and CSRF token in `bei-tasks/app/api/frappe/[...path]/route.ts`.

## Authorization (AuthZ)

Evidence:

1. Frontend RBAC matrix in `bei-tasks/lib/roles.ts`.
2. Token DocType permissions in `hrms/hr/doctype/user_oauth_token/user_oauth_token.json` restrict access to `System Manager`.
3. Role-to-route testing references are maintained in `docs/testing/ROUTE_REGISTRY.md`.

## Secrets and Key Management

Evidence:

1. `docs/00_START_HERE.md` mandates Doppler and forbids credentials in files.
2. `.github/workflows/build-and-deploy.yml` uses GitHub secrets for AWS, Docker, and Sentry.
3. OAuth token material is encrypted/decrypted through Frappe helpers (`encrypt`/`decrypt`) in `hrms/utils/google_oauth.py`.

Control requirements:

1. No plaintext credential commits.
2. Rotate any secrets exposed in historical docs/examples.
3. Keep deployment secrets in GitHub Secrets or Doppler only.

## Audit and Detection

Evidence:

1. OAuth/integration failures are logged through `frappe.log_error` in Google integration modules.
2. `.github/workflows/dm-checklist-gate.yml` enforces review reminders on GL/payment-risk changes.
3. Synthetic and uptime workflows can send failure alerts through Google Chat webhook.

## Security Controls Matrix

| Control Area | Implemented Control | Evidence | Owner |
|---|---|---|---|
| Identity provider validation | Google OAuth login with domain enforcement | `hrms/api/google_login.py` | Sam Karazi |
| Session protection | CSRF token forwarding on mutating requests | `bei-tasks/app/api/frappe/[...path]/route.ts` | Sam Karazi |
| Token confidentiality | Encrypted token storage helper usage | `hrms/utils/google_oauth.py` | Sam Karazi |
| Privilege boundary | Token DocType restricted to System Manager | `user_oauth_token.json` | Sam Karazi |
| Secret distribution | Doppler/GitHub Secrets policy | `docs/00_START_HERE.md`, workflow files | Sam Karazi |
| Deployment gate | DM checklist workflow reminder | `.github/workflows/dm-checklist-gate.yml` | Sam Karazi |

## Known Security Gaps

1. `docs/MY_BEBANG_PH_COMPLETE_REFERENCE.md` contains literal API key/secret examples and must be redacted/rotated.
2. There is no single dashboard spec for security event monitoring in architecture docs.
3. No documented key rotation cadence exists in architecture artifacts.

## Required Follow-ups

1. Redact credential-like values from reference docs and rotate affected credentials.
2. Add explicit key/token rotation schedule and owners.
3. Add security event dashboard/runbook section for incident triage.
