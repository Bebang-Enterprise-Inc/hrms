# S197 POS Sync 5-Minute Interval — Rollback Runbook

## Symptoms that trigger rollback

- Mosaic 429s spike (rate limit `x-ratelimit-remaining` drops to 0 across groups)
- Supabase upsert error rate > 5% (check `scripts/s189_webhook_health_monitor.py` output)
- `pos_sync_freshness` FAIL for > 2 consecutive hourly health checks
- GitHub Actions billing anomaly (unexpected charges — unlikely on Team plan)

## Immediate action (disable in <1 minute)

1. Go to GitHub → Bebang-Enterprise-Inc/hrms → Actions
2. Find **POS Sync (5-Minute Interval)** in the left sidebar
3. Click the **...** menu → **Disable workflow**
4. The next scheduled trigger will NOT fire. Existing in-flight run completes or times out.
5. The hourly `daily-pos-sync.yml` keeps running — data loss risk bounded to 1 hour max.

## Permanent rollback (remove workflow)

```bash
git checkout -b fix/s197-rollback origin/production
rm .github/workflows/pos-sync-5min.yml
git add .github/workflows/pos-sync-5min.yml
git commit -m "rollback(S197): remove 5-min POS sync workflow"
git push -u origin fix/s197-rollback
GH_TOKEN="" gh pr create --repo Bebang-Enterprise-Inc/hrms --base production \
  --head fix/s197-rollback --title "Rollback S197: remove 5-min POS sync"
```

## Partial rollback (throttle to 10 or 15 min)

ALWAYS create a new branch (never push to the sprint branch after PR creation):

```bash
git checkout -b fix/s197-throttle origin/production
```

Edit `.github/workflows/pos-sync-5min.yml`:
- Change `cron: "*/5 2-16 * * *"` to `"*/10 2-16 * * *"` or `"*/15 2-16 * * *"`
- Consider raising `timeout-minutes: 4` to `timeout-minutes: 8` if throttling to 10-min

```bash
git add .github/workflows/pos-sync-5min.yml
git commit -m "fix(S197): throttle POS sync to 10-min cadence"
git push -u origin fix/s197-throttle
GH_TOKEN="" gh pr create ...
```

## Known edge cases

- **Runner infrastructure outage:** GitHub may cancel runs due to runner unavailability (not `cancel-in-progress`). Looks identical in the Actions UI. The hourly health monitor catches this within 10 minutes via `pos_sync_freshness` check.
- **Midnight PHT crossing:** At 00:00 PHT (16:00 UTC), the 5-min workflow's `TZ=Asia/Manila date` rolls over to the new day. Orders from 23:55–23:59 PHT on the old day are NOT re-synced by the 5-min workflow (which now targets the new day). The hourly `daily-pos-sync.yml --daily` run at 00:30 PHT catches the previous day's tail.
- **Mosaic rate limit 60/min:** The sync script's built-in `REQUEST_INTERVAL=1.2s` keeps per-group throughput at ~50 req/min, under the 60/min limit. If multiple concurrent runs overlap (shouldn't happen with `cancel-in-progress: true`), the combined rate could exceed 60/min briefly.

## Monitoring after rollback

After disabling or removing the 5-min workflow:
1. Check `v_webhook_coverage` — hourly poll should still show 100% coverage
2. Check `pos_sync_freshness` — will show WARN (>10 min lag) then stabilize at ~30 min (half of hourly cadence)
3. Check S189 `daily_material_consumption` — consumption data reverts to hourly freshness
