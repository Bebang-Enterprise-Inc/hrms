# S099: Wastage Tracking Improvements

```yaml
canonical_sprint_id: S099
status: GO
created_date: 2026-03-23
```

## Summary

Improve wastage logging with reason codes and supervisor approval.

## L3 Workflow Scenarios

| User | Action | Expected Outcome | Failure Means |
|------|--------|-------------------|---------------|
| test.store@bebang.ph | Fill wastage form: item=ITEM-001, qty=2, reason=expired → click Log | Success toast, stock entry created | Wastage logging broken |
| test.store@bebang.ph | Fill wastage form with qty > 10 → click Log | Requires supervisor approval, status "Pending Approval" | Approval threshold broken |
| test.warehouse@bebang.ph | Open pending approvals → approve wastage | Status changes to "Approved", stock deducted | Approval workflow broken |
