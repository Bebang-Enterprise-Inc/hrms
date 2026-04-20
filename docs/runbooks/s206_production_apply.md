# S206 / S207 Production Apply Runbook

**Last updated:** 2026-04-20 (S207 Bimonthly cadence)
**Owner:** Finance (execution) + CEO (authorization)
**Related:**
- Plans: `docs/plans/2026-04-17-sprint-206-reliever-allocation-engine.md`, `docs/plans/2026-04-19-sprint-207-semi-monthly-allocation-and-coa-completion.md`
- TP Policy: `docs/compliance/s206-transfer-pricing-policy.md` (v1.2)
- CEO approval (S207): `docs/compliance/s207-ceo-approval-2026-04-19.md`
- Rollback: `docs/runbooks/s206_rollback.md`

## What this runbook covers

Bimonthly operational flow for the reliever labor cost-sharing engine (twice a month, in sync with the 10th + 25th payroll payouts):

1. Scheduled preview email (cron fires PHT 06:00 on the 1st and 16th)
2. Finance reviews the preview
3. (Optional) manual dry-run for spot-check
4. Apply the allocation (writes paired Journal Entries with payout-date posting)
5. Idempotency re-check (slip-based key; LD-14)
6. Sanity-check the GL

**S207 API note:** the S206 `(year, month)` signature is gone. The engine now takes `(period_start, period_end)` as any date range — half-month for the regular Bimonthly cadence, full-month for ad-hoc Q2 reporting. No backward-compat shim.

## Prerequisites (one-time, already done as of 2026-04-20)

- S206 PRs (#615, #622, gap-closure) + S207 PR merged and deployed
- TP Policy v1.2 active (`docs/compliance/s206-transfer-pricing-policy.md`)
- CEO approval artifact committed (`docs/compliance/s207-ceo-approval-2026-04-19.md`)
- Intercompany accounts + internal Customer/Supplier seeded for all 49 stores (P6 verified 49/49)
- Salary Structures flipped to `Bimonthly` payroll_frequency (P4)

Reseed after a new store is added:

```bash
CONTAINER=$(sudo docker ps --format '{{.Names}}' | grep frappe_backend | head -1)
sudo docker exec $CONTAINER \
  bench --site hq.bebang.ph execute \
  hrms.on_demand.s206_seed_intercompany_accounts.execute
```

Verify coverage (should report 49/49 complete):

```bash
python scripts/s207_verify_coverage_after.py
```

## Bimonthly flow

### Step 1 — Scheduled preview email (automatic)

Cron `0 22 * * *` (daily 22:00 UTC = 06:00 PHT) fires
`hrms.api.labor_allocation.preview_scheduled()`. The function **no-ops unless
the PHT date is the 1st or 16th**. On the firing days it:

- **Day 1:** computes preview for `period = 16-of-previous-month .. end-of-previous-month`
- **Day 16:** computes preview for `period = 1-of-current-month .. 15-of-current-month`
- Emails the summary to **sam@bebang.ph + denise@bebang.ph**
- Includes the exact apply command

If the email doesn't arrive on a firing day, check Error Log for title
`S207 preview_scheduled failed` or `S207 preview_scheduled email failed`.

### Step 2 — Finance reviews the preview

Denise reviews:
- **Planned count** (employees who crossed stores in the half-period)
- **Skipped count** + reasons (`non_store_billing`, `all_home`, `no_punches`, `zero_gross`, `already_allocated`)
- **Per-employee share breakdown** — does it look right given observed attendance?
- **Errors** — investigate before approving apply

The preview gives Finance **9–10 days** before the payout runs (April 10 / 25). If the preview looks correct, notify Sam to apply. Per TP Policy v1.2 § 10, no separate Finance countersignature is required — CEO approval covers apply authority.

### Step 3 — Manual dry-run (optional, for spot-checks)

```bash
CONTAINER=$(sudo docker ps --format '{{.Names}}' | grep frappe_backend | head -1)

# First half: April 1 – April 15
sudo docker exec $CONTAINER \
  bench --site hq.bebang.ph execute \
  hrms.api.labor_allocation.preview_allocation \
  --kwargs '{"period_start": "2026-04-01", "period_end": "2026-04-15"}'

# Second half: April 16 – April 30
sudo docker exec $CONTAINER \
  bench --site hq.bebang.ph execute \
  hrms.api.labor_allocation.preview_allocation \
  --kwargs '{"period_start": "2026-04-16", "period_end": "2026-04-30"}'
```

Returns JSON with `planned`, `skipped`, `errors`. Safe — no DB writes.

### Step 4 — Apply the allocation

**REQUIRES:** TP Policy v1.2 + CEO approval artifact committed (both already in the repo).

```bash
CONTAINER=$(sudo docker ps --format '{{.Names}}' | grep frappe_backend | head -1)

# First half: April 1 – April 15
sudo docker exec -e S206_APPLY=1 $CONTAINER \
  bench --site hq.bebang.ph execute \
  hrms.api.labor_allocation.post_allocation \
  --kwargs '{"period_start": "2026-04-01", "period_end": "2026-04-15"}'

# Second half: April 16 – April 30
sudo docker exec -e S206_APPLY=1 $CONTAINER \
  bench --site hq.bebang.ph execute \
  hrms.api.labor_allocation.post_allocation \
  --kwargs '{"period_start": "2026-04-16", "period_end": "2026-04-30"}'
```

**The `-e S206_APPLY=1` flag is MANDATORY.** Without it the apply path throws (intentional safety gate). The env-var name stays `S206_APPLY` even under S207 — same apply switch, different cadence.

**Ad-hoc full-month (for Q2 2026 reporting):** pass the full month span — the slip-based idempotency key (LD-14) ensures any half-period Log rows already present are skipped, so this is safe even after the per-half-month runs have landed:

```bash
sudo docker exec -e S206_APPLY=1 $CONTAINER \
  bench --site hq.bebang.ph execute \
  hrms.api.labor_allocation.post_allocation \
  --kwargs '{"period_start": "2026-04-01", "period_end": "2026-04-30"}'
```

Expected behaviour on the ad-hoc run: `applied_count=0`, `skipped_idempotent_count` = sum of the two half-month runs' applied counts.

### Step 5 — Idempotency re-check

Re-run the same command — zero new JEs, all idempotent skips:

```bash
sudo docker exec -e S206_APPLY=1 $CONTAINER \
  bench --site hq.bebang.ph execute \
  hrms.api.labor_allocation.post_allocation \
  --kwargs '{"period_start": "2026-04-01", "period_end": "2026-04-15"}'
```

Expected: `applied=[]`, `skipped_idempotent_count` equals the first run's applied count.

### Step 6 — Sanity-check the GL

Frappe Desk → Accounting → Journal Entry. Filter:
- `voucher_type = "Inter Company Journal Entry"`
- `user_remark LIKE 'S206/S207 cost-sharing%'`
- `posting_date` = the **payout date** (25th of same month for first-half slips, 10th of next month for second-half slips)

For any paired JE, confirm:
1. **Home JE** CR `Salaries and Wages - <abbr>`, DR `1104200 - DUE FROM GROUP ENTITIES - <abbr>`
2. **Covered JE** DR `Salaries and Wages - <abbr>`, CR `2104200 - DUE TO GROUP ENTITIES - <abbr>`
3. `inter_company_journal_entry_reference` on each points to the peer JE
4. Salaries row has `party_type='Employee'` + employee docname
5. Due From row has `party_type='Customer'` + internal Customer (peer's internal party)
6. Due To row has `party_type='Supplier'` + internal Supplier (peer's internal party)
7. `cost_center` set to each Company's default
8. `reference_type='Salary Slip'` + `reference_name` pointing to the originating slip
9. `posting_date` = the payout date (NOT slip.end_date) — cross-month example: March 16-31 slip posts on 2026-04-10

If any row fails the check, follow `docs/runbooks/s206_rollback.md` immediately.

## New stores (on Company creation)

When a new Company is added:
1. Run the seeder again (idempotent, always-apply):
   ```bash
   sudo docker exec $CONTAINER bench --site hq.bebang.ph execute \
     hrms.on_demand.s206_seed_intercompany_accounts.execute
   ```
2. Verify 50/50 coverage with `python scripts/s207_verify_coverage_after.py`.
3. If the new Company is a direct child of `BEBANG ENTERPRISE INC.` with empty own-COA, also run `python scripts/s207_create_4_children_root_groups.py` BEFORE the seeder (same S207 P6 pattern).

## Troubleshooting

### "S207 post_allocation requires S206_APPLY=1 env var"
Missing the `-e S206_APPLY=1` flag on `docker exec`. Intentional gate — add the flag. (Note: env-var stays `S206_APPLY` even under the S207 API signature.)

### "Internal Customer for company <X> already exists"
Duplicate internal Customer from a prior run. The seeder handles this transparently (lookup by `represents_company` first). If seen on older code, verify the latest PR is deployed.

### "Please add the account to root level Company - <parent>"
ERPNext parent_company validation. The seeder's `ignore_root_company_validation` flag bypasses this. If seen on the 4 BEBANG ENTERPRISE children, S207 P6 may not have run — call `scripts/s207_create_4_children_root_groups.py` then re-run the seeder.

### Preview email missing on a firing day
1. Check that today is the 1st or 16th PHT (PHT day = UTC day when UTC ≥ 16:00, otherwise UTC day - 1; at 22:00 UTC fire time we are always on the NEXT PHT day).
2. Check Error Log for `S207 preview_scheduled failed` or `S207 preview_scheduled email failed`.
3. Verify the cron wiring: `grep -A2 '"0 22 \* \* \*"' hrms/hooks.py` should show `preview_scheduled`.
4. Verify the module-level imports in `hrms/api/labor_allocation.py` haven't been moved to function-local (LD-16 regression would break mocked tests but not prod).

### Preview email wrong period (day 1 vs day 16)
If preview fires but covers the wrong half-period, it's an LD-17 regression. Check `hrms/api/labor_allocation.py::preview_scheduled` — `pht_date` must come from `datetime.now(timezone.utc).astimezone(PHT).date()` WITHOUT any `+ timedelta(days=1)` arithmetic. The cron fires at UTC 22:00 which is PHT 06:00 of the target date already (UTC+8 timezone shift is the equivalent of +1 day for most of the day).

### First apply hits savepoint errors
Per-slip savepoint isolates failures. Check Error Log for `S207 post_allocation failed for slip <name>`. One bad slip does NOT kill the batch — successful slips still commit.

### posting_date not the payout date
S207 P3 regression. Check `hrms/utils/labor_allocation.py::_build_paired_jes` — first line of the function should call `posting_date = posting_date_for_slip(slip.end_date)`. Both home and covered JE dicts should use `"posting_date": posting_date` (NOT `slip.end_date`).
