# S197 Baseline — Pre-Change Measurements

## GitHub Actions billing
**RESOLVED:** BEI GitHub org = **Team plan** (8 seats, unlimited private repo Actions minutes).

## T0.1: Current hourly sync performance (last 100 runs)

| Metric | Value |
|--------|-------|
| Success rate | 99% (99/100) |
| p50 duration | 5.5 min |
| p95 duration | 13.0 min |
| Max duration | 13.0 min |
| Min duration | 4.2 min |

**Impact on S197:** p50 is 5.5 min for a full-day sync (yesterday, ~7500 orders). Today-only sync at morning start has ~500 orders → expected ~2 min. By evening (~5000 orders) approaches ~4 min. The 4-min timeout will cancel runs that exceed budget; `cancel-in-progress: true` + idempotent upsert means the next run picks up safely.

## T0.2: Mosaic rate-limit headroom

| Credential Group | HTTP Status | x-ratelimit-limit | x-ratelimit-remaining |
|------------------|-------------|--------------------|-----------------------|
| Araneta Group (3 stores) | 500 | **60** | 59 |
| Shared Pool (27 stores) | 500 | **60** | 59 |
| Dedicated | 500 | **60** | 59 |

**Finding:** Mosaic enforces **60 requests/minute** per credential group. Rate-limit headers present even on HTTP 500 responses (app-level error, infra-level rate limit).

**Safety analysis:** The sync script uses `REQUEST_INTERVAL = 1.2` seconds between requests per thread, giving ~50 req/min per group — under the 60/min limit. At 5-min cadence, each group gets a fresh window every minute. The Shared Pool (27 stores × 1-2 pages = 27-54 requests at 1.2s spacing) fits within the 60/min window at 32-65 seconds.

**Risk:** If a store has >2 pages of orders (>200 orders/day), a single group could approach the 60/min ceiling during peak hours. Mitigation: the script's built-in 1.2s spacing provides inherent rate limiting.

Observability decision: MODIFY
