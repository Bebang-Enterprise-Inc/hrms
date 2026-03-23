# S098: Store Reorder Point Alerts

```yaml
canonical_sprint_id: S098
status: GO
created_date: 2026-03-23
```

## Summary

Add automatic reorder alerts when store inventory drops below minimum threshold.

## L3 Workflow Scenarios

| User | Action | Expected Outcome | Failure Means |
|------|--------|-------------------|---------------|
| test.store@bebang.ph | Open inventory page, verify low-stock items highlighted | Items below reorder point show warning badge | Alert display broken |
| test.store@bebang.ph | Click "Request Restock" on low-stock item → fill qty → submit | Material Request created with correct item and qty | MR creation broken |
| test.warehouse@bebang.ph | Open pending MR list → verify new MR appears | MR visible in warehouse queue | MR routing broken |
