# Team Module

### TEAM-001: Team list and member detail context
- **Type:** detail
- **Role:** test.supervisor@bebang.ph
- **Routes:** `/dashboard/team`
- **Call:** `GET hrms.api.projects.get_projects_team_users`
- **Assert:** Team list renders with member cards or rows and can open a member context/detail surface.

### TEAM-002: Team visits drilldowns
- **Type:** detail
- **Role:** test.area@bebang.ph
- **Routes:** `/dashboard/team/visits`, `/dashboard/team/visits/[id]`
- **Call:** `GET hrms.api.supervisor.get_store_visits`
- **Assert:** Team visit list and visit detail routes render with correct report metadata.

### TEAM-003: Office team schedule and flex review surface
- **Type:** workflow-surface
- **Role:** test.hr@bebang.ph
- **Routes:** `/dashboard/team/office-schedule`
- **Call:** `GET hrms.api.overtime.get_operational_queue`
- **Call:** `POST hrms.api.supervisor.create_team_attendance_request`
- **Assert:** Office direct-report cards render, pending flex review states are visible, and manager exception actions (`WFH`, `On Duty`, flex review) are available without store-style coverage widgets.
