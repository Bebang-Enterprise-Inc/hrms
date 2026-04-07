# S169 T0.5 — Webhook Signing Probe (Desk Research, No Test Order Created)

**Date:** 2026-04-07
**Method:** Desk research only — read `docs/api/MOSAIC_API.md` (187 lines) end to end and grep for HMAC/signature/secret/X- headers/webhook security. No Mosaic test order was created (per Phase 0 read-only constraint).

## Source reviewed

`F:\Dropbox\Projects\BEI-ERP\docs\api\MOSAIC_API.md` — full file. Section 8 ("Webhooks") is the only place that documents the webhook subsystem:

> ## 8. Webhooks
> ### 8.1-8.4 Full CRUD at `/api/v1/webhooks` and `/api/v1/webhooks/{id}`
> **Events:** `order.created`, `order.completed`, `order.cancelled`, `location.created`, `location.updated`

The doc summary points at the full file at
`F:\Dropbox\Projects\Dice-Roll-Game-Digital\docs\api\MOSAIC_API.md` for
complete request/response examples. Within the local copy, **there is no
mention of HMAC, signing secret, signature header, X-Mosaic-Signature,
X-Webhook-Signature, signing key, or any payload integrity mechanism**.

## Required fields

| Field | Value |
|---|---|
| `mosaic_signs` | `unknown` (not documented in local copy) |
| `signature_header_name` | n/a |
| `hmac_algorithm` | n/a |
| `decision` | **Path B (round-trip confirm via `GET /api/v1/orders/{id}` expect 404)** |
| `decision_rationale` | Plan T0.5 default rule: "Default to Path B if docs don't explicitly document signing." Local copy of MOSAIC_API.md has no signing fields. Path A (HMAC verify) would require guessing the header name and algorithm, which violates the Sprint Plan Compliance and No Scope Drift rules. Path B is also strictly safer because it requires zero trust in header content — Mosaic itself becomes the authority of record via the GET round-trip. |

## Path B implications for Phase 3 (T3.3 / T3.5)

- Webhook receiver does not authenticate via HMAC. It treats the webhook payload as a **hint**, not as authority.
- On every `order.cancelled` (or any `order.*` event we choose to act on), the receiver MUST call `GET /api/v1/orders/{id}` against the Mosaic API and:
  - HTTP 404 -> order is genuinely gone -> tombstone the row (`is_voided=true`, `cancelled_at=now()`, etc.)
  - HTTP 200 -> order still exists -> log discrepancy, do **not** tombstone, surface in observability
  - HTTP 5xx / network -> retry with backoff via `frappe.enqueue`
- **Latency budget:** Plan rule says if round-trip > 2s, T3.5 MUST use `frappe.enqueue` async path. Round-trip latency was NOT measured in Phase 0 (would have required creating + cancelling a test order). Phase 3 implementation MUST measure latency on first real cancel and switch to async if needed. Defaulting to async (`frappe.enqueue`) from day one is the lower-risk choice.

## Open questions to confirm before Phase 3 starts

1. Is there a more recent / longer copy of `MOSAIC_API.md` in the Dice-Roll-Game-Digital folder that documents signing? (Worth checking before committing to Path B permanently.)
2. Does the Mosaic admin UI (when registering a webhook) ask for or display a "signing secret" field? If yes, the local docs are out of date and Path A becomes viable.
3. What is the expected webhook delivery latency from `order.cancelled` event to receiver? This affects whether the round-trip GET race-condition window is meaningful.

## Phase 0 status

Path B is the **safe default**. Phase 3 implementation can proceed against Path B without further Phase 0 work, but answering questions 1-2 above before T3.3 will save rework if signing turns out to be available.
