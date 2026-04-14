# S191 Rollback Runbook

If unified FoodPanda totals surface unexpected issues post-deploy (e.g.,
corrupted channel_mix on the leaderboard, baseline drift on prior-period
deltas, or a specific store's numbers looking wrong), this runbook restores
the pre-S191 Mosaic-only behavior within ~10 minutes.

## 1. Identify the issue
- Check `hq.bebang.ph/app/error-log` for any `Sales Dashboard` errors.
- Check `/api/method/hrms.api.sales_dashboard.get_sales_dashboard_overview`
  response — confirm `summary.foodpanda_sales_without_vat` is unexpectedly
  wrong for a known date range.
- Optional: re-run `python output/s191/baseline_audit.py` to compare live
  SQL vs in-app numbers.

## 2. Revert the PR
```bash
# Locate S191 PR number from docs/plans/SPRINT_REGISTRY.md
GH_TOKEN="" gh pr view <PR#> --repo Bebang-Enterprise-Inc/hrms --json mergeCommit
GH_TOKEN="" gh pr list --repo Bebang-Enterprise-Inc/hrms --state merged \
    --search "S191 in:title" --limit 3
```
Two options:
- **(a) Revert commit** (preferred — keeps S191 branch history, allows re-apply):
  ```bash
  git fetch origin production
  git checkout -b revert-s191 origin/production
  git revert -m 1 <merge_commit_sha>
  git push -u origin revert-s191
  GH_TOKEN="" gh pr create --repo Bebang-Enterprise-Inc/hrms \
      --base production --head revert-s191 \
      --title "revert(S191): restore Mosaic-only FoodPanda channel split" \
      --body "Revert #<PR> — see output/s191/ROLLBACK_RUNBOOK.md"
  ```
- **(b) Emergency hotfix to re-assign `fp_bucket`** (only if a deploy is already
  mid-flight): edit `hrms/api/sales_dashboard.py` lines near 1201 to restore
  `fp_bucket = split.pop("foodpanda", {"gross": 0.0, "net_wo_vat": 0.0, "orders": 0})`
  and remove the `_get_unified_foodpanda_totals_aggregate` call. Push to a
  new hotfix branch, PR, merge. **Do NOT push to the S191 branch.**

## 3. Redeploy
Sam deploys via the standard Frappe workflow (agents do NOT deploy this
sprint). Allow up to 5 minutes for the cache to turn over.

## 4. Cache invalidation — automatic
No manual cache flush needed:
- Outer cache prefixes `summary_s191` / `overview_s191` will be abandoned on
  rollback; new payloads cache under the old `summary` / `overview` prefixes.
- Any payloads still in-flight under `summary_s191` / `overview_s191` expire
  naturally within their 300s TTL.
- Inner `fp_unified_v2` helper is no longer called (the unified helpers are
  removed by the revert), so no residual cache pollution.

## 5. No schema to undo
- No DocType changes.
- No DB migrations.
- No new columns on Supabase tables.
- No new whitelisted API endpoints.

## 6. Success criterion
Within 5 minutes of the rollback deploy landing, March 2026 FP on the main
dashboard shows **₱4,465,088** net (Mosaic-only pre-S191 value).
Verify by hitting:
```bash
curl -s "https://hq.bebang.ph/api/method/hrms.api.sales_dashboard.get_sales_dashboard_overview" \
    -H "Authorization: token <token>" \
    -G --data-urlencode "start_date=2026-03-01" --data-urlencode "end_date=2026-03-31" \
  | jq '.message.summary.foodpanda_sales_without_vat'
```
Expect value ≈ 4,465,088 after rollback.

## 7. Notify
Rollback changes March FP back from ~₱19.4M net → ~₱4.4M net. This is visible
to anyone watching the dashboard. Post the rollback reason in the Sam/CEO
Google Chat thread referenced in `output/s191/SAM_PRE_DEPLOY_NOTICE.md`.
