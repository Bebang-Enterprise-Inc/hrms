# Discount Monitoring

### DISCMON-001: Queue API returns same-day and rolling rows for a recent business date
- **Type:** happy
- **Role:** `test.hr@bebang.ph`
- **Call:** `GET hrms.api.discount_abuse.get_discount_audit_queue`
- **Params:** `{"business_date": "2026-03-07"}`
- **Assert:**
  - Response includes `data.rows`
  - `data.summary` is present
  - At least one row has `queue_bucket` in `same_day` or `rolling_30d`

### DISCMON-002: North EDSA February 13 same-day investigation case is reconstructable
- **Type:** regression
- **Role:** `test.hr@bebang.ph`
- **Call:** `GET hrms.api.discount_abuse.get_discount_investigation_cases`
- **Params:** `{"start_date": "2026-02-13", "end_date": "2026-02-13", "store_names": "SM North EDSA", "discount_bir_category": "SC"}`
- **Assert:**
  - Response includes a row with `detection_type == "same_reference_diff_name_same_day_same_store"`
  - Matching row includes reference `25402`
  - Matching row names include both `HELEN PAGLINGAYEN` and `PETRONA REYES`

### DISCMON-003: North vs Megamall February summary exposes store comparison metrics
- **Type:** regression
- **Role:** `test.hr@bebang.ph`
- **Call:** `GET hrms.api.discount_abuse.get_discount_investigation_summary`
- **Params:** `{"start_date": "2026-02-01", "end_date": "2026-02-28", "store_names": "SM North EDSA,SM Megamall", "discount_bir_category": "SC"}`
- **Assert:**
  - Response includes two store summary rows
  - Store names include `SM North EDSA` and `SM Megamall`
  - `same_day_metrics.repeat_name_findings` is present for each store
  - `contextual_metrics.multi_name_receipts` is present for each store

### DISCMON-004: Investigation analytics requires explicit store selection
- **Type:** edge
- **Role:** `test.hr@bebang.ph`
- **Call:** `GET hrms.api.discount_abuse.get_discount_investigation_summary`
- **Params:** `{"start_date": "2026-02-01", "end_date": "2026-02-28", "discount_bir_category": "SC"}`
- **Assert:**
  - Response has `requires_store_selection == true`
  - Response returns `stores == []`
