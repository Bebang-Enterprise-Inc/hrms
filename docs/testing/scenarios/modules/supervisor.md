# Supervisor Module

### SUP-001: Supervisor dashboard, labor plan, and reports feed
- **Type:** workflow-surface
- **Role:** test.area@bebang.ph
- **Routes:** `/dashboard/supervisor`, `/dashboard/supervisor/labor-plan`, `/dashboard/supervisor/reports-feed`
- **Call:** `GET hrms.api.store_dashboard.get_supervisor_dashboard_summary`
- **Call:** `POST hrms.api.supervisor.create_weekly_plan`
- **Assert:** Dashboard widgets, roster-first labor-plan grid, `Copy Previous Week`, `Apply Template`, publish actions, and reports feed render for supervisors.

### SUP-002: Store visits list, detail, and new-visit surface
- **Type:** workflow-surface
- **Role:** test.area@bebang.ph
- **Routes:** `/dashboard/supervisor/visits`, `/dashboard/supervisor/visits/new`, `/dashboard/supervisor/visits/[id]`
- **Call:** `GET hrms.api.supervisor.get_store_visits`
- **Call:** `POST hrms.api.supervisor.acknowledge_visit`
- **Assert:** Visit list/detail routes and new-visit entry form load with stable controls.

### SUP-003: Coaching and action-plan workflows
- **Type:** workflow-surface
- **Role:** test.area@bebang.ph
- **Routes:** `/dashboard/supervisor/coaching`, `/dashboard/supervisor/action-plans`
- **Call:** `POST hrms.api.supervisor.create_coaching_log`
- **Call:** `POST hrms.api.supervisor.create_action_plan`
- **Assert:** Coaching and action-plan forms render with authorized create/update actions.

### SUP-004: Area labor overview and drill-down workflow
- **Type:** workflow-surface
- **Role:** test.area@bebang.ph
- **Routes:** `/dashboard/supervisor/labor-plan/overview`, `/dashboard/supervisor/labor-plan`
- **Call:** `GET hrms.api.supervisor.get_area_schedule_overview`
- **Assert:** Area overview cards and store status rows render, warning counts are visible, and the drill-down action opens a concrete store labor plan for the selected week.
