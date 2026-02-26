# Connection Map: HR Management
**Last Scanned:** 2026-02-23 | **Previous Scan:** 2026-02-17 | **Commit:** 7b998877f

```mermaid
graph TD
    HRMgmt[HR Management]
    
    HRSelf((HR Self-Service))
    Supervisor((Supervisor))
    Finance((Finance))
    CrossCutting((Cross-cutting))

    HRMgmt ---|5 DATA: Records, Bio, Policies| HRSelf
    HRMgmt -->|3 APPROVAL: Recruitment, Disciplinary| Supervisor
    HRMgmt ---|3 DATA: Payroll, Final Pay| Finance
    HRMgmt -->|5 NOTIFY: GChat, Recruitment| CrossCutting
```
