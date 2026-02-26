# Connection Map: Projects & Maintenance
**Last Scanned:** 2026-02-23 | **Previous Scan:** 2026-02-17 | **Commit:** 7b998877f

```mermaid
graph TD
    Projects[Projects & Maintenance]
    
    StoreOps((Store Ops))
    Finance((Finance))
    Supervisor((Supervisor))
    Procurement((Procurement))

    Projects ---|5 DATA: Maint Requests, Completion| StoreOps
    Projects ---|4 DATA: Maint Billing, Charges| Finance
    Projects ---|3 DATA: Action Plans, Coaching| Supervisor
    Projects ---|2 DATA: Project Bids, Contracts| Procurement
```
