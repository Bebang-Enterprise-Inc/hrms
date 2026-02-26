# Connection Map: Supervisor Tools
**Last Scanned:** 2026-02-23 | **Previous Scan:** 2026-02-17 | **Commit:** 7b998877f

```mermaid
graph TD
    Supervisor[Supervisor Tools]
    
    StoreOps((Store Ops))
    HRSelf((HR Self))
    Inventory((Inventory))
    HRMgmt((HR Management))
    Projects((Projects))
    Finance((Finance))
    CrossCutting((Cross-cutting))

    Supervisor -->|6 APPROVAL: Reports, Handover| StoreOps
    Supervisor -->|4 APPROVAL: Leave, OB, Attendance| HRSelf
    Supervisor -->|3 APPROVAL: Variance, Adjustments| Inventory
    Supervisor -->|3 APPROVAL: Recruitment, Disciplinary| HRMgmt
    Supervisor ---|3 DATA: Action Plans, Coaching| Projects
    Supervisor ---|2 DATA: Budget, Costs| Finance
    Supervisor -->|5 NOTIFY: GChat, Alerts| CrossCutting
```
