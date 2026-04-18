# S206 Production Apply Runbook

**Last updated:** 2026-04-18
**Owner:** Finance (execution) + CEO (authorization)
**Related:**
- Plan: `docs/plans/2026-04-17-sprint-206-reliever-allocation-engine.md`
- TP Policy: `docs/compliance/s206-transfer-pricing-policy.md`
- Rollback: `docs/runbooks/s206_rollback.md`

## What this runbook covers

Monthly operational flow for the S206 Reliever Labor Cost-Sharing Engine:
1. Preview the month's allocation (dry-run, safe)
2. Review the preview with Finance
3. Apply the allocation (writes paired Journal Entries)
4. Idempotency re-check
5. Sanity-check the GL

## Prerequisites (one-time)

- PR #615 + PR #622 + gap-closure PR merged and deployed
- TP Policy signed by CEO (`docs/compliance/s206-transfer-pricing-policy.md` § 10)
- Intercompany accounts + internal Customer/Supplier records seeded:

```bash
CONTAINER=$(sudo docker ps --format '{{.Names}}' | grep frappe_backend | head -1)

sudo docker exec $CONTAINER \
  bench --site hq.bebang.ph execute \
  hrms.on_demand.s206_seed_intercompany_accounts.execute
```

Verify (should list 102 accounts — 51 Companies × 2):
```bash
sudo docker exec $CONTAINER bench --site hq.bebang.ph mariadb -e \
  "SELECT company, COUNT(*) FROM tabAccount WHERE name LIKE '%GROUP ENTITIES%' GROUP BY company;"
```

## Monthly flow

### Step 1 — Scheduled preview email (automatic, 06:00 PHT on the 1st)

The cron `0 22 1 * *` fires `hrms.api.labor_allocation.preview_monthly_allocation_scheduled()` which:
- Computes the prior month's allocation (no DB writes)
- Emails the summary to **sam@bebang.ph + denise@bebang.ph**
- Includes the exact apply command

If the email doesn't arrive, check Error Log for title `S206 monthly preview cron failed` or `S206 preview cron email failed`.

### Step 2 — Finance reviews the preview

Denise reviews:
- **Planned count** (employees who crossed stores)
- **Skipped count** + reasons (non_store_billing, all_home, no_punches, zero_gross)
- **Per-employee share breakdown** — does it look right given observed attendance?
- **Errors** — investigate before approving apply

If preview looks correct, Denise countersigns the TP Policy (file signature section) and notifies Sam to apply.

### Step 3 — Manual dry-run (optional, for spot-checks)

```bash
CONTAINER=$(sudo docker ps --format '{{.Names}}' | grep frappe_backend | head -1)

sudo docker exec $CONTAINER \
  bench --site hq.bebang.ph execute \
  hrms.api.labor_allocation.preview_monthly_allocation \
  --kwargs '{"year": 2026, "month": 4}'
```

Returns JSON with `planned`, `skipped`, `errors`. Safe — no DB writes.

### Step 4 — Apply the allocation

**REQUIRES:** TP Policy CEO + Finance both signed. Preview reviewed. Run ONLY after confirmation.

```bash
CONTAINER=$(sudo docker ps --format '{{.Names}}' | grep frappe_backend | head -1)

sudo docker exec -e S206_APPLY=1 $CONTAINER \
  bench --site hq.bebang.ph execute \
  hrms.api.labor_allocation.post_monthly_allocation \
  --kwargs '{"year": 2026, "month": 4}'
```

**The `-e S206_APPLY=1` flag is MANDATORY.** Without it the apply path throws (intentional safety gate).

### Step 5 — Idempotency re-check

Run the same command again immediately:

```bash
sudo docker exec -e S206_APPLY=1 $CONTAINER \
  bench --site hq.bebang.ph execute \
  hrms.api.labor_allocation.post_monthly_allocation \
  --kwargs '{"year": 2026, "month": 4}'
```

Expected: `applied=[]`, `skipped_idempotent_count` equals the first run's applied count. Zero new JEs.

### Step 6 — Sanity-check the GL

Frappe Desk → Accounting → Journal Entry. Filter:
- `voucher_type = "Inter Company Journal Entry"`
- `user_remark LIKE 'S206 cost-sharing%'`
- `posting_date` = end of the month

For any paired JE, confirm:
1. **Home JE** CR `Salaries and Wages - <abbr>`, DR `1104200 - DUE FROM GROUP ENTITIES - <abbr>`
2. **Covered JE** DR `Salaries and Wages - <abbr>`, CR `2104200 - DUE TO GROUP ENTITIES - <abbr>`
3. `inter_company_journal_entry_reference` on each points to the peer JE
4. Salaries row has `party_type='Employee'` + employee docname
5. Due From row has `party_type='Customer'` + internal Customer (peer's internal party)
6. Due To row has `party_type='Supplier'` + internal Supplier (peer's internal party)
7. `cost_center` set to each Company's default
8. `reference_type='Salary Slip'` + `reference_name` pointing to the originating slip

If any row fails the check, follow `docs/runbooks/s206_rollback.md` immediately.

## New stores (on Company creation)

When a new Company is added:
1. Run the seeder again (it's idempotent, always-apply):
   ```bash
   sudo docker exec $CONTAINER bench --site hq.bebang.ph execute \
     hrms.on_demand.s206_seed_intercompany_accounts.execute
   ```
2. The seeder creates Due From + Due To + internal Customer + internal Supplier for the new Company.
3. Existing Customers/Suppliers get the new Company appended to their `companies` allowlist automatically.

## Troubleshooting

### "S206 post_monthly_allocation requires S206_APPLY=1 env var"
Missing the `-e S206_APPLY=1` flag on `docker exec`. Intentional gate — add the flag.

### "Internal Customer for company <X> already exists"
Duplicate internal Customer from a prior run. Seeder handles this transparently in v1.1+ (lookup by `represents_company` first). If seen on older code, `docker exec -e` rebuild or skip that company.

### "Please add the account to root level Company - <parent>"
ERPNext parent_company validation. The seeder's `ignore_root_company_validation` flag (v1.1+) bypasses this. If seen, confirm the latest PR is deployed (`docker exec $CONTAINER grep -c _best_territory .../s206_seed_intercompany_accounts.py` — should return ≥2).

### Preview email missing for Denise
Check `hrms/api/labor_allocation.py` line ~314: `recipients = ["sam@bebang.ph", "denise@bebang.ph"]`. If only Sam is listed, deploy gap-closure PR.

### First apply hits savepoint errors
Per-slip savepoint isolates failures. Check Error Log for `S206 post_monthly_allocation failed for slip <name>`. One bad slip does NOT kill the batch — successful slips still commit.
