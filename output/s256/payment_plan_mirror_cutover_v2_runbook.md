# Denise PP Seed Cutover Runbook (v3.10 / S256 Phase 4b)

## Purpose

Transition the Suppliers SOA source from Denise PP (one-time opening-balance) to Procurement App (continuous).

## Prerequisites (must ALL be true before flipping)

1. v3.10 deployed with `seedFromProcurementApp_` active
2. Procurement App seed has produced > 0 new rows for >= 3 consecutive hourly cycles
3. Spot-check: randomly sample 5 Procurement App-seeded rows in AP Master Suppliers SOA — confirm supplier name, invoice no, and amount match the source PO
4. Sam has explicitly approved the cutover

## Cutover Steps

1. Edit `s256_ap_view_hourly_sync_v310.gs` line ~70:
   ```javascript
   const denise_pp_seed_disabled = true;   // was: false
   ```
2. Push to Apps Script HEAD: `projects.updateContent`
3. Create new version (increments from current) + promote production deployment
4. Verify next hourly cycle:
   - `stats.denise_seed.seed_disabled === true`
   - `stats.procurement_seed.appended >= 0` (still running)
   - No new rows with SOURCE starting with 'Denise PP' appear after cutover
5. Log cutover timestamp to `_sync_log_v3`

## Verification After Cutover

- Next 24h: check `_sync_log_v3` for any `denise_seed_error` entries
- Denise PP sheet remains accessible (read-only for historical audit)
- Payment Plan mirror (`mirrorDenisePaymentPlanTab_`) is INDEPENDENT of this flag — it keeps running unless `payment_plan_mirror_disabled = true` is ALSO flipped

## Rollback

If Procurement App seed produces bad data or stops:
1. Edit: `const denise_pp_seed_disabled = false;`
2. Push + promote
3. Denise PP seed resumes next cycle
4. Investigate Procurement App issues before retrying cutover

## Who Decides

- **Sam Karazi (CEO)** — sole approver
- Agent does NOT auto-flip this. Sam confirms via explicit instruction.
