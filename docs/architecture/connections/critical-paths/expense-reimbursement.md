# Critical Path: Expense Reimbursement
**Scanned:** 2026-02-17 | **Commit:** 7e445d778

```mermaid
graph LR
    EMPLOYEE["Employee<br/>(Store Staff)"]
    SUPERVISOR["Supervisor<br/>(Custodian)"]
    FINANCE["Finance<br/>(Accounting)"]

    EMPLOYEE -->|1. Submit<br/>Expense + Receipt| EXPENSES
    EXPENSES -->|2. OCR<br/>Extract Data| GEMINI
    GEMINI -->|3. Return<br/>Vendor/Amount/Date| EXPENSES
    EXPENSES -->|4. Calculate<br/>Match Score| EXPENSES
    EXPENSES -->|5. Classify<br/>COA| AI_MODEL
    AI_MODEL -->|6. Return<br/>COA Suggestion| EXPENSES
    EXPENSES -->|7. Add to<br/>PCF Pending| SUPERVISOR
    SUPERVISOR -->|8. Submit<br/>Batch (threshold/month-end)| FINANCE
    FINANCE -->|9. Review<br/>Batch| FINANCE
    FINANCE -->|10. Approve<br/>Batch| SUPERVISOR
    SUPERVISOR -->|11. Request<br/>Replenishment| FINANCE
    FINANCE -->|12. Process<br/>Replenishment| EMPLOYEE

    EXPENSES["Expenses<br/>Module"]
    GEMINI["Gemini<br/>2.0 Flash OCR"]
    AI_MODEL["Rules + ML<br/>+ OpenAI GPT-3.5"]
```
