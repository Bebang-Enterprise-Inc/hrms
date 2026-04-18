# S206 Rollback Runbook

**Last updated:** 2026-04-18
**Owner:** CEO (authorization) + Finance (validation) + Engineering (execution)
**Related:**
- Plan: `docs/plans/2026-04-17-sprint-206-reliever-allocation-engine.md`
- Apply: `docs/runbooks/s206_production_apply.md`
- TP Policy: `docs/compliance/s206-transfer-pricing-policy.md`

## When to roll back

Roll back an S206 allocation run if ANY of:
- Finance identifies material mis-allocation (wrong amount, wrong Company, wrong period)
- An employee's shift-share is wrong (bad device mapping, duplicate punches, timezone drift)
- Paired JEs are not balanced or reference the wrong period
- Finance declines to countersign the TP Policy after an apply already ran

Do NOT roll back for minor reporting differences. Cost-sharing reclasses are not tax-triggering so small corrections can be handled in the next month's allocation.

## Rollback scope decision

| Scope | When | Action |
|---|---|---|
| **Single slip** | One employee's allocation is wrong | Cancel the pair(s) for that slip only |
| **Single Company pair** | Home↔covered pair is wrong (e.g., wrong covered Company) | Cancel all pairs with that (home, covered) combo |
| **Whole month** | Systematic bug (parameter wrong, code regression) | Cancel every S206 JE for the month |
| **Code-level** | Engine itself is broken | Code rollback via `git revert` + redeploy + data rollback for active period |

## Step 1 — Identify affected JEs

```bash
CONTAINER=$(sudo docker ps --format '{{.Names}}' | grep frappe_backend | head -1)

# All S206 JEs for a given month:
sudo docker exec $CONTAINER bench --site hq.bebang.ph mariadb -e "
  SELECT je.name, je.company, je.posting_date, je.total_debit, je.inter_company_journal_entry_reference
  FROM \`tabJournal Entry\` je
  WHERE je.voucher_type = 'Inter Company Journal Entry'
    AND je.user_remark LIKE 'S206 cost-sharing%'
    AND YEAR(je.posting_date) = 2026
    AND MONTH(je.posting_date) = 4
    AND je.docstatus = 1
  ORDER BY je.posting_date, je.name;
"
```

For single-slip scope, filter by employee:

```bash
... AND je.accounts LIKE '%EMP-<id>%'
```

Or query the Log:

```bash
sudo docker exec $CONTAINER bench --site hq.bebang.ph mariadb -e "
  SELECT name, employee, home_company, home_jes_json, covered_jes_json
  FROM \`tabBEI Labor Allocation Log\`
  WHERE year = 2026 AND month = 4 AND employee = 'EMP-<id>';
"
```

## Step 2 — Cancel JEs in pairs

Frappe validates that Inter Company JEs cancel as a pair. Always cancel home + covered together.

```python
# Script: scripts/s206_cancel_pairs.py (create as needed)
import frappe

PAIRS_TO_CANCEL = [
    # (home_je_name, covered_je_name)
    ("ACC-JV-2026-00123", "ACC-JV-2026-00124"),
    # ...
]

for home_name, covered_name in PAIRS_TO_CANCEL:
    home = frappe.get_doc("Journal Entry", home_name)
    covered = frappe.get_doc("Journal Entry", covered_name)
    home.cancel()
    covered.cancel()
    print(f"Cancelled pair: {home_name} + {covered_name}")

frappe.db.commit()
```

Run via bench:

```bash
sudo docker exec $CONTAINER bench --site hq.bebang.ph execute <path_to_script>
```

## Step 3 — Delete Log rows for the cancelled scope

The Log tracks idempotency. If you want the allocation to run fresh later, delete the Log rows so they don't block re-allocation.

```bash
sudo docker exec $CONTAINER bench --site hq.bebang.ph mariadb -e "
  DELETE FROM \`tabBEI Labor Allocation Log\`
  WHERE year = 2026 AND month = 4
    AND employee = 'EMP-<id>';
"
```

For whole-month rollback:

```bash
sudo docker exec $CONTAINER bench --site hq.bebang.ph mariadb -e "
  DELETE FROM \`tabBEI Labor Allocation Log\`
  WHERE year = 2026 AND month = 4;
"
```

**WARNING:** Only delete Log rows for JEs you have cancelled first. Deleting without cancel leaves orphan JEs in GL.

## Step 4 — Verify rollback

```bash
# Should return 0 submitted S206 JEs for the cancelled scope:
sudo docker exec $CONTAINER bench --site hq.bebang.ph mariadb -e "
  SELECT COUNT(*) FROM \`tabJournal Entry\`
  WHERE voucher_type = 'Inter Company Journal Entry'
    AND user_remark LIKE 'S206 cost-sharing%'
    AND YEAR(posting_date) = 2026
    AND MONTH(posting_date) = 4
    AND docstatus = 1
    AND employee_in_accounts_table = 'EMP-<id>';  -- adapt per scope
"
```

## Step 5 — Code rollback (only if the engine itself is the bug)

```bash
# From repo root
git fetch origin
git checkout -b revert/s206-<reason> origin/production
git revert <merge_commit_sha>  # e.g. a3575ee5a for PR #615
git push -u origin revert/s206-<reason>

GH_TOKEN="" gh pr create --repo Bebang-Enterprise-Inc/hrms --base production \
  --head revert/s206-<reason> \
  --title "revert(S206): <reason>" \
  --body "Rolls back S206 engine due to <reason>. Data rollback already executed per s206_rollback runbook."
```

Seeded accounts (102 Due From/To) and internal Customers/Suppliers are safe to leave — they're harmless if unused. Rollback code without rolling back data is fine.

## Step 6 — Communicate

1. Email Finance (Denise) + CEO (Sam) with:
   - What was rolled back (scope)
   - Which JE names cancelled
   - Why the rollback was needed
   - What's different going forward
2. Update the plan file's execution_summary if it's a material rollback.
3. Add a memory entry if the cause is systemic (future agents need to know).

## Safety checklist before cancelling any JE

- [ ] Finance has confirmed the rollback is needed
- [ ] JE names match the Log exactly (not a different intercompany JE)
- [ ] Cancellation is paired (home + covered cancelled together)
- [ ] Log deletion only happens AFTER JE cancellation succeeds
- [ ] Production DB backup is fresh (nightly is acceptable)
