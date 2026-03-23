# S100: Employee Shift Swap

```yaml
canonical_sprint_id: S100
status: GO
created_date: 2026-03-23
```

## Summary

Allow employees to request shift swaps with colleagues.

## L3 Workflow Scenarios

| User | Action | Expected Outcome | Failure Means |
|------|--------|-------------------|---------------|
| test.crew@bebang.ph | Open shift swap form → select colleague → select target date → submit | Swap request created, status "Pending" | Swap creation broken |
| test.crew@bebang.ph | View pending swap requests | List shows the pending swap with details | List display broken |
| test.area@bebang.ph | Open swap approval → approve request | Status changes to "Approved", shifts swapped | Approval broken |
| test.area@bebang.ph | Open swap approval → reject request | Status changes to "Rejected", no shift change | Rejection broken |
| test.hr@bebang.ph | View swap history for all stores | Complete swap history visible with filters | History view broken |
