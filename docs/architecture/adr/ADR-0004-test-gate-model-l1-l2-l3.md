# ADR-0004: Test Gate Model - L1/L2/L3 with Scenario-Catalog Governance

**Status:** Accepted  
**Date:** 2026-02-26

## Context

1. Existing testing method separates L1 API checks, L2 page checks, and L3 workflow verification.
2. V3 flow plan distinguishes runtime pass state from coverage completeness.
3. E2E rules require browser-real actions plus backend verification for L3.

## Decision

Adopt L1/L2/L3 as mandatory production-readiness gate with scenario catalog as source-of-truth.

Gate rules:

1. L1 fail count must be zero.
2. L2 fail count must be zero.
3. L3 fail count and not-implemented count must both be zero for promoted releases.
4. Coverage status remains tracked independently from single-run green status.

## Consequences

1. Release decisions depend on artifact-backed run results.
2. Scenario catalog maintenance is a first-class architecture responsibility.
3. Flow gaps (`partial`/`gap`) remain explicit risk items until closed.

## Evidence

1. `docs/testing/L3_V2_METHOD.md`
2. `docs/testing/E2E_RULES.md`
3. `docs/testing/scenarios/index.yaml`
4. `docs/plans/system-flow-gaps-v3.md`

