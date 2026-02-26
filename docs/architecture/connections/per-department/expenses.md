# Connection Map: Expenses & PCF
**Last Scanned:** 2026-02-23 | **Previous Scan:** 2026-02-17 | **Commit:** 7b998877f

```mermaid
graph TD
    Expenses[Expenses & PCF]
    
    Finance((Finance))
    StoreOps((Store Ops))
    Supervisor((Supervisor))
    CrossCutting((Cross-cutting))

    Expenses ---|4 DATA: PCF Batch, Review, GL| Finance
    Expenses ---|2 DATA: Store Petty Cash| StoreOps
    Expenses -->|1 APPROVAL: Batch Approval| Supervisor
    Expenses -->|2 NOTIFY: GChat Alerts| CrossCutting
```
