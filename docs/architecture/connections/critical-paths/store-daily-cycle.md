# Critical Path: Store Daily Cycle
**Scanned:** 2026-02-17 | **Commit:** 7e445d778

```mermaid
graph LR
    STORE["Store Staff"]
    SUPERVISOR["Supervisor"]
    INVENTORY["Inventory"]
    FINANCE["Finance"]

    STORE -->|1. Submit<br/>Opening Report| SUPERVISOR
    SUPERVISOR -->|2. Review<br/>Photos + Checklist| STORE
    STORE -->|3. Submit<br/>Midshift Check| SUPERVISOR
    SUPERVISOR -->|4. Review<br/>Temp Readings| STORE
    STORE -->|5. Submit<br/>Cashier Handover| SUPERVISOR
    SUPERVISOR -->|6. Review<br/>X-Reading + Cash| STORE
    STORE -->|7. Start<br/>Closing Stage 1 (Cash)| SUPERVISOR
    STORE -->|8. Submit<br/>Stage 2 (Checklist)| SUPERVISOR
    STORE -->|9. Submit<br/>Cycle Count| INVENTORY
    INVENTORY -->|10. Approve<br/>Cycle Count| STORE
    STORE -->|11. Submit<br/>Stage 3 (Photos)| SUPERVISOR
    SUPERVISOR -->|12. Review<br/>Variance if >threshold| FINANCE
    FINANCE -->|13. Investigate<br/>Variance| STORE
    STORE -->|14. Upload<br/>POS Data| SUPERVISOR
    SUPERVISOR -->|15. Review<br/>POS Files| FINANCE
    FINANCE -->|16. Generate<br/>Monthly Billing (franchise)| FINANCE
    STORE -->|17. Submit<br/>Bank Deposit| SUPERVISOR
    SUPERVISOR -->|18. Review<br/>Deposit Slips| FINANCE
```
