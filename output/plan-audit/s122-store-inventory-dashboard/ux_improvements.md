# UX Improvement Recommendations for S122
# Store Inventory Dashboard — my.bebang.ph
# BEI (Bebang Enterprise Inc.) | Philippine QSR Chain | 46+ Stores
# Prepared: 2026-03-25

---

## Context

Store managers handle 80–150 SKUs across DRY, COLD, FROZEN, and CHILLED categories.
Devices: phones (primary) and laptops (secondary).
Route: /dashboard/store-ops/inventory
Backend: Frappe tabBin + ordering demand data.
User population: ~46 store managers, varying tech literacy.

---

## Priority 1: Must-Have for Launch (add to S122)

---

### 1.1 Timestamped Alert Acknowledgement

- **What:** When a critical or low-stock alert surfaces for an SKU, the manager must tap an "I've seen this" button to dismiss it. The acknowledgement is logged with a timestamp and the manager's user ID.
- **Why:** Without a forced acknowledgement, managers can claim they never saw the alert. This is the most common inventory accountability gap in QSR operations. The dismiss gesture must be explicit — scrolling past an alert does NOT count as seen.
- **How:** Add a `stock_alert_acknowledgements` child table in Frappe linked to the store and SKU. The alert badge stays visible (red dot) until the manager taps dismiss. The Area Supervisor's multi-store view shows unacknowledged alerts with age (e.g., "3 hrs unacknowledged").
- **Anti-abuse angle:** Creates an irrefutable audit trail. A manager cannot claim ignorance of a stockout if the log shows the alert was visible for 4 hours with no acknowledgement.

---

### 1.2 Mandatory Count Confirmation Before Order Submission

- **What:** When a manager initiates an order request from the dashboard, the system requires them to confirm the current physical count for each item being ordered before the request can be submitted. The confirmation field is pre-populated with the ERP's on-hand quantity and the manager must edit it if different.
- **Why:** Prevents "phantom ordering" — submitting orders based on system numbers without actually verifying physical stock. Also catches data drift between system counts and shelf reality early.
- **How:** Order request flow inserts a count-verify step. The submitted order captures both the system quantity and the manager-confirmed quantity. Discrepancies greater than 20% are flagged automatically and escalate to the Area Supervisor for review before the order is approved.
- **Anti-abuse angle:** Over-ordering to stockpile requires the manager to lie about physical counts — a falsifiable record. Under-reporting counts to trigger urgent orders is also flagged by the threshold logic.

---

### 1.3 Sticky Critical-Items Strip (Above the Fold, Always Visible)

- **What:** A horizontally scrollable strip of SKU chips pinned to the top of the dashboard (both mobile and desktop) showing only CRITICAL items. Chips are red, show item name and quantity, and cannot be collapsed or hidden. The strip disappears only when all critical items are resolved.
- **Why:** The current plan has a summary strip with counts, but counts alone do not force action. A manager can see "3 Critical" and still scroll to DRY goods without addressing the issue. Named chips make it personal — "Ube Ice Cream: 0 packs" is harder to ignore than the number 3.
- **How:** Query the bottom of the reorder threshold for each SKU at page load and on a 15-minute polling interval. Render chips in the sticky strip. Tapping a chip scrolls the main list to that SKU and expands its detail card.
- **Anti-abuse angle:** The strip is server-rendered from Frappe data, not client-controlled. A manager cannot collapse or dismiss it without the timestamped acknowledgement flow from 1.1.

---

### 1.4 Order Window Countdown With Hard Lock

- **What:** The existing order window banner should display a live countdown timer (HH:MM) to the next order cutoff. When the window closes, the "Submit Order" button is disabled and grayed out — not hidden, so the manager sees they missed it.
- **Why:** "I didn't know the deadline" is a common excuse for missed orders. Visual urgency (countdown) and a visible locked state (disabled button with label "Order window closed — opens [next time]") removes ambiguity and creates accountability.
- **How:** Order window schedule is stored in Frappe as a store config setting. Frontend derives countdown from server time (not device time — device clocks can be manipulated). The disabled state persists until the next window opens.
- **Anti-abuse angle:** Prevents retroactive blame for stockouts caused by a missed order window. The lock state is logged with a server timestamp.

---

### 1.5 Quick Action: "Flag for Physical Count"

- **What:** A single-tap action on any SKU card or table row that marks the item as "pending physical count." The flag is visible to the Area Supervisor in the multi-store view.
- **Why:** When a manager suspects a system count is wrong (common after deliveries), they need a lightweight way to signal it without writing in a chat or calling. This also discourages gaming by normalizing the correction process — if you flag and then don't update, the flag stays visible.
- **How:** Add a boolean `needs_physical_count` field on tabBin. Flagged items get a yellow badge on the card. The Area Supervisor sees flagged items in their multi-store view grouped separately. When a manager submits a corrected count, the flag clears and logs the delta.
- **Anti-abuse angle:** A manager who frequently flags items without following up with a corrected count creates a visible pattern. Area Supervisors can identify chronic flaggers.

---

### 1.6 Last-Submitted Order Summary (Accessible From Dashboard)

- **What:** A persistent "Last Order" panel accessible via a single tap from the dashboard header. Shows: order date, items ordered, quantities, status (pending/confirmed/delivered), and who submitted.
- **Why:** Managers often forget what they ordered 2 days ago, leading to double orders or disputes with suppliers. "Reorder last order" is a common and legitimate need, but it should show what was ordered — not blindly re-submit.
- **How:** Pull from existing order records in Frappe. Display as a simple list. Include a "Reorder this" button that pre-fills the current order form with last order quantities (editable, not auto-submitted).
- **Anti-abuse angle:** The reorder button pre-fills but does not auto-submit — managers must go through the count-confirmation step (1.2) before submitting. Prevents lazy reorders that ignore actual current stock.

---

### 1.7 Smart Default View: "Needs Attention" First

- **What:** The default view on load is NOT all items sorted alphabetically. It is a filtered view called "Needs Attention" that shows only: CRITICAL items, LOW items, and items with a pending flag. All other items are collapsed behind a "Show All Items" toggle.
- **Why:** A list of 100–150 SKUs on a phone screen is paralyzing. Managers will scroll aimlessly. Defaulting to the 10–20 items that actually need action focuses behavior immediately. The full list is always one tap away.
- **How:** Apply the filter server-side at API response level so the initial payload is small (fast load). The "Show All Items" toggle fetches the full list. The last-used view is remembered per user in localStorage so experienced managers can change their default.
- **Anti-abuse angle:** Managers cannot claim they "couldn't find" a critical item when it is the first thing they see on load.

---

### 1.8 Audit Log Tab (Manager-Visible)

- **What:** A tab on the dashboard (or accessible via a "History" link in the header) showing the last 30 days of actions taken by the current manager on this store: orders submitted, counts confirmed, alerts acknowledged, flags raised and resolved.
- **Why:** Transparency is a two-way accountability tool. Managers who can see their own history are less likely to game the system because the log is familiar — not a surprise during a review. It also helps managers track their own patterns.
- **How:** Pull from the audit tables created by 1.1 and 1.2. Render as a simple reverse-chronological list with date, action, and item. No edit capability. Read-only.
- **Anti-abuse angle:** Managers know the log exists and is visible to Area Supervisors. The act of making the log visible to the manager (not just to supervisors) removes the "surveillance" feeling while maintaining accountability.

---

## Priority 2: Should-Have for V2 (separate sprint)

---

### 2.1 Daily Workflow Checkpoint Prompts

- **What:** Three lightweight in-app prompts tied to time of day: Opening Check (store open time), Midshift Check (store midpoint), Closing Count (1 hour before close). Each prompt is a minimal checklist — not a full inventory audit — covering only the top 10 high-velocity SKUs.
- **Why:** Inventory management fails when it is treated as a once-a-day task. Three micro-touchpoints per day catch drift early and build habit. The prompt is non-blocking (a banner, not a modal) but it creates a timestamp record if the manager completes it.
- **How:** Schedule prompt triggers via a server-side cron based on each store's operating hours config. Push a notification badge to the dashboard nav item. The checklist is pre-populated with the high-velocity SKUs identified from demand projection data.
- **Anti-abuse angle:** Completed checklists are logged. A store with frequent stockouts but no completed midshift checks has a documented pattern of neglect.

### 2.2 Week-Over-Week Stock Trend Sparklines

- **What:** Each SKU card (expanded view) shows a 7-day sparkline of stock level alongside actual demand. A "burn rate" indicator shows: at current demand, this stock lasts N days.
- **Why:** Demand projections exist in the current plan but are not tied to visual trend context. A manager who sees the sparkline diving sharply over 3 days understands urgency better than reading a number.
- **How:** Compute from existing demand data in Frappe. Render a minimal SVG sparkline (no charting library needed for this complexity). The "N days remaining" figure comes from the demand projection already in scope.
- **Anti-abuse angle:** Sparklines make gaming obvious — a sudden drop in recorded stock that doesn't match a corresponding spike in sales is visually anomalous and surfaced in the Area Supervisor view.

### 2.3 Store vs. Store Benchmark Panel (Area Supervisor Only)

- **What:** In the Area Supervisor multi-store view, a "Benchmarks" panel compares stores on: stockout frequency (last 30 days), average order accuracy (ordered vs. needed), and alert acknowledgement rate.
- **Why:** Peer comparison is a powerful motivator. Managers who see their store ranked last on stockout frequency respond faster than managers who receive a private correction.
- **How:** Aggregate from audit log and alert data. Render as a simple ranked list (no need for charts). Stores are identified by name, not anonymous.
- **Anti-abuse angle:** Makes chronic gaming (repeated over-ordering, repeated ignored alerts) visible across the organization, not just to the direct supervisor.

### 2.4 Damaged Stock Quick-Report

- **What:** A "Report Damaged" action on each SKU that lets a manager record: quantity damaged, reason (from a dropdown: spoilage, delivery damage, mishandling, theft-suspected, other), and a required photo attachment.
- **Why:** Without a formal damage report channel in the inventory tool, damaged stock is either ignored (inflating apparent losses) or informally handled (no audit trail). The photo requirement prevents fabrication.
- **How:** Creates a Frappe document linked to the SKU and store. Reduces the system stock count by the reported quantity only after Area Supervisor approval. Pending approvals show in both the manager's dashboard and the supervisor's multi-store view.
- **Anti-abuse angle:** Requires photo evidence. Quantity reduction is gated on supervisor approval. Frequent damage reports from a single manager/store are flagged for review.

### 2.5 Print-Friendly Inventory Count Sheet

- **What:** A dedicated print layout (triggered via a "Print Count Sheet" button) that generates a clean, table-formatted page with: SKU name, category, unit, current system quantity, and a blank "Actual Count" column for physical counting.
- **Why:** Many BEI store managers run physical counts on paper before updating the system. A print button that generates a properly formatted sheet (not a browser screenshot of the dashboard) is a genuine time-saver and reduces transcription errors.
- **How:** A separate CSS print stylesheet or a server-rendered PDF endpoint. Includes store name, date, and a signature line at the bottom. The printed sheet references the system count so discrepancies are obvious when the manager updates.
- **Anti-abuse angle:** The printed sheet has a generated timestamp and system count snapshot. A manager who alters the physical count before entry has a documented discrepancy to explain.

### 2.6 Offline Resilience: Read-Cache With Deferred Sync

- **What:** The dashboard caches the last-fetched inventory snapshot in the browser (IndexedDB). When connectivity is lost, the cached view is shown with a "Offline — showing data from [timestamp]" banner. Any actions taken offline (flag, acknowledge alert, log a count) are queued and sync when connectivity returns.
- **Why:** BEI stores can have intermittent connectivity. A manager who cannot load the dashboard does not manage inventory. Offline read access with queued writes ensures the daily workflow is not blocked.
- **How:** Service worker with IndexedDB cache for the inventory API response. Write actions are queued in a pending-sync list. On reconnect, the queue is flushed and conflicts are resolved server-side (last-write-wins for counts, all alerts must be re-acknowledged if they changed while offline).
- **Anti-abuse angle:** Offline-queued actions are stamped with the device's local time AND the server receipt time. A large gap between the two is flagged as suspicious (e.g., manager wrote counts offline hours ago and synced only at shift end).

---

## Priority 3: Nice-to-Have (Backlog)

---

### 3.1 Onboarding / Training Mode

- **What:** A guided overlay activated on first login (or manually via a "Tutorial" link in settings) that walks a new store manager through the five core actions: checking critical items, acknowledging an alert, flagging an item for count, submitting an order request, and reading the last-order summary.
- **Why:** New store managers in a QSR environment turn over frequently. A 5-step guided tutorial embedded in the actual tool is more effective than a printed manual.
- **How:** Simple step overlay highlighting real UI elements (not a separate demo environment). Completion is logged. Area Supervisors can see which managers have completed onboarding.
- **Anti-abuse angle:** Completion log prevents "I don't know how to use it" as an excuse after training is complete.

### 3.2 Saved Custom Views

- **What:** Managers can save a named filter configuration (e.g., "My Cold Chain Items", "Opening Check SKUs") and recall it with one tap from a saved-views strip below the search bar.
- **Why:** High-velocity managers who already know their problem items develop mental shortcuts. Saved views let experienced managers move faster without forcing them through the default "Needs Attention" filter every time.
- **How:** Store view configs (active filters + sort order + visible categories) in localStorage per user. No server storage required for V1 of this feature.
- **Anti-abuse angle:** Saved views do not bypass the sticky critical-items strip (1.3). A manager's saved view can only filter the main list — critical items remain visible regardless.

### 3.3 Badge Count in Sidebar Nav

- **What:** The "Inventory" nav item in my.bebang.ph's sidebar shows a red badge with the count of unacknowledged critical alerts.
- **Why:** Managers who use multiple parts of the app (tasks, approvals, payslip) may not check inventory unprompted. A badge creates passive urgency without requiring a push notification.
- **How:** Fetch unacknowledged alert count on app load and on a polling interval. Use the existing sidebar badge pattern if present in the UI kit.
- **Anti-abuse angle:** The badge count is server-derived and cannot be cleared by the manager except through the acknowledgement flow. Supervisors see the same badge count in the multi-store view.

### 3.4 Supplier Delivery Confirmation Tie-In

- **What:** When a delivery is expected (based on a pending order), the dashboard surfaces a "Confirm Delivery" prompt on the order window. The manager records: quantity received per SKU (vs. quantity ordered), any shortages, and any quality issues. On confirmation, system stock is updated.
- **Why:** The loop between "order submitted" and "stock updated" is currently manual. Delivery confirmation in the same tool closes the loop and prevents stock count drift after deliveries.
- **How:** Requires integration between the order request flow and the stock update. Deferred to backlog because it touches supplier/procurement flows outside S122 scope.
- **Anti-abuse angle:** Receiving quantity is logged separately from what was ordered. A manager who records a full delivery but the supplier's invoice shows a short delivery creates a discrepancy that can be audited.

### 3.5 Exportable Audit Report (Area Supervisor)

- **What:** In addition to the CSV export of current stock, Area Supervisors can export a 30-day audit report per store: all alerts with acknowledgement timestamps, all orders with count-verify records, all flags raised and resolved, all damage reports.
- **Why:** Area Supervisors need evidence when addressing performance issues with store managers. A structured export is more defensible than screenshots of chat conversations.
- **How:** Server-rendered report from the audit log tables. CSV or PDF. Filterable by date range and store.
- **Anti-abuse angle:** The existence of the export option is itself a deterrent. Managers who know their supervisors can pull a full 30-day audit log are less likely to game individual transactions.

---

## Summary Notes for Engineering

1. All audit log writes (alert acknowledgements, count confirmations, flag events) must use server time, not device time.
2. The "Needs Attention" default view filter (1.7) should be computed server-side so it works correctly even when the manager's device has a stale cache.
3. The order count-confirmation step (1.2) is the single highest-leverage anti-abuse control — it should not be simplified or made skippable under any circumstances.
4. Area Supervisor visibility features (multi-store unacknowledged alerts, benchmark panel) should be RBAC-gated to the `Area Supervisor` role in Frappe and mirrored in `bei-tasks/lib/roles.ts`.
5. Print stylesheet (2.5) should be tested on both A4 and short-bond paper sizes — Philippine QSR stores commonly use short bond.
