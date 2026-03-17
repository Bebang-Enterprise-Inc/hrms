# Commissary Module

### COMMISSARY-001: Commissary dashboard, production, and work-order flow surfaces
- **Type:** workflow-surface
- **Role:** test.commissary@bebang.ph
- **Routes:** `/dashboard/commissary`, `/dashboard/commissary/production`, `/dashboard/commissary/work-orders`
- **Call:** `GET hrms.api.commissary.get_production_history`
- **Call:** `POST hrms.api.commissary.create_work_order`
- **Assert:** Dashboard metrics render and production/work-order forms expose valid create actions.

### COMMISSARY-002: Quality, transfer, and fulfillment operations
- **Type:** workflow-surface
- **Role:** test.commissary@bebang.ph
- **Routes:** `/dashboard/commissary/quality`, `/dashboard/commissary/transfer`, `/dashboard/commissary/fulfillment`
- **Call:** `POST hrms.api.commissary.create_quality_inspection`
- **Call:** `POST hrms.api.commissary.create_hub_transfer`
- **Assert:** Quality and transfer surfaces load with active controls and no route-level failures.

### COMMISSARY-003: Inventory, wastage, raw-material, and expiry monitoring
- **Type:** view
- **Role:** test.commissary@bebang.ph
- **Routes:** `/dashboard/commissary/inventory`, `/dashboard/commissary/raw-materials`, `/dashboard/commissary/wastage`, `/dashboard/commissary/wastage-trends`, `/dashboard/commissary/expiring`
- **Call:** `GET hrms.api.commissary.get_inventory_levels`
- **Call:** `GET hrms.api.commissary.get_wastage_trends`
- **Assert:** Stock, wastage, and expiry alerts are visible and consistent for commissary operators.

### COMMISSARY-004: Commissary labor plan, coverage, and rotation workflow
- **Type:** workflow-surface
- **Role:** test.commissary@bebang.ph
- **Routes:** `/dashboard/commissary/labor-plan`
- **Call:** `GET hrms.api.supervisor.get_labor_plan_bootstrap`
- **Call:** `POST hrms.api.supervisor.apply_weekly_template`
- **Call:** `POST hrms.api.supervisor.publish_weekly_plan`
- **Assert:** Commissary roster grid renders with rotation labels, coverage timeline is visible, overnight-safe shift options are available, and copy/template/publish actions are present for commissary operators.
