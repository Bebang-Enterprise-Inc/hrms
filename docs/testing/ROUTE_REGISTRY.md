# Route Registry

## Finance & Accounting

| Feature | Route | Test Role | API Endpoint |
|---|---|---|---|
| Discount Identity Monitoring Queue | `/dashboard/accounting/discount-abuse` | `test.hr@bebang.ph` | `hrms.api.discount_abuse.get_discount_audit_dashboard`, `hrms.api.discount_abuse.get_discount_audit_queue`, `hrms.api.discount_abuse.get_discount_audit_incident_queue`, `hrms.api.discount_abuse.generate_daily_discount_audit_report`, `hrms.api.discount_abuse.resolve_discount_audit_alert`, `hrms.api.discount_abuse.resolve_discount_audit_incident` |
| Discount Investigation Analytics | `/dashboard/accounting/discount-abuse` | `test.hr@bebang.ph` | `hrms.api.discount_abuse.get_discount_investigation_summary`, `hrms.api.discount_abuse.get_discount_investigation_cases` |
