# S169 Mosaic API Outage Report

**Date:** 2026-04-07T19:36:14+08:00

## Symptom
Mosaic API returning HTTP 500 "Server Error" HTML response on ALL endpoints:
- GET /api/v1/orders/{id} (3 phantom IDs + canonical 49575311)
- GET /api/v1/orders?filter[location_id]=2317
- GET /api/v1/webhooks

## OAuth
OAuth /oauth/token returns HTTP 200 with valid 1024-char access token. Authentication works.
The issue is downstream API endpoints, not credentials.

## Impact on S169
- Phase 7 (webhook registration on 12 credential groups): **BLOCKED** — cannot POST /api/v1/webhooks
- Phase 8 T8.1-T8.6 (Apr 4 SM Marikina tombstone test): **BLOCKED** — verify script's round-trip confirm cannot run
- Phase 8 T8.7 (live self-induced webhook test): **BLOCKED** — cannot create test order

## Plan note
The S169 plan's Design Rationale section says 'my earlier 500s were transient' for the same
/orders/{id} endpoint when investigating the original incident. Indicates Mosaic API has a
history of intermittent 500s on this endpoint family.

## Decision
DEFERRED: Phase 7, Phase 8 T8.1-T8.7 to follow-up session when Mosaic API is healthy.
All committed code, schema, and view rewrites in this PR are net-positive regardless.
