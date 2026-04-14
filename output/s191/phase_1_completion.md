# S191 Phase 1 — Completion Report

| Task | Status | Evidence |
|---|---|---|
| 1.1 `_get_unified_foodpanda_totals` helper | ✅ | FULL OUTER JOIN SQL; cache key `fp_unified_v2`; completeness guard (`legacy_partial_mosaic` emitted); straight SUM (Task 0.4 confirmed 0 dupes) |
| 1.2 PostgREST fallback + > 45-day guard | ✅ | `_get_unified_foodpanda_totals_postgrest`; `ilike.delivered` (case-insensitive) used; raises RuntimeError on > 45-day windows without Mgmt token |
| 1.3 `_get_unified_foodpanda_totals_aggregate` | ✅ | Wraps inner helper, returns `{"gross","net_wo_vat","orders"}` |
| 1.4 Python AST parse | ✅ | PARSE OK |

## Grep posture
```
_get_unified_foodpanda_totals           : 6
_get_unified_foodpanda_totals_aggregate : 1
FULL OUTER JOIN                         : 2
fp_unified_v2                           : 1
legacy_partial_mosaic                   : 4
ilike.delivered                         : 3
SupabaseMgmtTokenMissing                : 9
```

## Design notes
- `_apply_fp_completeness_guard` extracted as a small helper so the SQL path and the PostgREST fallback share one decision rule (avoids logic drift).
- Cache TTL 300s via `_cache_get_or_set` — matches the TTL used elsewhere for per-day channel splits.
- Straight SUM used (no `DISTINCT ON`) because Task 0.4 confirmed 0 dupes. PostgREST fallback still dedups defensively in Python by `(order_id, latest synced_at)` to stay safe if future data drifts.
