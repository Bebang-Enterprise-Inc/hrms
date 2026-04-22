# S220 Backend Investigation — Key Finding

**Date:** 2026-04-22 PHT
**Objective:** Find why ARANETA GATEWAY passes approval but FESTIVAL MALL ALABANG fails
**Method:** Direct API submit of fresh orders + live backend probe as test.area

## Result — my DEFECT-11 hypothesis was WRONG

### Both orders look identical at the backend

| Field | ARANETA | FESTIVAL MALL |
|---|---|---|
| Order status | Pending Approval | Pending Approval |
| approval_stage | Pending Area Supervisor | Pending Area Supervisor |
| requires_dual_approval | 1 | 1 |
| edited_lines_count | 3 | 2 |
| Queue entries (recent) | 10 (1 Pending) | 8 (1 Pending) |
| Latest queue: approver | test.area@bebang.ph | test.area@bebang.ph |
| Latest queue: status | Pending | Pending |

### UI filter result (`get_order_review_queue` as test.area)

```
Total orders visible: 2
ARANETA visible: True
FESTIVAL visible: True
```

**Both orders are visible to test.area via the backend UI filter.**

## What this rules out

- ~~`requires_manual_approval=False` leaves orders without queue entries~~ → both have queue entries
- ~~Queue entry not assigned to test.area~~ → both assigned to test.area
- ~~`get_order_review_queue` SQL filter excludes the order~~ → both returned

## What's left

The UI times out waiting for the order text (`getByText(orderId).first()`) to become visible. Backend confirms the order IS in the list returned to test.area. So either:

1. **UI pagination/slicing** — the approval page renders only N rows; FESTIVAL MALL's order might be past the visible slice
2. **UI sorting/filtering** — a client-side filter on the page might hide the order
3. **UI hydration race** — the order IS eventually rendered but after the 30s waitFor
4. **Text match failure** — the order ID text appears differently in DOM (inside a code-block, a tooltip, a different case)

## Next step required: Playwright trace-zip inspection

This is S221 scope. The direct API probe has reached its limit — we know the problem is client-side rendering, not backend. A Playwright trace will show:
- What the UI page looked like at the moment of timeout
- What DOM text was actually present
- Whether the order was off-screen / paginated / filtered out
- Whether a client-side filter is applied by default

## Remaining 7-store DEFECT-11 cluster

Based on this finding, all 7 stores (FESTIVAL MALL, MEGAWIDE PITX, MEGAWORLD VENICE, NAIA T3, ORTIGAS ESTANCIA, ROBINSONS ANTIPOLO, SM STA. ROSA) likely share the same UI-rendering bottleneck. A single fix in how the approval page renders/paginates could unblock all 7.

## Evidence artifacts

- `output/l3/s220/direct_submit_probe.json` — full field-by-field comparison
- `scripts/s220_compare_pass_vs_fail.py` — reusable comparison probe
- `scripts/s220_direct_submit.py` — fresh-order submit probe

## Recommendation

**STOP** test-side iteration of the sweep. The 3 recent iterations (S217/S218/S219) hit 63% plateau because:
- S217 removed Playwright's maxFailures (made the full sweep possible)
- S218/S219 patched the wrong root cause

**Next productive move: inspect Playwright trace-zip** for one failing DEFECT-11 store to find the actual UI rendering bug. That's genuinely S221 scope — not something that can be done here without the trace artifact.
