# Sprint 97: Commissary Handoff Notification Fix + UX

```yaml
canonical_sprint_id: S097
status: COMPLETED
created: 2026-03-23
lane: single
depends_on: null
estimated_work_units: 7
completed_date: 2026-03-23
execution_summary: "5 fixes shipped. Backend PR #317 merged+deployed (hrms). Frontend PR #231 merged+deployed (bei-tasks/Vercel). FIX-1 notification import, FIX-2 dialog header, FIX-3 grouped warehouse targets, FIX-4 grouped dropdown, FIX-5 TS type update."
```

## Problem Statement

Ian Dionisio reported an error when creating a commissary handoff on the Commissary > Transfer page (`my.bebang.ph/dashboard/commissary/transfer`):

```
Error Log: Warehouse handoff notification failed for BEI-WHR-2026-00011:
cannot import name 'send_bot_message' from 'hrms.api.google_chat'
```

**Root cause:** `hrms/api/warehouse.py:66` imports `send_bot_message` which does not exist in `hrms/api/google_chat.py`. The correct function is `send_message_to_space(space_name: str, message: str) -> bool`.

Additionally, Ian requested two UX improvements:
1. The dialog header says "Create Warehouse Handoff" -- should say "Create Commissary Handoff" to match the module context.
2. Target warehouse dropdown shows ALL BKI warehouses alphabetically (Greenhills Ortigas appears first). Should show only 3PL warehouses (3MD, Pinnacle, RCS) as the primary targets, with store warehouses available below a separator for the rare case of direct commissary-to-store dispatch.

## Design Rationale (For Cold-Start Agents)

**Why this exists:** The `_notify_warehouse_handoff` function was added in S093 (UX-011) to notify the Ops GChat space when a commissary handoff is created. The import name `send_bot_message` was a hallucinated function name -- the actual Google Chat sender in `hrms/api/google_chat.py` is `send_message_to_space(space_name: str, message: str) -> bool`. The handoff itself succeeds (the error is caught in a try/except), but the GChat notification silently fails.

**Why the warehouse target restructuring:** BEI's commissary (Bebang Kitchen Inc.) produces finished goods at Shaw BLVD - BKI. These FG are transferred to 3PL cold storage warehouses for distribution to stores. The 3PL partners are:
- **3MD Logistics -- Camangyanan** (wet & dry, Bulacan)
- **Pinnacle Cold Storage Solutions** (frozen, Calamba, Laguna)
- **Royal Cold Storage -- Taytay (RCS)** (frozen, Taytay, Rizal)

These are the ONLY normal destinations for commissary FG handoff. Store warehouses (Greenhills, Estancia, NAIA, etc.) belong to BEI (not BKI), so they are currently excluded by the company filter in `get_internal_receiving_warehouses`. However, there may be future need to send finished goods directly from commissary to stores. Sam requested stores appear below a dotted separator as a secondary option.

**Key trade-off:** We group the dropdown into "3PL Warehouses" (primary) and "Store Warehouses" (secondary, below separator). The backend returns both groups with a `group` field. The frontend renders a separator between them. This is chosen over hiding stores entirely because Sam wants the option available.

**How to identify 3PL warehouses:** The Frappe Warehouse DocType has a `warehouse_type` field. However, the current data may not reliably tag 3PL warehouses with a distinct type. The safest approach is to use a hardcoded list of known 3PL warehouse name patterns (`3MD`, `Pinnacle`, `RCS`/`Royal Cold`), consistent with `hrms/api/erp_sync.py` lines 327-334 and `hrms/api/commissary.py` line 1732. Store warehouses are the rest (non-commissary, non-3PL BKI warehouses plus BEI store warehouses).

**Source references:**
- Notification bug: `hrms/api/warehouse.py:66` (broken import)
- Correct function: `hrms/api/google_chat.py:270` (`send_message_to_space`)
- 3PL names: `hrms/api/erp_sync.py:55-64`, `hrms/api/commissary.py:1732`
- Warehouse target endpoint: `hrms/api/warehouse.py:415` (`get_internal_receiving_warehouses`)
- Frontend page: `../bei-tasks/app/dashboard/commissary/transfer/page.tsx`
- Commissary source warehouse: `hrms/utils/supply_chain_contracts.py:21` (`Shaw BLVD - BKI`)

## Scope

| # | File | Change | Type | Class |
|---|------|--------|------|-------|
| FIX-1 | `hrms/api/warehouse.py` | Fix import: `send_bot_message` -> `send_message_to_space`, fix call signature from `(space_id=, text=)` to positional `(space_name, message)`. Rename local var `space_id` to `space_name`. | Backend bugfix | [EXTEND] |
| FIX-2 | `../bei-tasks/app/dashboard/commissary/transfer/page.tsx` | Change dialog title from "Create Warehouse Handoff" to "Create Commissary Handoff", update description | Frontend UX | [EXTEND] |
| FIX-3 | `hrms/api/warehouse.py` (`get_internal_receiving_warehouses`) | Restructure to return 3PL warehouses as primary group, store warehouses as secondary group, with per-item `group` field (`"3pl"` or `"store"`, lowercase) | Backend UX | [EXTEND] |
| FIX-4 | `../bei-tasks/app/dashboard/commissary/transfer/page.tsx` | Render target warehouse dropdown with grouped options: 3PL first, separator, stores below. Conditional group rendering. Update imports, type, post-submit reset, add `mutateInventory()` to success. | Frontend UX | [EXTEND] |
| FIX-5 | `../bei-tasks/hooks/use-commissary.ts` | Add `group: "3pl" \| "store"` to `WarehouseReceivingTarget` interface | Frontend type | [EXTEND] |

### API Contract (locked)

The `get_internal_receiving_warehouses` endpoint returns:
```json
{
  "success": true,
  "data": [
    {"name": "3MD Logistics...- BKI", "label": "3MD Logistics", "company": "Bebang Kitchen Inc.", "group": "3pl"},
    {"name": "Pinnacle...- BKI", "label": "Pinnacle Cold Storage", "company": "Bebang Kitchen Inc.", "group": "3pl"},
    {"name": "Greenhills...- BEI", "label": "Greenhills Ortigas", "company": "Bebang Enterprise Inc.", "group": "store"}
  ]
}
```
- `group` is a per-item field, values are `"3pl"` or `"store"` (lowercase strings)
- 3PL items sorted first (alphabetical within group), then store items (alphabetical within group)
- Note: this module uses **SWR** (not TanStack Query) for data fetching

## Requirements Regression Checklist

- [ ] Is the import changed to `send_message_to_space` (not any other function)?
- [ ] Is the call signature positional `(space_name, message)` not keyword `(space_id=, text=)`?
- [ ] Does `get_chat_space(SPACE_OPS)` return a `space_name` string compatible with `send_message_to_space`?
- [ ] Does the dialog title say "Commissary" not "Warehouse"?
- [ ] Do 3PL warehouses (3MD, Pinnacle, RCS) appear FIRST in the target dropdown?
- [ ] Do store warehouses appear BELOW a visual separator after the 3PL warehouses?
- [ ] Is the default selection a 3PL warehouse (not a store)?
- [ ] Does the `create_warehouse_receiving` endpoint still accept both 3PL AND store warehouse targets? (The company filter `Bebang Kitchen Inc.` must be relaxed to also allow BEI store warehouses.)
- [ ] Is the commissary source warehouse (Shaw BLVD - BKI) still excluded from targets?
- [ ] Is `WarehouseReceivingTarget` type updated with `group: "3pl" | "store"` field? (FIX-5)
- [ ] Does the post-submit reset (line 157) use `targets.find(t => t.group === "3pl")` not `targets[0]`?
- [ ] Are empty groups conditionally hidden (no floating SelectLabel with zero items)?
- [ ] Is `mutateInventory()` called in the success handler alongside `mutateReceipts()`?
- [ ] Was `_send_message_to_space_internal` verified to accept `spaces/XXXX` format as resource path?

## Phase 1: Backend Fixes (3 units)

### Task 1.1: Fix notification import and call (FIX-1)

**File:** `hrms/api/warehouse.py`, lines 61-80

Replace the broken `_notify_warehouse_handoff` function:

**AUDIT FINDING (B-1):** Before writing the fix, read `hrms/api/google_chat.py:196-268` to verify that `_send_message_to_space_internal` uses the `space_name` parameter as a Google API resource path (i.e., `f"https://chat.googleapis.com/v1/{space_name}/messages"`). The `get_chat_space(SPACE_OPS)` returns `"spaces/AAAAvDZdY-o"` which is a resource path, not a display name. Rename the local variable from `space_id` to `space_name` for clarity.

```python
# BEFORE (broken)
from hrms.api.google_chat import send_bot_message
...
send_bot_message(
    space_id=space_id,
    text=("..."),
)

# AFTER (fixed)
from hrms.api.google_chat import send_message_to_space
...
space_name = get_chat_space(SPACE_OPS)  # renamed from space_id for clarity
if space_name:
    send_message_to_space(
        space_name,
        (
            f"\U0001f4e6 New commissary handoff: *{receiving_name}*\n"
            f"From: {source_warehouse or 'Commissary'} \u2192 To: {target_warehouse or 'Warehouse'}\n"
            f"Check warehouse receiving queue: https://my.bebang.ph/dashboard/warehouse/receiving"
        ),
    )
```

### Task 1.2: Restructure warehouse target endpoint (FIX-3)

**File:** `hrms/api/warehouse.py`, function `get_internal_receiving_warehouses` (line 415)

Changes needed:
1. Define a `_3PL_PATTERNS` tuple: `("3MD", "Pinnacle", "Royal Cold", "RCS")`
2. After building the `filtered` list, classify each warehouse into `group: "3pl"` or `group: "store"` based on whether the warehouse name matches any 3PL pattern (case-insensitive)
3. Sort 3PL warehouses first (alphabetical within group), then store warehouses (alphabetical within group)
4. **Relax the company filter**: Currently only returns `Bebang Kitchen Inc.` warehouses. Must ALSO include `Bebang Enterprise Inc.` warehouses (these are the store warehouses). Exclude commissary operation warehouses and test warehouses from both companies.
5. Return format: `{"success": True, "data": [...], "groups": {"3pl": "3PL Warehouses", "store": "Store Warehouses"}}`

**HARD BLOCKER:** The `create_warehouse_receiving` endpoint (line 484) currently validates `source_company != "Bebang Kitchen Inc." or target_company != "Bebang Kitchen Inc."` and throws an error. This MUST be relaxed to also allow BEI store warehouses as targets. Change to: source must be BKI, target can be BKI or BEI. Without this, selecting a store warehouse in the dropdown will throw a server error. (Source: `hrms/api/warehouse.py:484`)

### Task 1.3: Relax company validation in create_warehouse_receiving

**File:** `hrms/api/warehouse.py`, line 484

Change:
```python
# BEFORE
if source_company != "Bebang Kitchen Inc." or target_company != "Bebang Kitchen Inc.":
    frappe.throw(_("Commissary warehouse handoff must stay within Bebang Kitchen Inc. warehouses"))

# AFTER
if source_company != "Bebang Kitchen Inc.":
    frappe.throw(_("Source warehouse must belong to Bebang Kitchen Inc."))
if target_company not in ("Bebang Kitchen Inc.", "Bebang Enterprise Inc."):
    frappe.throw(_("Target warehouse must belong to BKI or BEI"))
```

## Phase 2: Frontend Fixes (2 units)

### Task 2.1: Update dialog header (FIX-2)

**File:** `../bei-tasks/app/dashboard/commissary/transfer/page.tsx`, line 291

```tsx
// BEFORE
<DialogTitle>Create Warehouse Handoff</DialogTitle>
<DialogDescription>
  Build a pending inbound record for Ian to receive into the warehouse.
</DialogDescription>

// AFTER
<DialogTitle>Create Commissary Handoff</DialogTitle>
<DialogDescription>
  Send finished goods from commissary to a 3PL warehouse or store.
</DialogDescription>
```

### Task 2.2: Grouped target warehouse dropdown (FIX-4)

**File:** `../bei-tasks/app/dashboard/commissary/transfer/page.tsx`, lines 304-316

Replace the flat `<Select>` with grouped rendering. The backend now returns targets with a `group` field ("3pl" or "store"). Render:

```tsx
<SelectContent>
  {/* 3PL warehouses first */}
  <SelectGroup>
    <SelectLabel>3PL Warehouses</SelectLabel>
    {targets.filter(t => t.group === "3pl").map(target => (
      <SelectItem key={target.name} value={target.name}>
        {target.label}
      </SelectItem>
    ))}
  </SelectGroup>
  <SelectSeparator />
  {/* Store warehouses below separator */}
  <SelectGroup>
    <SelectLabel>Store Warehouses</SelectLabel>
    {targets.filter(t => t.group === "store").map(target => (
      <SelectItem key={target.name} value={target.name}>
        {target.label}
      </SelectItem>
    ))}
  </SelectGroup>
</SelectContent>
```

Import `SelectGroup`, `SelectLabel`, `SelectSeparator` from `@/components/ui/select`. (AUDIT: confirmed exported at lines 15, 90, 127, 179 -- no blocker.)

**AUDIT FINDING (B-4):** Conditionally render groups to avoid empty labels:
```tsx
const groups3pl = targets.filter(t => t.group === "3pl");
const groupsStore = targets.filter(t => t.group === "store");

<SelectContent>
  {groups3pl.length > 0 && (
    <SelectGroup>
      <SelectLabel>3PL Warehouses</SelectLabel>
      {groups3pl.map(target => (
        <SelectItem key={target.name} value={target.name}>{target.label}</SelectItem>
      ))}
    </SelectGroup>
  )}
  {groups3pl.length > 0 && groupsStore.length > 0 && <SelectSeparator />}
  {groupsStore.length > 0 && (
    <SelectGroup>
      <SelectLabel>Store Warehouses</SelectLabel>
      {groupsStore.map(target => (
        <SelectItem key={target.name} value={target.name}>{target.label}</SelectItem>
      ))}
    </SelectGroup>
  )}
</SelectContent>
```

**AUDIT FINDING (B-3):** Update BOTH the `useEffect` default (line 77-80) AND the post-submit reset (line 157) to prefer first 3PL:
```tsx
// useEffect default selection
useEffect(() => {
  if (!targetWarehouse && targets.length > 0) {
    const first3pl = targets.find(t => t.group === "3pl");
    setTargetWarehouse(first3pl?.name || targets[0].name);
  }
}, [targets]); // removed targetWarehouse from deps (unnecessary churn)

// post-submit reset (line 157) — MUST ALSO UPDATE:
const defaultTarget = targets.find(t => t.group === "3pl")?.name || targets[0]?.name || "";
setTargetWarehouse(defaultTarget);
```

**AUDIT FINDING (B-5):** Add `mutateInventory()` to success handler (after line 159):
```tsx
if (result.success) {
  toast.success(result.message || `Warehouse handoff ${result.data?.name} created`);
  // ... existing reset code ...
  mutateReceipts();
  mutateInventory(); // ADD: refresh FG stock counts after handoff
}
```

### Task 2.3: Update WarehouseReceivingTarget type (FIX-5)

**File:** `../bei-tasks/hooks/use-commissary.ts`, line 821

Add `group` field to the interface:
```tsx
export interface WarehouseReceivingTarget {
  name: string;
  label: string;
  company: string;
  group: "3pl" | "store";  // AUDIT B-2: required for FIX-4 to compile
}
```

## Phase 3: Closeout (1 unit)

### Task 3.1: Deploy and verify

1. Create PR for `hrms` backend changes (FIX-1, FIX-3, company validation relaxation)
2. Push bei-tasks frontend changes (FIX-2, FIX-4) -- auto-deploys to Vercel
3. Update this plan YAML: status -> COMPLETED, add completed_date and execution_summary
4. Update `docs/plans/SPRINT_REGISTRY.md` row for S097
5. `git add -f docs/plans/` and push

## L3 Workflow Scenarios

| User | Action | Expected Outcome | Failure Means |
|------|--------|-------------------|---------------|
| test.commissary@bebang.ph | Open Commissary > Transfer > New Handoff dialog | Dialog title says "Create Commissary Handoff", description mentions 3PL | FIX-2 not deployed |
| test.commissary@bebang.ph | Check Target Warehouse dropdown | 3PL warehouses (3MD, Pinnacle, RCS) appear first under "3PL Warehouses" header, stores appear below separator under "Store Warehouses" | FIX-3/FIX-4 not working |
| test.commissary@bebang.ph | Verify default target selection | A 3PL warehouse is pre-selected (not a store) | Default selection logic broken |
| test.commissary@bebang.ph | Add SAGO (FG009), qty=1, select 3PL target, click Send to Warehouse | Handoff created successfully, no error toast about notification | FIX-1 import still broken |
| test.commissary@bebang.ph | Add SAGO (FG009), qty=1, select a STORE target, click Send to Warehouse | Handoff created successfully (no company validation error) | Company validation not relaxed |

Evidence files required before closeout:
```
output/l3/s097/form_submissions.json
output/l3/s097/api_mutations.json
output/l3/s097/state_verification.json
```

## Autonomous Execution Contract

- completion_condition:
  - FIX-1 import error resolved, GChat notification sends successfully
  - FIX-2 dialog header updated on production
  - FIX-3 backend returns grouped 3PL + store warehouses
  - FIX-4 frontend renders grouped dropdown with separator
  - Company validation allows BEI store warehouses as targets
  - plan YAML status updated to COMPLETED and pushed to production
  - SPRINT_REGISTRY.md row updated to COMPLETED and pushed to production
- stop_only_for:
  - missing credentials/access
  - destructive approval requiring explicit operator consent
  - `_send_message_to_space_internal` does NOT accept `spaces/XXXX` format (present options)
- continue_without_pause_through:
  - execute -> pr_creation -> deploy -> closeout
- blocker_policy:
  - programmatic -> fix and continue
  - repeated technical failure x3 -> research, then continue
  - business-data/policy -> pause
- signoff_authority: single-owner
- canonical_closeout_artifacts:
  - `docs/plans/2026-03-23-sprint-97-commissary-handoff-fix.md` (this plan)
  - `docs/plans/SPRINT_REGISTRY.md`

## Execution Workflow

- Test Python changes: `/local-frappe`
- Deploy changes: `/deploy-frappe`
- Full workflow: `/agent-kickoff`
- E2E testing: `/e2e-test`

## Agent Boot Sequence

1. Read this plan fully.
2. Read `hrms/api/warehouse.py` lines 61-80 (notification function), lines 415-459 (warehouse targets), and line 484 (company validation).
3. Read `hrms/api/google_chat.py` lines 196-270 to confirm `_send_message_to_space_internal` uses `space_name` as Google API resource path AND confirm `send_message_to_space` signature. (AUDIT B-1)
4. Read `hrms/api/erp_sync.py` lines 55-64 to confirm 3PL warehouse name patterns.
5. Read `../bei-tasks/app/dashboard/commissary/transfer/page.tsx` lines 30 (imports), 77-80 (useEffect), 157 (post-submit reset), 288-316 (dialog + dropdown).
6. Read `../bei-tasks/hooks/use-commissary.ts` line 821 to see current `WarehouseReceivingTarget` type. (AUDIT B-2)
7. SelectGroup/SelectLabel/SelectSeparator exports confirmed at `../bei-tasks/components/ui/select.tsx` lines 176-187. No need to re-verify.
8. Execute Phase 1, Phase 2, Phase 3 in order.

## Execution Authority

This sprint is intended for autonomous end-to-end execution.
Do not stop for progress-only updates.
Only pause for items listed in the Autonomous Execution Contract `stop_only_for` section.
