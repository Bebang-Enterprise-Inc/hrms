# Sentry Events — S225 Sweep Window

Window UTC: 2026-04-27T00:00:00+00:00 → 2026-04-27T11:22:14.911570+00:00

## Project: `bei-hrms`

Total events: 100

### By level


### Top buckets (title-normalized)

| Count | Bucket |
|---|---|
| 49 | `Sales Dashboard: unmapped warehouse dropped` |
| 15 | `HTTPError: 409 Client Error: Conflict for url: https://csnniykjrychgajfrgua.supabase.co/rest/v1/pos_order_items` |
| 12 | `RuntimeError: object is not bound` |
| 9 | `S225 Lock Contention` |
| 3 | `ValidationError: Stock decreased between resolution and dispatch — SCM must re-resolve order line for PM001 (have 0.0, need 5.0) at Pinnacle Cold Storage Solutions - BKI.` |
| 3 | `ValueError: Invalid site name `$host`` |
| 2 | `PermissionError: Store selection 'BGC' is outside your allowed scope.` |
| 1 | `InvalidWarehouseCompany: Warehouse SM STA. ROSA - SWEET HARMONY FOOD CORP. does not belong to company BEBANG ENTERPRISE INC.` |
| 1 | `ValidationError: The Batch BACKFILL-20260421-FG004-PINNACLE-COLD-STORAGE-SOLUTIONS of an item FG004 has negative stock in the warehouse PINNACLE COLD STORAGE SOLUTIONS - BKI as of 27-04-2026 17:19:14.` |
| 1 | `InvalidWarehouseCompany: Warehouse ROBINSONS ANTIPOLO - BEBANG ENTERPRISE INC. does not belong to company BEBANG ENTERPRISE INC.` |
| 1 | `InvalidWarehouseCompany: Warehouse ORTIGAS GREENHILLS - BEIFRANCHISE FOOD OPC does not belong to company BEBANG ENTERPRISE INC.` |
| 1 | `InvalidWarehouseCompany: Warehouse ORTIGAS ESTANCIA - BB ESTANCIA FOOD CORP. does not belong to company BEBANG ENTERPRISE INC.` |
| 1 | `ValidationError: Stock decreased between resolution and dispatch — SCM must re-resolve order line for PM001 (have 0.0, need 2.0) at Pinnacle Cold Storage Solutions - BKI.` |
| 1 | `PermissionError: Store selection 'SM AURA - BEBANG MEGA INC.' is outside your allowed scope.` |

### Top culprits (file:line)

| Count | Culprit |
|---|---|
| 26 | `/api/method/hrms.api.sales_dashboard.get_sales_dashboard_overview` |
| 21 | `/api/method/hrms.api.sales_dashboard.get_sales_dashboard_access_context` |
| 15 | `/api/method/hrms.api.mosaic_webhook.receive` |
| 9 | `frappe.utils.sentry in set_scope` |
| 8 | `/api/method/hrms.api.store.approve_order` |
| 4 | `frappe in _raise_exception` |
| 3 | `werkzeug.local in _get_current_object` |
| 3 | `frappe in init` |
| 2 | `/api/method/hrms.api.sales_dashboard.get_product_mix_analytics` |

### First 30 events (chronological)

- [2026-04-27T01:44:27.006000Z] **None** `/api/method/hrms.api.sales_dashboard.get_sales_dashboard_overview` — Sales Dashboard: unmapped warehouse dropped
- [2026-04-27T01:44:27.052000Z] **None** `/api/method/hrms.api.sales_dashboard.get_sales_dashboard_access_context` — Sales Dashboard: unmapped warehouse dropped
- [2026-04-27T01:44:27.060000Z] **None** `/api/method/hrms.api.sales_dashboard.get_sales_dashboard_overview` — Sales Dashboard: unmapped warehouse dropped
- [2026-04-27T01:44:27.073000Z] **None** `/api/method/hrms.api.sales_dashboard.get_sales_dashboard_access_context` — Sales Dashboard: unmapped warehouse dropped
- [2026-04-27T01:44:27.167000Z] **None** `/api/method/hrms.api.sales_dashboard.get_sales_dashboard_overview` — Sales Dashboard: unmapped warehouse dropped
- [2026-04-27T01:44:27.182000Z] **None** `/api/method/hrms.api.sales_dashboard.get_sales_dashboard_access_context` — Sales Dashboard: unmapped warehouse dropped
- [2026-04-27T01:44:27.211000Z] **None** `/api/method/hrms.api.sales_dashboard.get_sales_dashboard_access_context` — Sales Dashboard: unmapped warehouse dropped
- [2026-04-27T01:44:27.219000Z] **None** `/api/method/hrms.api.sales_dashboard.get_sales_dashboard_overview` — Sales Dashboard: unmapped warehouse dropped
- [2026-04-27T01:44:27.260000Z] **None** `/api/method/hrms.api.sales_dashboard.get_sales_dashboard_access_context` — Sales Dashboard: unmapped warehouse dropped
- [2026-04-27T01:44:27.268000Z] **None** `/api/method/hrms.api.sales_dashboard.get_sales_dashboard_overview` — Sales Dashboard: unmapped warehouse dropped
- [2026-04-27T01:44:27.334000Z] **None** `/api/method/hrms.api.sales_dashboard.get_sales_dashboard_access_context` — Sales Dashboard: unmapped warehouse dropped
- [2026-04-27T01:44:27.363000Z] **None** `/api/method/hrms.api.sales_dashboard.get_sales_dashboard_access_context` — Sales Dashboard: unmapped warehouse dropped
- [2026-04-27T01:44:27.454000Z] **None** `/api/method/hrms.api.sales_dashboard.get_sales_dashboard_access_context` — Sales Dashboard: unmapped warehouse dropped
- [2026-04-27T01:44:27.493000Z] **None** `/api/method/hrms.api.sales_dashboard.get_sales_dashboard_overview` — Sales Dashboard: unmapped warehouse dropped
- [2026-04-27T01:44:27.527000Z] **None** `/api/method/hrms.api.sales_dashboard.get_sales_dashboard_overview` — Sales Dashboard: unmapped warehouse dropped
- [2026-04-27T01:44:27.640000Z] **None** `/api/method/hrms.api.sales_dashboard.get_sales_dashboard_access_context` — Sales Dashboard: unmapped warehouse dropped
- [2026-04-27T01:44:27.662000Z] **None** `/api/method/hrms.api.sales_dashboard.get_sales_dashboard_access_context` — Sales Dashboard: unmapped warehouse dropped
- [2026-04-27T01:44:27.666000Z] **None** `/api/method/hrms.api.sales_dashboard.get_sales_dashboard_overview` — Sales Dashboard: unmapped warehouse dropped
- [2026-04-27T01:44:27.726000Z] **None** `/api/method/hrms.api.sales_dashboard.get_sales_dashboard_access_context` — Sales Dashboard: unmapped warehouse dropped
- [2026-04-27T01:44:27.747000Z] **None** `/api/method/hrms.api.sales_dashboard.get_sales_dashboard_overview` — Sales Dashboard: unmapped warehouse dropped
- [2026-04-27T01:44:27.755000Z] **None** `/api/method/hrms.api.sales_dashboard.get_sales_dashboard_access_context` — Sales Dashboard: unmapped warehouse dropped
- [2026-04-27T01:44:27.776000Z] **None** `/api/method/hrms.api.sales_dashboard.get_sales_dashboard_overview` — Sales Dashboard: unmapped warehouse dropped
- [2026-04-27T01:44:27.801000Z] **None** `/api/method/hrms.api.sales_dashboard.get_sales_dashboard_overview` — Sales Dashboard: unmapped warehouse dropped
- [2026-04-27T01:44:27.814000Z] **None** `/api/method/hrms.api.sales_dashboard.get_sales_dashboard_access_context` — Sales Dashboard: unmapped warehouse dropped
- [2026-04-27T01:44:27.832000Z] **None** `/api/method/hrms.api.sales_dashboard.get_sales_dashboard_access_context` — Sales Dashboard: unmapped warehouse dropped
- [2026-04-27T01:44:27.851000Z] **None** `/api/method/hrms.api.sales_dashboard.get_sales_dashboard_overview` — Sales Dashboard: unmapped warehouse dropped
- [2026-04-27T01:44:27.861000Z] **None** `/api/method/hrms.api.sales_dashboard.get_sales_dashboard_access_context` — Sales Dashboard: unmapped warehouse dropped
- [2026-04-27T01:44:27.904000Z] **None** `/api/method/hrms.api.sales_dashboard.get_sales_dashboard_overview` — Sales Dashboard: unmapped warehouse dropped
- [2026-04-27T01:44:27.988000Z] **None** `/api/method/hrms.api.sales_dashboard.get_sales_dashboard_overview` — Sales Dashboard: unmapped warehouse dropped
- [2026-04-27T01:44:28.012000Z] **None** `/api/method/hrms.api.sales_dashboard.get_sales_dashboard_overview` — Sales Dashboard: unmapped warehouse dropped

## Project: `bei-tasks`

Total events: 30

### By level


### Top buckets (title-normalized)

| Count | Bucket |
|---|---|
| 6 | `Error: Frappe API error: 417 - Warehouse ROBINSONS ANTIPOLO - BEBANG ENTERPRISE INC. does not belong to company BEBANG ENTERPRISE INC.` |
| 6 | `Error: Frappe API error: 403 - Order <ID> is currently assigned to test.area@bebang.ph.` |
| 3 | `Error: Frappe API error: 417 - Stock decreased between resolution and dispatch — SCM must re-resolve order line for PM001 (have 0.0, need 5.0) at Pinnacle Cold Storage Solutions - BKI.` |
| 3 | `Error: Frappe API error: 417 - Warehouse ORTIGAS ESTANCIA - BB ESTANCIA FOOD CORP. does not belong to company BEBANG ENTERPRISE INC.` |
| 3 | `Error: Frappe API error: 417 - Stock decreased between resolution and dispatch — SCM must re-resolve order line for PM001 (have 0.0, need 2.0) at Pinnacle Cold Storage Solutions - BKI.` |
| 2 | `Error: Frappe API error: 417 - Warehouse SM STA. ROSA - SWEET HARMONY FOOD CORP. does not belong to company BEBANG ENTERPRISE INC.` |
| 2 | `Error: ` |
| 2 | `Error: Frappe API error: 417 - Stock decreased between resolution and dispatch — SCM must re-resolve order line for KL004 (have 0.0, need 3.0) at Pinnacle Cold Storage Solutions - BKI.` |
| 1 | `FrappeHttpError: ` |
| 1 | `Error: Frappe API error: 417 - Warehouse ORTIGAS GREENHILLS - BEIFRANCHISE FOOD OPC does not belong to company BEBANG ENTERPRISE INC.` |
| 1 | `404: /api/method/frappe.integrations.oauth2_logins.login_via_google` |

### Top culprits (file:line)

| Count | Culprit |
|---|---|
| 20 | `/dashboard/store-ops/order-approvals` |
| 6 | `POST /api/ordering` |
| 2 | `/dashboard/warehouse/dispatch` |
| 1 | `POST /api/warehouse` |
| 1 | `/api/method/frappe.integrations.oauth2_logins.login_via_google` |

### First 30 events (chronological)

- [2026-04-27T01:41:03.219000Z] **None** `/dashboard/store-ops/order-approvals` — Error: Frappe API error: 417 - Stock decreased between resolution and dispatch — SCM must re-resolve order line for PM001 (have 0.0, need 2.0) at Pinnacle Cold Storage Solutions - BKI.
- [2026-04-27T01:41:19.080000Z] **None** `/dashboard/store-ops/order-approvals` — Error: Frappe API error: 403 - Order BEI-ORD-2026-00406 is currently assigned to test.area@bebang.ph.
- [2026-04-27T01:42:12.677000Z] **None** `POST /api/ordering` — Error: Frappe API error: 417 - Stock decreased between resolution and dispatch — SCM must re-resolve order line for KL004 (have 0.0, need 3.0) at Pinnacle Cold Storage Solutions - BKI.
- [2026-04-27T01:42:12.800000Z] **None** `/dashboard/store-ops/order-approvals` — Error: Frappe API error: 417 - Stock decreased between resolution and dispatch — SCM must re-resolve order line for KL004 (have 0.0, need 3.0) at Pinnacle Cold Storage Solutions - BKI.
- [2026-04-27T01:42:28.533000Z] **None** `/dashboard/store-ops/order-approvals` — Error: Frappe API error: 403 - Order BEI-ORD-2026-00407 is currently assigned to test.area@bebang.ph.
- [2026-04-27T01:43:22.482000Z] **None** `/dashboard/store-ops/order-approvals` — Error: Frappe API error: 417 - Warehouse ORTIGAS ESTANCIA - BB ESTANCIA FOOD CORP. does not belong to company BEBANG ENTERPRISE INC.
- [2026-04-27T01:43:38.079000Z] **None** `/dashboard/store-ops/order-approvals` — Error: Frappe API error: 403 - Order BEI-ORD-2026-00408 is currently assigned to test.area@bebang.ph.
- [2026-04-27T01:44:35.504000Z] **None** `/dashboard/store-ops/order-approvals` — Error: Frappe API error: 417 - Warehouse ORTIGAS ESTANCIA - BB ESTANCIA FOOD CORP. does not belong to company BEBANG ENTERPRISE INC.
- [2026-04-27T01:44:51.210000Z] **None** `/dashboard/store-ops/order-approvals` — Error: Frappe API error: 403 - Order BEI-ORD-2026-00409 is currently assigned to test.area@bebang.ph.
- [2026-04-27T01:45:42.597000Z] **None** `POST /api/ordering` — Error: Frappe API error: 417 - Warehouse ROBINSONS ANTIPOLO - BEBANG ENTERPRISE INC. does not belong to company BEBANG ENTERPRISE INC.
- [2026-04-27T01:45:42.714000Z] **None** `/dashboard/store-ops/order-approvals` — Error: Frappe API error: 417 - Warehouse ROBINSONS ANTIPOLO - BEBANG ENTERPRISE INC. does not belong to company BEBANG ENTERPRISE INC.
- [2026-04-27T01:45:58.263000Z] **None** `/dashboard/store-ops/order-approvals` — Error: Frappe API error: 403 - Order BEI-ORD-2026-00410 is currently assigned to test.area@bebang.ph.
- [2026-04-27T01:46:51.579000Z] **None** `POST /api/ordering` — Error: Frappe API error: 417 - Warehouse ROBINSONS ANTIPOLO - BEBANG ENTERPRISE INC. does not belong to company BEBANG ENTERPRISE INC.
- [2026-04-27T01:46:51.686000Z] **None** `/dashboard/store-ops/order-approvals` — Error: Frappe API error: 417 - Warehouse ROBINSONS ANTIPOLO - BEBANG ENTERPRISE INC. does not belong to company BEBANG ENTERPRISE INC.
- [2026-04-27T01:47:07.141000Z] **None** `/dashboard/store-ops/order-approvals` — Error: Frappe API error: 403 - Order BEI-ORD-2026-00411 is currently assigned to test.area@bebang.ph.
- [2026-04-27T02:24:29.061000Z] **None** `/api/method/frappe.integrations.oauth2_logins.login_via_google` — 404: /api/method/frappe.integrations.oauth2_logins.login_via_google
- [2026-04-27T08:52:31.160000Z] **None** `/dashboard/store-ops/order-approvals` — Error: Frappe API error: 417 - Stock decreased between resolution and dispatch — SCM must re-resolve order line for PM001 (have 0.0, need 5.0) at Pinnacle Cold Storage Solutions - BKI.
- [2026-04-27T08:54:07.220000Z] **None** `/dashboard/store-ops/order-approvals` — Error: Frappe API error: 417 - Stock decreased between resolution and dispatch — SCM must re-resolve order line for PM001 (have 0.0, need 5.0) at Pinnacle Cold Storage Solutions - BKI.
- [2026-04-27T09:08:54.476000Z] **None** `/dashboard/store-ops/order-approvals` — Error: Frappe API error: 417 - Stock decreased between resolution and dispatch — SCM must re-resolve order line for PM001 (have 0.0, need 2.0) at Pinnacle Cold Storage Solutions - BKI.
- [2026-04-27T09:08:54.610000Z] **None** `POST /api/ordering` — Error: Frappe API error: 417 - Stock decreased between resolution and dispatch — SCM must re-resolve order line for PM001 (have 0.0, need 2.0) at Pinnacle Cold Storage Solutions - BKI.
- [2026-04-27T09:10:28.638000Z] **None** `/dashboard/store-ops/order-approvals` — Error: Frappe API error: 417 - Warehouse ORTIGAS ESTANCIA - BB ESTANCIA FOOD CORP. does not belong to company BEBANG ENTERPRISE INC.
- [2026-04-27T09:12:02.275000Z] **None** `/dashboard/store-ops/order-approvals` — Error: Frappe API error: 417 - Warehouse ORTIGAS GREENHILLS - BEIFRANCHISE FOOD OPC does not belong to company BEBANG ENTERPRISE INC.
- [2026-04-27T09:13:35.502000Z] **None** `/dashboard/store-ops/order-approvals` — Error: Frappe API error: 417 - Warehouse ROBINSONS ANTIPOLO - BEBANG ENTERPRISE INC. does not belong to company BEBANG ENTERPRISE INC.
- [2026-04-27T09:13:35.655000Z] **None** `POST /api/ordering` — Error: Frappe API error: 417 - Warehouse ROBINSONS ANTIPOLO - BEBANG ENTERPRISE INC. does not belong to company BEBANG ENTERPRISE INC.
- [2026-04-27T09:19:14.665000Z] **None** `/dashboard/warehouse/dispatch` — Error: 
- [2026-04-27T09:19:14.669000Z] **None** `/dashboard/warehouse/dispatch` — Error: 
- [2026-04-27T09:19:14.820000Z] **None** `POST /api/warehouse` — FrappeHttpError: 
- [2026-04-27T09:37:03.260000Z] **None** `/dashboard/store-ops/order-approvals` — Error: Frappe API error: 417 - Stock decreased between resolution and dispatch — SCM must re-resolve order line for PM001 (have 0.0, need 5.0) at Pinnacle Cold Storage Solutions - BKI.
- [2026-04-27T09:38:38.624000Z] **None** `/dashboard/store-ops/order-approvals` — Error: Frappe API error: 417 - Warehouse SM STA. ROSA - SWEET HARMONY FOOD CORP. does not belong to company BEBANG ENTERPRISE INC.
- [2026-04-27T09:38:38.850000Z] **None** `POST /api/ordering` — Error: Frappe API error: 417 - Warehouse SM STA. ROSA - SWEET HARMONY FOOD CORP. does not belong to company BEBANG ENTERPRISE INC.
