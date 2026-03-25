# Procurement Practical Improvements — Grounded Review

**What this is:** A reality-checked version of the vision doc. Strips away over-design, accounts for what BEI already has, and prioritizes based on industry best practices for a 47-store Philippine QSR chain with a 2-person procurement team.

**What changed from the vision doc:** The Command Center vision was over-designed. BEI already has a comprehensive procurement dashboard with KPIs, pending approvals widget, AP aging chart, PO trend chart, outstanding by supplier chart, upcoming payments list, and quick actions. The problem isn't missing dashboards — it's missing **bulk actions** and **automation to reduce clicks per transaction**.

---

## What BEI Already Has (Don't Rebuild)

| Feature | Status | Where |
|---------|--------|-------|
| Dashboard with 4 KPI cards | Done | /procurement |
| Pending approvals widget (PR, PO, Payment tabs) | Done | /procurement |
| AP Aging pie chart | Done | /procurement |
| Monthly PO Trend chart | Done | /procurement |
| Outstanding by Supplier chart | Done | /procurement |
| Upcoming Payments list (next 30 days) | Done | /procurement |
| Quick Actions (5 buttons) | Done | /procurement |
| OR Follow-up with escalation | Done | /procurement/or-follow-up |
| Approval dialog (modal) per PO | Done | PO list + detail page |
| 4-level payment approval workflow | Done | Payment pages |
| 3-way match variance detection | Done | Invoice detail |
| GR quality inspection dialog | Done | GR detail |
| Status filtering on all list pages | Done | All list pages |
| Contracted price auto-fill on PR form | Done | S104+S107 |
| Auto PO email to supplier on approval | Done | PO approval flow |
| Google Chat notifications for approvals | Done | Automatic |
| Over-delivery protection (5% tolerance) | Done | GR creation |
| Smart tax calculation (VAT/EWT per supplier) | Done | PO creation |
| Supplier performance metrics | Done | Supplier detail |

**Bottom line:** The dashboard is already good. The pages work. The problem is SPEED — too many clicks for high-volume operations.

---

## What's Actually Missing (Industry Standard for This Size)

Based on research: a 47-store QSR with 2 procurement staff should expect 375-750 POs/month (~12-25 POs/person/day). That's only manageable with these features:

### MUST-HAVE #1: Batch PO Approval for Mae

**Industry practice:** Batch approval is standard. Every procurement platform (SAP Ariba, Coupa, NetSuite) has multi-select + approve.

**What to build:**
- Add checkboxes to PO list rows
- When 1+ rows selected, show floating action bar: `[Approve Selected (N)] [Reject Selected]`
- Clicking "Approve Selected" shows a summary modal:
  ```
  Approve 5 POs?
  Total value: P3,031,616
  Suppliers: GLARA, Orangepop, UBE House, National, Jovylyn
  [Cancel] [Approve All 5]
  ```
- Mae clicks once → 5 POs approved

**Why this is #1:** Mae has 41 POs stuck. Every day without this, Luwi can't send POs to suppliers. This is the biggest single bottleneck.

**Effort:** ~8 units (frontend only — backend `approve_po` already works per-PO, just call it in a loop)

---

### MUST-HAVE #2: "Received as Ordered" Quick GR

**Industry practice:** Exception-based receiving is standard in food service. Staff only enters what DOESN'T match. The happy path is one button.

**What to build:**
- On GR new page, after selecting a PO, show all items pre-filled with ordered qty
- Add a prominent button: `[Received All as Ordered]`
- Clicking it = creates GR with all qty matching PO + today's date
- Only use the manual qty fields when something is different
- Still require delivery note upload (photo from phone camera)

**Why this is #2:** ~70% of deliveries match the PO exactly. Each full-form GR takes 3-5 minutes. Quick receive: 30 seconds.

**Effort:** ~6 units (frontend change — add button that auto-submits with PO quantities)

---

### MUST-HAVE #3: PO Duplicate/Copy

**Industry practice:** "Copy to new PO" is standard. Same supplier, same items, adjust quantities.

**What to build:**
- Add "Duplicate" button on PO detail page (next to Edit/Delete)
- Clicking it opens the New PO form pre-filled with:
  - Same supplier
  - Same items + last-used quantities and prices
  - New PO date = today
  - Delivery date = blank (user fills)
- User adjusts quantities, clicks Create

**Why this is #3:** Recurring orders (weekly commissary restock, monthly supplies) are the same items from the same supplier. Re-entering everything from scratch is pure waste.

**Effort:** ~4 units (frontend — pass PO data as query params to new form)

---

### SHOULD-HAVE #4: Blanket POs (Recurring Orders)

**Industry practice:** For QSR, blanket POs (standing orders) are common. "We buy 200kg sago from GLARA every week at P84/kg for Q2 2026." Individual releases against the blanket PO don't need re-approval.

**What to build (simplified version):**
- "Saved Orders" — save a PO as a template with name (e.g., "Weekly Sago")
- "Reorder" button creates a new PO from the template
- Templates show last-used date and average frequency
- NOT full blanket PO management (that's enterprise — overkill for BEI)

**Why:** Reduces the most repetitive POs from 5-minute form fills to 30-second reorders.

**Effort:** ~10 units (new template DocType + frontend)

---

### SHOULD-HAVE #5: Today's Expected Deliveries

**Industry practice:** Morning delivery visibility is a top-6 daily KPI. Every procurement officer checks this first.

**What to build:**
- Add a widget to the existing dashboard (NOT a new page): "Deliveries Expected Today"
- Pull from POs where `delivery_date = today` and status is Approved/Partially Received
- Show: supplier, PO#, item count, expected time (if available)
- Color: green = confirmed, yellow = no confirmation, red = overdue
- Link: click → opens the PO detail or quick GR form

**Why:** Luwi currently has no way to see what's arriving today without scrolling through all POs. At 3-5 deliveries per day, this saves 10-15 minutes of hunting.

**Effort:** ~5 units (dashboard widget + backend query using existing `delivery_date` field)

---

### SHOULD-HAVE #6: Auto-Invoice from GR (Draft)

**Industry practice:** When a GR is created, auto-draft an invoice with PO data pre-filled. User adds invoice number + attaches scan.

**What to build:**
- After GR creation success, show a prompt: "Create invoice for this delivery? [Yes] [Later]"
- If Yes, navigate to Invoice form pre-filled with PO, GR, supplier, items, amounts
- User only enters: invoice number, invoice date, attaches scanned invoice
- NOT auto-verified — still goes through 3-way match

**Why:** Eliminates the navigation step between GR and Invoice. At 5+ GRs/day, saves 15+ minutes.

**Effort:** ~5 units (frontend — redirect with pre-fill params after GR success)

---

### NICE-TO-HAVE #7: Morning Digest via Google Chat

**Industry practice:** Daily procurement digest is standard for teams >2 people.

**What to build:**
- Scheduled Google Chat message to procurement team at 8 AM:
  ```
  Good morning Luwi! Today's procurement summary:
  - 3 deliveries expected (GLARA 10am, UBE 2pm, National 3pm)
  - 5 PRs waiting to be converted to POs
  - 41 POs pending Mae's approval (oldest: 12 days)
  - 2 invoices ready for verification
  - 1 OR overdue 81 days (PAY-2026-00050)
  ```
- Uses existing Google Chat integration (already works for approval notifications)

**Why:** Luwi starts her day knowing exactly what needs attention without opening 6 pages.

**Effort:** ~4 units (scheduled Blip Sentinel job using existing Chat API)

---

## What NOT to Build (Over-Design Alert)

| Vision Doc Idea | Why Skip It |
|-----------------|-------------|
| Full Command Center replacing dashboard | Dashboard already has KPIs, charts, pending approvals. Enhance it, don't replace it. |
| Keyboard shortcuts (Superhuman style) | Luwi uses a mouse. 2-person team doesn't justify the dev cost. Add later if requested. |
| Global command palette (cmdk) | Same — useful for power users, not priority for 2-person team. |
| Bloomberg terminal styling | Over-designed. BEI's existing modern UI is fine. |
| Price Comparison Tool | Good idea but complex (needs price history across suppliers). Defer to Phase 2. |
| Supplier Scorecard page | Already exists on supplier detail. Enhance, don't rebuild. |
| Zero-Touch PO automation | Aspirational. Needs reorder points, demand forecasting, auto-approval rules. 12-18 month horizon. |
| Invoice OCR | High effort (20+ units), external dependency. Defer to Phase 3. |
| Mobile dock receiving | Real need but high effort (15 units). Current desktop works at HQ. Defer unless store managers need it. |
| Auto-payment scheduling | Requires finance approval workflow changes. Defer. |
| Color-coded heatmap system | Existing status badges + color variants work. Don't over-engineer. |

---

## Revised Priority List

### Build Now (This Week) — 23 units total

| # | Feature | Units | Impact |
|---|---------|-------|--------|
| 1 | **Batch PO Approval** (checkboxes + approve selected) | 8 | Unblocks 41 POs immediately |
| 2 | **Quick Receive** ("Received as Ordered" button) | 6 | 70% of GRs become one-click |
| 3 | **PO Duplicate** (copy to new PO) | 4 | Recurring orders go from 5 min → 30 sec |
| 4 | **Today's Deliveries** widget on dashboard | 5 | Morning visibility without page-hopping |

### Build Next (Next 2 Weeks) — 19 units

| # | Feature | Units | Impact |
|---|---------|-------|--------|
| 5 | **Auto-Invoice from GR** (prompt + pre-fill) | 5 | Eliminates GR→Invoice navigation |
| 6 | **Saved Orders / Templates** (reorder center) | 10 | Recurring POs become 30-second reorders |
| 7 | **Morning Digest** via Google Chat | 4 | Start day with full visibility |

### Build Later (Month 2+) — Needs Discussion

| # | Feature | Notes |
|---|---------|-------|
| 8 | Threshold auto-approval (POs < P10K, established supplier) | Needs Mae's buy-in |
| 9 | Delegate approver (backup for Mae) | Needs org decision |
| 10 | Batch actions on ALL list pages (GR, Invoice, Payment) | Extend the PO pattern |
| 11 | Price comparison across suppliers | Needs historical price data model |
| 12 | Store-level requisition catalog | Needs store ordering workflow design |
| 13 | Mobile GR at dock | Needs mobile layout work |

---

## Open Questions (Same as Before, Refined)

1. **Volume check:** How many POs does Luwi actually create per day? The industry benchmark says 12-25/person/day for this size. Is that accurate?

2. **Mae's bottleneck:** Would Mae use a "batch approve" feature, or does she prefer reviewing each PO? Would she accept auto-approval under P10K for established suppliers?

3. **Recurring orders:** What % of POs are repeat orders (same supplier + same items)? If >50%, templates are critical. If <20%, PO duplicate is enough.

4. **Delivery predictability:** Do suppliers confirm delivery dates, or do they just show up? This determines whether the delivery calendar is useful.

5. **Invoice timing:** Do suppliers deliver invoice with goods (same-day), or mail it later? If same-day, combined GR+Invoice flow is high value. If later, less impact.

6. **Cayla's role:** Does Cayla do the same work as Luwi, or different? (e.g., Luwi = POs, Cayla = invoices/payments?)

7. **Store ordering:** Do store managers currently submit PRs, or does Luwi decide what to order for each store? This affects whether store-level requisition catalogs matter.

---

## Evidence Sources

| File | What It Proves |
|------|----------------|
| `output/l3/S116-retest/agent1_pr_po.json` | PR + PO forms work, tax math correct |
| `output/l3/S116-retest/agent2_gr_inv.json` | GR + Invoice work, VAT verified |
| `output/l3/S116-retest/agent3_pay_sup.json` | Payment + Supplier work, D2/D3/D4 fixed |
| `output/l3/S116-retest/agent4_dash_reports.json` | Dashboard KPIs valid, all reports render |
| `output/l3/S116-retest/payment_chain.json` | Full chain PR→PO→GR→Invoice→Pay works |
| `output/l3/S116-retest/FACT_CHECK.md` | Adversarial verification: tests were real |
| `tmp/procurement_best_practices.md` | Industry benchmarks and patterns |
| `tmp/luwi_training_doc.md` | Training guide v2.0 content |
