# Connection Map: HR Self-Service
**Last Scanned:** 2026-02-23 | **Previous Scan:** 2026-02-17 | **Commit:** 7b998877f

```mermaid
graph TD
    HRSelf[HR Self-Service]
    
    HRMgmt((HR Management))
    Supervisor((Supervisor))
    CrossCutting((Cross-cutting))
    Finance((Finance))

    HRSelf ---|5 DATA: Leave, Attendance, Bio| HRMgmt
    HRSelf -->|4 APPROVAL: Leave, Correction, OB| Supervisor
    HRSelf -->|4 NOTIFY: GChat, Announcements| CrossCutting
    HRSelf ---|1 SHARED: Payroll Link| Finance
```
