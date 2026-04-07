# Q2 — Clearance Module

**Verdict: STUB_CONFIRMED**

Lane F's EMP-STUB-005 finding is correct and is reinforced by backend doctype enumeration.

## Backend Doctype Enumeration (definitive)

Filter: `[["name","like","%Clearance%"]]`

Result:
- `Bank Clearance` — upstream Frappe doctype for **bank reconciliation** (not employees)
- `Bank Clearance Detail` — child of above

**There is NO `BEI Clearance Station`, NO `BEI Clearance Item`, NO `Employee Clearance` doctype.** The clearance domain has zero structured backing data.

Filter: `[["name","like","%Separation%"]]`

Result:
- `Employee Separation` (1 record exists: `HR-EMP-SEP-2026-00001` — this is `test.hr` in active separation state since 2026-03-17, polluting Lane F's view of `/clearance`)
- `BEI Separation Type Item`
- `Employee Separation Template`

So the **Separation** workflow exists and is wired (with templates and 1 live record), but the **Clearance** layer downstream of it is a stub.

## UI Inspection

`/clearance` (visited as test.hr — who happens to be in active separation):

- h1: `Clearance Status`
- Sections rendered: Separation Overview, DOLE Compliance counter (0/2), 3 Key Milestones (Exit Interview / Final Pay Approval / Certificate of Employment)
- has_stations_word: **false**
- has_documenso_word: **false**
- has_item_return: **false**
- Buttons: only `Start Interview` (which navigates to `/clearance/exit-interview`)

`/dashboard/hr/separations` (HR view):

- "Start Separation" button present (workflow CAN be initiated)
- 1 row: "Test HR / TEST-HR-001 / — / Pending / Not Started"
- Helper text: "Click a row to view the exit interview or clearance details"

The page DOES expose a separation creation flow, but the resulting clearance UI surface is purely the milestone tracker (Lane F's observation).

## Verdict Reasoning

The "needs separation context to appear" hypothesis is **disproven**: even though test.hr IS in active separation, the clearance page still has no stations, no items, no Documenso. Therefore the missing functionality is genuinely absent, not gated.

## Lane A Impact

Lane A scenarios that depend on clearance functionality MUST be skipped:

| Scenario family | Status | Why |
|---|---|---|
| EMP-CLEARANCE-STATION-* | **SKIP** | No `BEI Clearance Station` doctype |
| EMP-CLEARANCE-ITEM-RETURN-* | **SKIP** | No item-return UI or doctype |
| EMP-CLEARANCE-DOCUMENSO-* | **SKIP** | No Documenso integration in `/clearance` |
| EMP-SEPARATION-INITIATE | **RUN** | "Start Separation" button works on `/dashboard/hr/separations` |
| EMP-SEPARATION-MILESTONE-VIEW | **RUN** | Clearance milestone tracker is functional (read-only) |
| EMP-EXIT-INTERVIEW-* | **RUN (probe in Lane A)** | `/clearance/exit-interview` route exists with "Start Interview" button — Lane A should verify it accepts answers |
| EMP-COE-DOWNLOAD | **SKIP** | "Available after clearance" — and clearance has no completion path |

## Escalation

This is already a **CRITICAL collateral defect** flagged by Lane F (recommended sprint S167). No new escalation needed beyond preserving Lane F's recommendation. The Wave 1-Full diagnostic CONFIRMS Lane F was right and adds backend evidence that the implementation gap is structural (missing doctypes), not just UI.

## Backend evidence files

- `api_queries/clearance_doctypes.json`
- `api_queries/separation_doctypes.json`
- `api_queries/records_Employee_Separation.json`

## Screenshots

- `screenshots/q2_clearance_page.png`
- `screenshots/q2_separations_list.png`
