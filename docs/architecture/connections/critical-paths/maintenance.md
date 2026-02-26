# Critical Path: Maintenance Request
**Scanned:** 2026-02-17 | **Commit:** 7e445d778

```mermaid
graph LR
    STORE["Store Staff"]
    PROJECTS["Projects Team"]
    SUPERVISOR["Supervisor"]
    FINANCE["Finance"]

    STORE -->|1. Submit<br/>Maintenance Request| PROJECTS
    PROJECTS -->|2. Assign<br/>to Technician/Vendor| PROJECTS
    PROJECTS -->|3. Update<br/>Status to In Progress| STORE
    PROJECTS -->|4. Record<br/>Completion + Photos| PROJECTS
    PROJECTS -->|5. Assess<br/>Concern Type| FINANCE
    FINANCE -->|6. Set<br/>Charge (if Supplier/Contractor)| SUPERVISOR
    SUPERVISOR -->|7. Acknowledge<br/>Charge| PROJECTS
    PROJECTS -->|8. Mark<br/>Verified| FINANCE
    FINANCE -->|9. Create<br/>Billing (future)| STORE
```
