# Discount Monitoring

### DISCMON-001: Raw queue API returns same-day and rolling rows for a recent business date
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

### DISCMON-005: Incident queue clusters duplicate same-day alerts into one work item
- **Type:** regression
- **Role:** `test.hr@bebang.ph`
- **Call:** `GET hrms.api.discount_abuse.get_discount_audit_incident_queue`
- **Params:** `{"business_date": "2026-03-08", "queue_bucket": "same_day"}`
- **Assert:**
  - Response includes `data.parity.same_day_raw_rows`
  - Response includes `data.parity.same_day_clusters`
  - `data.parity.same_day_raw_rows == 84`
  - `data.parity.same_day_clusters == 45`
  - At least one incident row contains `detection_types` with more than one detection
  - At least one same-day incident row includes `resolution_targets`

### DISCMON-006: Daily workbook generation remains available after the queue rewrite
- **Type:** regression
- **Role:** `test.hr@bebang.ph`
- **Call:** `POST hrms.api.discount_abuse.generate_daily_discount_audit_report`
- **Params:** `{"business_date": "2026-03-08"}`
- **Assert:**
  - Response includes `file_url`
  - Response includes `file_name`
  - `file_name` starts with `Discount_Identity_Audit_Report_`

### DISCMON-007: Cluster resolution resolves every underlying raw target
- **Type:** regression
- **Role:** `test.hr@bebang.ph`
- **Call sequence:**
  1. `GET hrms.api.discount_abuse.get_discount_audit_incident_queue`
  2. Pick one unresolved `same_day` incident with `resolution_targets.length >= 2`
  3. `POST hrms.api.discount_abuse.resolve_discount_audit_incident`
- **Params:** incident payload from step 1 with `resolution_code = "under_investigation"`
- **Assert:**
  - Resolution response includes `resolved_count`
  - Resolution response includes `target_count`
  - `resolved_count == target_count`
  - Re-running raw queue lookup shows each underlying target is resolved or absent from unresolved queue

### DISCMON-008: Executive summary returns benchmarked February store risk and statutory burden metrics
- **Type:** regression
- **Role:** `test.hr@bebang.ph`
- **Call:** `GET hrms.api.discount_abuse.get_discount_executive_summary`
- **Params:** `{"start_date": "2026-02-01", "end_date": "2026-02-28", "category_scope": "BOTH", "denominator_scope": "pos_original_gross", "peer_mode": "auto"}`
- **Assert:**
  - Response includes `data.cards`
  - Response includes `data.control_trend`
  - Response includes `data.top_weighted_risk_stores`
  - `data.cards.top_outlier_store.store_name` is populated
  - At least one top weighted risk row includes `weighted_risk_rate`
  - At least one top weighted risk row includes `recorded_sc_pct_of_sales`

### DISCMON-009: Finance reconciliation separates recorded discounts, statutory VAT relief, and other gap
- **Type:** regression
- **Role:** `test.hr@bebang.ph`
- **Call:** `GET hrms.api.discount_abuse.get_discount_finance_reconciliation`
- **Params:** `{"start_date": "2026-02-01", "end_date": "2026-02-28", "category_scope": "BOTH", "denominator_scope": "pos_original_gross"}`
- **Assert:**
  - Response includes `data.totals`
  - Response includes `data.waterfall`
  - `data.totals.recorded_discount_amount >= 0`
  - `data.totals.statutory_vat_relief >= 0`
  - `data.totals.other_discount_gap >= 0`
  - Waterfall contains rows for `recorded_discount`, `statutory_vat_relief`, and `other_discount_gap`

### DISCMON-010: Executive portal renders command view and can pivot into investigation for a ranked store
- **Type:** happy
- **Role:** `test.hr@bebang.ph`
- **Route:** `/dashboard/accounting/discount-abuse`
- **Steps:**
  1. Open the page and switch to `Executive Command`
  2. Set window to `2026-02-01` through `2026-02-28`
  3. Wait for the executive cards and chart sections to render
  4. Click one `Investigate` action from the ranked benchmark table
- **Assert:**
  - Executive view shows KPI cards including `Recorded SC % of Sales`
  - Executive view shows a chart section titled `Finance Reconciliation`
  - Executive view shows a benchmark table with at least one row
  - After clicking `Investigate`, the page switches to `Investigation Analytics`
  - The selected store chip/filter is populated from the executive row
