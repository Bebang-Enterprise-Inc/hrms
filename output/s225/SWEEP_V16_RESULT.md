# V16 Full 49-Store Sweep Result — 2026-05-03

## Headline

**v16 sweep: 48 passed / 1 failed (1.2h) → MEGAWIDE PITX solo re-run: 1 passed (1.7m) → 49/49 effective.**

Re-validation requested by Sam after recent BD/warehouse setup changes (S231 + S232). All 4 v15-era fixes intact, billing routing preserved, no BD-related regressions.

## Pre-sweep state verification

Verified via `tmp/verify_v15_full_state.py` against `hq.bebang.ph` before launching:

| Check | Result |
|---|---|
| SM MARIKINA Company `is_group=0` | ✓ intact |
| 24 BEI Routes (BEI-ROUTE-0633..0656) exist + active | ✓ all 24 |
| SM MARIKINA in `_get_allowed_target_companies()` | ✓ in list (106 total) |
| All 49 fixture stores have Company + Warehouse + Customer | ✓ all 49 |
| All 49 per-store Companies are leaves (`is_group=0`) | ✓ all 49 |
| Active routes per store | 41/49 with explicit routes; 8 without (same as v15 pre-state, not a regression) |

## Sweep results

| Sweep | Pass | Fail | Skip | Runtime | Notes |
|---|---|---|---|---|---|
| **v15** (2026-05-01, post-S225) | 49 | 0 | 0 | 1.2h | All 4 fixes deployed |
| **v16** (2026-05-03, post-S231/S232) | 48 | 1 | 0 | 1.2h | MEGAWIDE PITX hit transient ECONNRESET |
| **v16-megawide-iso** | 1 | 0 | 0 | 1.7m | Same store solo passes |

## The 1 failure — MEGAWIDE PITX

**Error**: `apiRequestContext.get: read ECONNRESET`

**Stack**: `support/frappeReadback.ts:56` (test-side helper that polls Frappe `/api/resource/Material Request` after MR creation)

**Verdict**: **transient network blip, not a BD regression**. The same store passes solo in 1.7m post-incident with no code changes.

This is the same network-flake class as v11's SM MARIKINA (`dispatch-button` 40s timeout — solo passes 3/3). Single occurrences across full-sweep runs that don't reproduce in isolation. Production users don't run 49 sequential test scenarios in <2m, so they wouldn't hit this access pattern.

## Billing chain audit

Ran `scripts/s225/audit_v15_billing.py` against the 48 v16 SIs:

| Check | Pass |
|---|---|
| `SI.customer` = per-store Customer | **48/48** ✓ |
| `SI.company` = BKI | **48/48** ✓ |
| GL Entry `party=Customer` debits per-store Customer (DM-1) | **48/48** ✓ |
| Customer record exists with valid `customer_name` | **48/48** ✓ |
| `Company.parent_company` = BD holding (per fixture) | **48/48** ✓ |
| `Customer.tax_id` = fixture TIN | 47/48 (1 known fixture-staleness, same as v15) |

**Same single fixture-staleness finding** as v15: ORTIGAS GREENHILLS - BEIFRANCHISE FOOD OPC has TIN `688-721-280-00000` in production but fixture says `tin: ""`. Pre-existing finding from v15 audit (PR #705). Not introduced by S231/S232.

## What's NEW since v15 (S231 + S232 commits)

S231 (markup field, ownership-type guard, monthly billing extension, recipient routing, FT INC. CSV rename, pricing-coupling tests):
- Did NOT break per-store Customer routing
- Did NOT break BKI seller assignment
- Did NOT break GL party booking
- Markup field changes preserved billing chain integrity

S232 (POS ingest hardening — bill-number dedup, cup classification, view filters, payment inference, multi-terminal probe):
- Affects pos_orders / Mosaic ingest path
- Does NOT touch the BKI → store SI happy chain
- No impact observed in v16 sweep

## Post-sweep cleanup

Teardown ran via `scripts/s225/teardown_v4_v5_v6.py` (WHERE remarks LIKE 'S229%' / INTERVAL 12 HOUR):

```
se_count: 62
cancelled: 62
already: 0
errors: 0
stock_settings_after: allow_negative_stock=0, allow_negative_stock_for_batch=0
all_clean: true
```

24 BEI Routes preserved (the routes are permanent, not transient seed data).

## Verdict

✅ **BD changes (S231 + S232) did NOT regress the 49-store happy chain.** All fixes from S225 (auth.ts cache TTL, SM MARIKINA `is_group=0`, 24 BEI Routes, DispatchPage SWR cache-bust) remain intact. Billing chain routes correctly to per-store Customer for all 48 successfully-ran stores. The 1 failure (MEGAWIDE PITX) is a known transient ECONNRESET pattern that doesn't reproduce in isolation.

Production state is clean: no leftover seeds, all canonical records intact, all v15 fixes still applied.
