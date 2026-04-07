# S169 Phase 8 T8.7 — Live webhook test findings

**Date:** 2026-04-07 (after Frappe deploy)
**Endpoint:** https://hq.bebang.ph/api/method/hrms.api.mosaic_webhook.receive (LIVE)

## Test results

| # | Test | Expected | Actual | Verdict |
|---|---|---|---|---|
| 1 | POST {"event":"ping"} | 200 ping branch | 200 `{"ok":true,"handled":false,"reason":"ping"}` | ✅ PASS |
| 2 | Live order 49575311 (canonical, still exists in Mosaic) | 401 round_trip_confirm_failed | 401 `{"ok":false,"reason":"round_trip_confirm_failed","order_id":49575311}` | ✅ PASS (but see caveat below) |
| 3 | Already-tombstoned phantom 49575307 (Mosaic 404) | 200 handled=false already_tombstoned_or_not_found | 401 round_trip_confirm_failed | ⚠️ GAP |
| 4 | Invalid JSON body | 400 invalid_json | 500 JSONDecodeError (framework throws before endpoint catches) | ⚠️ MINOR |
| 5 | Unknown event (order.created) | 200 ignored | 200 `{"ok":true,"handled":false,"reason":"ignored event: order.created"}` | ✅ PASS |

## Root cause of gap

The endpoint's `_authenticate_webhook()` implementation reads the Mosaic credentials CSV at:

```python
MOSAIC_KEYS_CSV = Path(frappe.get_app_path("hrms")).parent / "data" / "POS_Extraction" / "MOSAIC_POS_API_KEYS.csv"
```

This resolves to `/home/frappe/frappe-bench/apps/data/POS_Extraction/MOSAIC_POS_API_KEYS.csv` inside the Frappe Docker container — but the `data/` directory at the repo root is NOT included in the Docker image build context. Only `hrms/` is copied into `apps/hrms/`.

Result: `_find_credential(location_id)` returns `None` → `_authenticate_webhook()` returns `False` → endpoint returns 401 regardless of whether the round-trip would have confirmed 404 or 200.

Test #2 accidentally passes because BOTH "Mosaic returns 200" AND "CSV not found" produce 401 — the 401 is correct for test #2 but only by coincidence.

## What this means operationally

- ✅ The endpoint is deployed and reachable
- ✅ JSON parsing / event routing / observability context / 'ping' branch all work
- ✅ The endpoint never accidentally tombstones (safety invariant holds — it returns 401 on every cancel request)
- ⚠️ **No cancel request will ever successfully trigger a tombstone UPDATE until the CSV is loaded into the container**
- ⚠️ **Every real Mosaic cancel webhook that fires will return 401** → Mosaic will retry → same 401 → eventually give up

## Fix options (follow-up sprint)

1. **Load credentials from Doppler/bench config** instead of CSV file (preferred — no file dependency)
2. **Copy the CSV into the Docker image** at build time
3. **Store credentials in a Frappe DocType** at deploy time via a fixture
4. **Copy the CSV to `apps/hrms/hrms/data/`** so it ships with the app directory

Option 1 is cleanest. Secret doesn't live on disk in the image, can be rotated via Doppler without rebuild.

## Impact on S169 goals

| Goal | Status |
|---|---|
| Schema lifecycle columns | ✅ DONE |
| map_order fix | ✅ DONE |
| Wrapper view + 13 view rewrites | ✅ DONE |
| Verify script tombstone upgrade | ✅ DONE |
| **Apr 4 SM Marikina tombstone (Phase 8 T8.1-T8.6)** | ✅ DONE (via direct SQL with round-trip 404 confirmed manually) |
| Webhook registration (12 credential groups) | ✅ DONE |
| **Live webhook happy-path tombstone (Phase 8 T8.7)** | ⚠️ BLOCKED on credential-loading fix |

The nightly verify script (Phase 6 upgrade) is the safety net and can still tombstone future phantom-void groups without the webhook — so the S169 goal of "prevent phantom revenue drift" is still achievable via the nightly run. The webhook is additive/near-real-time and will kick in after the cred-loading fix.

## Recommendation

Create a small follow-up fix `S169.1` that:
1. Changes `_authenticate_webhook` to load credentials via `_supabase_query_sql` to the Supabase `mosaic_credentials` table (create one), OR via Doppler env vars mapped from Frappe site_config
2. Removes the filesystem CSV dependency
3. Re-runs this test suite
4. Verifies tests #2 and #3 produce distinct responses

Estimated effort: ~30 min + redeploy.
