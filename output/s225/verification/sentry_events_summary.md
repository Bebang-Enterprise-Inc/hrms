# Sentry Events — S225 Sweep Window

Window UTC: 2026-04-28T00:00:00+00:00 → 2026-04-28T01:55:02.581956+00:00

## Project: `bei-hrms`

Total events: 100

### By level


### Top buckets (title-normalized)

| Count | Bucket |
|---|---|
| 97 | `Sales Dashboard: unmapped warehouse dropped` |
| 2 | `PermissionError: Order <ID> is currently assigned to test.area@bebang.ph.` |
| 1 | `S225 follow-up: no commissary route for SM STA. ROSA - SWEET HARMONY FOOD CORP.+DRY; defaulting source to store warehouse. Add a BEI...` |

### Top culprits (file:line)

| Count | Culprit |
|---|---|
| 69 | `/api/method/hrms.api.sales_dashboard.get_sales_dashboard_overview` |
| 28 | `/api/method/hrms.api.sales_dashboard.get_sales_dashboard_access_context` |
| 2 | `frappe in _raise_exception` |
| 1 | `/api/method/hrms.api.store.approve_order` |

### First 30 events (chronological)

- [2026-04-28T01:05:12.057000Z] **None** `/api/method/hrms.api.sales_dashboard.get_sales_dashboard_overview` — Sales Dashboard: unmapped warehouse dropped
- [2026-04-28T01:05:12.078000Z] **None** `/api/method/hrms.api.sales_dashboard.get_sales_dashboard_overview` — Sales Dashboard: unmapped warehouse dropped
- [2026-04-28T01:05:12.090000Z] **None** `/api/method/hrms.api.sales_dashboard.get_sales_dashboard_overview` — Sales Dashboard: unmapped warehouse dropped
- [2026-04-28T01:05:12.097000Z] **None** `/api/method/hrms.api.sales_dashboard.get_sales_dashboard_overview` — Sales Dashboard: unmapped warehouse dropped
- [2026-04-28T01:05:12.112000Z] **None** `/api/method/hrms.api.sales_dashboard.get_sales_dashboard_overview` — Sales Dashboard: unmapped warehouse dropped
- [2026-04-28T01:05:12.129000Z] **None** `/api/method/hrms.api.sales_dashboard.get_sales_dashboard_overview` — Sales Dashboard: unmapped warehouse dropped
- [2026-04-28T01:05:12.162000Z] **None** `/api/method/hrms.api.sales_dashboard.get_sales_dashboard_overview` — Sales Dashboard: unmapped warehouse dropped
- [2026-04-28T01:05:12.166000Z] **None** `/api/method/hrms.api.sales_dashboard.get_sales_dashboard_overview` — Sales Dashboard: unmapped warehouse dropped
- [2026-04-28T01:05:12.189000Z] **None** `/api/method/hrms.api.sales_dashboard.get_sales_dashboard_overview` — Sales Dashboard: unmapped warehouse dropped
- [2026-04-28T01:05:12.200000Z] **None** `/api/method/hrms.api.sales_dashboard.get_sales_dashboard_overview` — Sales Dashboard: unmapped warehouse dropped
- [2026-04-28T01:05:12.204000Z] **None** `/api/method/hrms.api.sales_dashboard.get_sales_dashboard_overview` — Sales Dashboard: unmapped warehouse dropped
- [2026-04-28T01:05:12.211000Z] **None** `/api/method/hrms.api.sales_dashboard.get_sales_dashboard_overview` — Sales Dashboard: unmapped warehouse dropped
- [2026-04-28T01:05:12.216000Z] **None** `/api/method/hrms.api.sales_dashboard.get_sales_dashboard_overview` — Sales Dashboard: unmapped warehouse dropped
- [2026-04-28T01:14:08.202000Z] **None** `frappe in _raise_exception` — PermissionError: Order BEI-ORD-2026-00439 is currently assigned to test.area@bebang.ph.
- [2026-04-28T01:15:26.878000Z] **None** `/api/method/hrms.api.store.approve_order` — S225 follow-up: no commissary route for SM STA. ROSA - SWEET HARMONY FOOD CORP.+DRY; defaulting source to store warehouse. Add a BEI...
- [2026-04-28T01:15:42.316000Z] **None** `frappe in _raise_exception` — PermissionError: Order BEI-ORD-2026-00440 is currently assigned to test.area@bebang.ph.
- [2026-04-28T01:33:09.188000Z] **None** `/api/method/hrms.api.sales_dashboard.get_sales_dashboard_access_context` — Sales Dashboard: unmapped warehouse dropped
- [2026-04-28T01:33:09.206000Z] **None** `/api/method/hrms.api.sales_dashboard.get_sales_dashboard_access_context` — Sales Dashboard: unmapped warehouse dropped
- [2026-04-28T01:33:09.210000Z] **None** `/api/method/hrms.api.sales_dashboard.get_sales_dashboard_overview` — Sales Dashboard: unmapped warehouse dropped
- [2026-04-28T01:33:09.214000Z] **None** `/api/method/hrms.api.sales_dashboard.get_sales_dashboard_access_context` — Sales Dashboard: unmapped warehouse dropped
- [2026-04-28T01:33:09.226000Z] **None** `/api/method/hrms.api.sales_dashboard.get_sales_dashboard_access_context` — Sales Dashboard: unmapped warehouse dropped
- [2026-04-28T01:33:09.231000Z] **None** `/api/method/hrms.api.sales_dashboard.get_sales_dashboard_access_context` — Sales Dashboard: unmapped warehouse dropped
- [2026-04-28T01:33:09.239000Z] **None** `/api/method/hrms.api.sales_dashboard.get_sales_dashboard_overview` — Sales Dashboard: unmapped warehouse dropped
- [2026-04-28T01:33:09.244000Z] **None** `/api/method/hrms.api.sales_dashboard.get_sales_dashboard_access_context` — Sales Dashboard: unmapped warehouse dropped
- [2026-04-28T01:33:09.247000Z] **None** `/api/method/hrms.api.sales_dashboard.get_sales_dashboard_overview` — Sales Dashboard: unmapped warehouse dropped
- [2026-04-28T01:33:09.261000Z] **None** `/api/method/hrms.api.sales_dashboard.get_sales_dashboard_access_context` — Sales Dashboard: unmapped warehouse dropped
- [2026-04-28T01:33:09.266000Z] **None** `/api/method/hrms.api.sales_dashboard.get_sales_dashboard_overview` — Sales Dashboard: unmapped warehouse dropped
- [2026-04-28T01:33:09.275000Z] **None** `/api/method/hrms.api.sales_dashboard.get_sales_dashboard_access_context` — Sales Dashboard: unmapped warehouse dropped
- [2026-04-28T01:33:09.286000Z] **None** `/api/method/hrms.api.sales_dashboard.get_sales_dashboard_overview` — Sales Dashboard: unmapped warehouse dropped
- [2026-04-28T01:33:09.294000Z] **None** `/api/method/hrms.api.sales_dashboard.get_sales_dashboard_access_context` — Sales Dashboard: unmapped warehouse dropped

## Project: `bei-tasks`

Total events: 27

### By level


### Top buckets (title-normalized)

| Count | Bucket |
|---|---|
| 9 | `Error: Frappe API error: 403 - Order <ID> is currently assigned to test.area@bebang.ph.` |
| 8 | `Error: ` |
| 5 | `Error: Frappe API error: 417 - Stock decreased between resolution and dispatch — SCM must re-resolve order line for PM001 (have 0.0, need 5.0) at Pinnacle Cold Storage Solutions - BKI.` |
| 1 | `Error: Frappe API error: 417 - Stock decreased between resolution and dispatch — SCM must re-resolve order line for FG001 (have 0.0, need 5.0) at SM STA. ROSA - SWEET HARMONY FOOD CORP..` |
| 1 | `Error: Frappe API error: 417 - Stock decreased between resolution and dispatch — SCM must re-resolve order line for PM001 (have 0.0, need 5.0) at ROBINSONS ANTIPOLO - BEBANG ENTERPRISE INC..` |
| 1 | `Error: Frappe API error: 417 - Stock decreased between resolution and dispatch — SCM must re-resolve order line for PM001 (have 0.0, need 5.0) at ORTIGAS GREENHILLS - BEIFRANCHISE FOOD OPC.` |
| 1 | `Error: Frappe API error: 417 - Stock decreased between resolution and dispatch — SCM must re-resolve order line for PM001 (have 0.0, need 5.0) at ORTIGAS ESTANCIA - BB ESTANCIA FOOD CORP..` |
| 1 | `Error: Frappe API error: 417 - Stock decreased between resolution and dispatch — SCM must re-resolve order line for PM001 (have 0.0, need 2.0) at Pinnacle Cold Storage Solutions - BKI.` |

### Top culprits (file:line)

| Count | Culprit |
|---|---|
| 18 | `/dashboard/store-ops/order-approvals` |
| 8 | `/dashboard/warehouse/dispatch` |
| 1 | `POST /api/ordering` |

### First 30 events (chronological)

- [2026-04-28T00:33:48.967000Z] **None** `/dashboard/store-ops/order-approvals` — Error: Frappe API error: 417 - Stock decreased between resolution and dispatch — SCM must re-resolve order line for PM001 (have 0.0, need 5.0) at Pinnacle Cold Storage Solutions - BKI.
- [2026-04-28T00:34:05.557000Z] **None** `/dashboard/store-ops/order-approvals` — Error: Frappe API error: 403 - Order BEI-ORD-2026-00405 is currently assigned to test.area@bebang.ph.
- [2026-04-28T00:35:24.374000Z] **None** `/dashboard/store-ops/order-approvals` — Error: Frappe API error: 417 - Stock decreased between resolution and dispatch — SCM must re-resolve order line for PM001 (have 0.0, need 5.0) at Pinnacle Cold Storage Solutions - BKI.
- [2026-04-28T00:35:39.952000Z] **None** `/dashboard/store-ops/order-approvals` — Error: Frappe API error: 403 - Order BEI-ORD-2026-00406 is currently assigned to test.area@bebang.ph.
- [2026-04-28T00:37:55.129000Z] **None** `/dashboard/store-ops/order-approvals` — Error: Frappe API error: 417 - Stock decreased between resolution and dispatch — SCM must re-resolve order line for PM001 (have 0.0, need 5.0) at Pinnacle Cold Storage Solutions - BKI.
- [2026-04-28T00:37:57.660000Z] **None** `POST /api/ordering` — Error: Frappe API error: 417 - Stock decreased between resolution and dispatch — SCM must re-resolve order line for PM001 (have 0.0, need 5.0) at Pinnacle Cold Storage Solutions - BKI.
- [2026-04-28T00:38:10.918000Z] **None** `/dashboard/store-ops/order-approvals` — Error: Frappe API error: 403 - Order BEI-ORD-2026-00408 is currently assigned to test.area@bebang.ph.
- [2026-04-28T00:46:30.648000Z] **None** `/dashboard/warehouse/dispatch` — Error: 
- [2026-04-28T00:46:30.653000Z] **None** `/dashboard/warehouse/dispatch` — Error: 
- [2026-04-28T00:48:45.045000Z] **None** `/dashboard/store-ops/order-approvals` — Error: Frappe API error: 417 - Stock decreased between resolution and dispatch — SCM must re-resolve order line for PM001 (have 0.0, need 2.0) at Pinnacle Cold Storage Solutions - BKI.
- [2026-04-28T00:49:00.771000Z] **None** `/dashboard/store-ops/order-approvals` — Error: Frappe API error: 403 - Order BEI-ORD-2026-00418 is currently assigned to test.area@bebang.ph.
- [2026-04-28T00:50:19.874000Z] **None** `/dashboard/store-ops/order-approvals` — Error: Frappe API error: 417 - Stock decreased between resolution and dispatch — SCM must re-resolve order line for PM001 (have 0.0, need 5.0) at ORTIGAS ESTANCIA - BB ESTANCIA FOOD CORP..
- [2026-04-28T00:50:35.295000Z] **None** `/dashboard/store-ops/order-approvals` — Error: Frappe API error: 403 - Order BEI-ORD-2026-00419 is currently assigned to test.area@bebang.ph.
- [2026-04-28T00:51:53.316000Z] **None** `/dashboard/store-ops/order-approvals` — Error: Frappe API error: 417 - Stock decreased between resolution and dispatch — SCM must re-resolve order line for PM001 (have 0.0, need 5.0) at ORTIGAS GREENHILLS - BEIFRANCHISE FOOD OPC.
- [2026-04-28T00:52:08.899000Z] **None** `/dashboard/store-ops/order-approvals` — Error: Frappe API error: 403 - Order BEI-ORD-2026-00420 is currently assigned to test.area@bebang.ph.
- [2026-04-28T00:53:27.268000Z] **None** `/dashboard/store-ops/order-approvals` — Error: Frappe API error: 417 - Stock decreased between resolution and dispatch — SCM must re-resolve order line for PM001 (have 0.0, need 5.0) at ROBINSONS ANTIPOLO - BEBANG ENTERPRISE INC..
- [2026-04-28T00:53:42.891000Z] **None** `/dashboard/store-ops/order-approvals` — Error: Frappe API error: 403 - Order BEI-ORD-2026-00421 is currently assigned to test.area@bebang.ph.
- [2026-04-28T00:56:20.861000Z] **None** `/dashboard/warehouse/dispatch` — Error: 
- [2026-04-28T00:56:20.867000Z] **None** `/dashboard/warehouse/dispatch` — Error: 
- [2026-04-28T00:58:00.834000Z] **None** `/dashboard/warehouse/dispatch` — Error: 
- [2026-04-28T00:58:00.841000Z] **None** `/dashboard/warehouse/dispatch` — Error: 
- [2026-04-28T00:59:51.214000Z] **None** `/dashboard/warehouse/dispatch` — Error: 
- [2026-04-28T00:59:51.219000Z] **None** `/dashboard/warehouse/dispatch` — Error: 
- [2026-04-28T01:13:49.804000Z] **None** `/dashboard/store-ops/order-approvals` — Error: Frappe API error: 417 - Stock decreased between resolution and dispatch — SCM must re-resolve order line for PM001 (have 0.0, need 5.0) at Pinnacle Cold Storage Solutions - BKI.
- [2026-04-28T01:14:05.689000Z] **None** `/dashboard/store-ops/order-approvals` — Error: Frappe API error: 403 - Order BEI-ORD-2026-00439 is currently assigned to test.area@bebang.ph.
- [2026-04-28T01:15:24.369000Z] **None** `/dashboard/store-ops/order-approvals` — Error: Frappe API error: 417 - Stock decreased between resolution and dispatch — SCM must re-resolve order line for FG001 (have 0.0, need 5.0) at SM STA. ROSA - SWEET HARMONY FOOD CORP..
- [2026-04-28T01:15:39.794000Z] **None** `/dashboard/store-ops/order-approvals` — Error: Frappe API error: 403 - Order BEI-ORD-2026-00440 is currently assigned to test.area@bebang.ph.
