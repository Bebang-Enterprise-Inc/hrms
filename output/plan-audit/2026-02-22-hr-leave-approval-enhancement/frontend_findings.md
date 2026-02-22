# Frontend Architecture Audit Findings
## Plan: 2026-02-22-hr-leave-approval-enhancement.md
## Date: 2026-02-22
## Overall Plan Quality: 8/10

### CRITICAL Findings (Missing specs that will block frontend agents)
#### C-01: Missing Data Fetching Strategy (TanStack Query)
**Location in plan:** Phase 3, Tasks 3.1-3.4
**Problem:** The plan describes building the UI but does not specify how the data will be fetched or cached. This will result in multiple agents implementing conflicting `useEffect` fetching patterns or non-cached data, causing terrible UX on a heavy dashboard.
**Fix:** Specify the creation of `use-leave-dashboard.ts` with custom `useQuery` hooks for `get_leave_overview` and `get_all_leaves`, and a `useMutation` hook for `bulk_update_leave_status`.

#### C-02: Missing Optimistic Updates for Action Queue
**Location in plan:** Task 3.3
**Problem:** Approving a leave requires an API call. Without optimistic updates, the UI will freeze or wait for the server before removing the row from the "Action Queue".
**Fix:** Add optimistic update logic in the `useMutation` for `bulk_update_leave_status` to immediately update the local cache and move the item out of the pending list.

### WARNING Findings (Weak specs that will cause inconsistency)
#### W-01: Calendar Component Selection
**Location in plan:** Task 3.2
**Problem:** `react-big-calendar` is heavy and might conflict with the `bei-tasks` project's Tailwind v4 styling since it relies on extensive custom CSS.
**Fix:** Consider using a lightweight custom grid or ensuring the calendar library is properly wrapped in a Shadcn-compatible styling container.

### Summary
- CRITICAL: 2
- WARNING: 1
- INFO: 0
