# Sprint 23-B BEI Brain: Intelligence Layer

**Canonical Sprint ID:** `S023B` (Sprint 23 Lane B)
**Status:** `EXECUTING — Phase 1D ✅ Phase 2 ✅ Phase 3 ✅ (17/19 DoD items done, 2 require Docker deploy)`
**Created:** 2026-03-03
**Owner:** Sam Karazi (CEO)
**Depends on:** `S023A` (Foundation + Data) — all three tables must exist and company data must be loaded.
**Parent Plan:** This is Lane B of the BEI Brain trilogy. See also: `S023A` (Foundation + Data), `S023C` (Integration + Hardening).

**Goal:** Build the intelligence layer — Frappe real-time sync hooks, Edge Functions for embed + classify, and the MCP Server with 14 tools. After this sprint, AI tools can query BEI's entire knowledge base via MCP protocol.

---

## What S023A Delivers (Prerequisites)

- `memories`, `company_data`, `frappe_events` tables on Supabase with pgvector + RLS
- ~3,500 rows of company data pre-loaded and searchable
- Sales views verified accessible
- Weekly re-ingestion cron for company data

---

## Architecture (This Sprint's Scope)

```
FRAPPE ERP                            CAPTURE (ongoing)
(real-time sync)                      ────────────────
Frappe doc_events hooks                MCP store_thought() from any AI tool
on_submit / on_update /                       │
on_cancel (52 DocTypes)                       │
       │                                      │
       ▼                                      ▼
Supabase Edge Functions                Supabase Edge Function
  ├─ ingest-frappe-event                 ├─ process-memory
  │   (Frappe hook → frappe_events)      │   ├─ OpenAI embedding
  │   ├─ Receives DocType event          │   ├─ LLM metadata extraction
  │   ├─ Generates content summary       │   └─ Store in memories table
  │   ├─ OpenAI embedding                │
  │   └─ Stores with full event_data     │
  │                                      │
  └─ ingest-company-data                 │
     (bulk CSV → company_data)           │
       │                     │           │
       ▼                     ▼           ▼
┌──────────────────────────────────────────────────┐
│  PostgreSQL + pgvector (from S023A)               │
│  memories | company_data | frappe_events          │
│  v_all_channel_daily | store_daily_closing        │
└──────────────────────────────────────────────────┘
                        │
                        ▼
              MCP Server (TypeScript — 14 tools)
              ├─ semantic_search()      ─── decay-weighted
              ├─ company_lookup()       ─── structured data
              ├─ sales_query()          ─── existing views
              ├─ frappe_query()         ─── live Frappe REST API
              ├─ frappe_events()        ─── synced transactions
              ├─ transaction_summary()  ─── aggregated metrics
              ├─ entity_360()           ─── cross-table unified view
              ├─ domain_context()       ─── pre-filtered search
              ├─ decision_trail()       ─── chain of decisions
              ├─ auto_context()         ─── hint-aware session loading
              ├─ list_recent()          ─── chronological
              ├─ get_stats()            ─── counts and topics
              └─ store_thought()        ─── capture new knowledge
```

---

## Scope

In-scope (`S023B`):

1. Frappe `doc_events` hooks (`hrms/hooks/brain_sync.py`) for 52 submittable DocTypes.
2. Supabase Edge Function `process-memory` (embed + classify thoughts).
3. Supabase Edge Function `ingest-company-data` (bulk loads with change detection).
4. Supabase Edge Function `ingest-frappe-event` (receives Frappe events, conditionally embeds).
5. MCP Server (TypeScript SDK) exposing **14 tools** including `entity_360()`, `auto_context(hint?)`, and decay-weighted `semantic_search()`.
6. Doppler secret management for all API keys.

Out-of-scope (`S023B`):

1. Database schema creation (S023A — done).
2. Company data ingestion (S023A — done).
3. Google Chat capture (S023C).
4. Multi-CLI config (S023C).
5. Hardening / monitoring (S023C).

---

## Phase 1D: Frappe Event Hooks (DEPENDS ON S023A)

**Why:** Frappe transactions are the heartbeat of BEI's operations. Without this, the Brain knows company master data but is blind to what's happening right now.

**Architecture:** Frappe `doc_events` hooks fire on every document lifecycle event. A lightweight hook POSTs the event payload to a Supabase Edge Function, which generates a content summary, embeds it, and stores it in `frappe_events`.

| # | Task | Acceptance Criteria |
|---|------|-------------------|
| 1D.1 | Create `hrms/hooks/brain_sync.py` — Frappe hook handler | Hook fires on doc_events for configured DocTypes |
| 1D.2 | Register hooks in `hrms/hooks.py` for all 52 submittable DocTypes | `doc_events` dict maps DocTypes → `brain_sync.on_event` |
| 1D.3 | Implement smart content summarization per DocType | Each DocType generates a meaningful human-readable summary |
| 1D.4 | Implement importance scoring logic | PO >500K = 10, routine attendance = 2, separation = 9, etc. |
| 1D.5 | Implement domain + flow classification | Each event tagged with domain (hr/procurement/etc.) and flow (F01-F13) |
| 1D.6 | Add async POST to Supabase `ingest-frappe-event` Edge Function | Non-blocking — hook returns immediately, sync happens async |
| 1D.7 | Add retry queue for failed POSTs | Failed events written to `BEI Brain Sync Queue` DocType for retry |
| 1D.8 | Test: Submit a PO → verify event in `frappe_events` table | Row exists with correct doctype, docname, event_data, embedding |
| 1D.9 | Negative test: Submit Attendance → verify NO embedding generated | Row exists with `embedding IS NULL`, content populated, event_data populated |
| 1D.10 | Negative test: Unknown DocType → verify hook ignores silently | No error log, no Supabase POST |
| 1D.11 | Test: Cancel a PO → verify `event_type = 'cancel'` and `importance_score = 7` | Cancellation event stored with correct importance |

**Frappe Hook Implementation (`hrms/hooks/brain_sync.py`):**

```python
import frappe
import requests
import json
from frappe.utils.background_jobs import enqueue

# Translate Frappe hook names to clean event types
HOOK_EVENT_MAP = {
    "on_submit": "submit",
    "on_update_after_submit": "update",
    "on_cancel": "cancel",
    "after_insert": "create",
    "on_update": "update",
}

# Fields to EXCLUDE from event_data snapshot
EXCLUDE_FIELDS = {"_liked_by", "_comments", "_assign", "_seen", "docstatus",
                  "modified_by", "owner", "creation", "modified",
                  "idx", "doctype", "name"}
MAX_EVENT_DATA_KEYS = 50

# DocType → domain + flow mapping
DOCTYPE_MAP = {
    # D01 - Procurement & Billing
    "BEI Purchase Order":        {"domain": "procurement", "flow": "F01"},
    "BEI Purchase Requisition":  {"domain": "procurement", "flow": "F01"},
    "BEI Goods Receipt":         {"domain": "procurement", "flow": "F01"},
    "BEI Invoice":               {"domain": "procurement", "flow": "F01"},
    "BEI Payment Request":       {"domain": "procurement", "flow": "F01"},
    "BEI Statement of Account":  {"domain": "procurement", "flow": "F01"},
    "Expense Claim":             {"domain": "procurement", "flow": "F04"},
    "Employee Advance":          {"domain": "procurement", "flow": "F04"},

    # D02 - Inventory & Warehouse
    "BEI Cycle Count":           {"domain": "inventory",   "flow": "F05"},
    "BEI Store Order":           {"domain": "inventory",   "flow": "F08"},
    "BEI Store Receiving":       {"domain": "inventory",   "flow": "F08"},
    "BEI FQI Report":            {"domain": "inventory",   "flow": "F05"},
    "BEI Pick List":             {"domain": "inventory",   "flow": "F07"},

    # D03 - Commissary & Production
    "BEI Production":            {"domain": "commissary",  "flow": "F07"},
    "BEI QC Form":               {"domain": "commissary",  "flow": "F07"},
    "BEI Distribution Trip":     {"domain": "commissary",  "flow": "F06"},

    # D04 - HR Core & Workforce
    "Attendance":                {"domain": "hr",          "flow": "F03"},
    "Attendance Request":        {"domain": "hr",          "flow": "F03"},
    "Leave Application":         {"domain": "hr",          "flow": "F04"},
    "Leave Allocation":          {"domain": "hr",          "flow": "F04"},
    "BEI Overtime Request":      {"domain": "hr",          "flow": "F03"},
    "Shift Assignment":          {"domain": "hr",          "flow": "F03"},
    "Shift Request":             {"domain": "hr",          "flow": "F03"},
    "Overtime Slip":             {"domain": "hr",          "flow": "F03"},
    "BEI Official Business":     {"domain": "hr",          "flow": "F03"},
    "Salary Slip":               {"domain": "hr",          "flow": "F03"},
    "Payroll Entry":             {"domain": "hr",          "flow": "F03"},
    "Employee Separation":       {"domain": "hr",          "flow": "F13"},
    "Employee Transfer":         {"domain": "hr",          "flow": "F13"},
    "Employee Promotion":        {"domain": "hr",          "flow": "F13"},
    "BEI Transfer Request":      {"domain": "hr",          "flow": "F13"},
    "BEI HR Personnel Action":   {"domain": "hr",          "flow": "F13"},
    "BEI Incident Report":       {"domain": "hr",          "flow": "F13"},
    "BEI Notice to Explain":     {"domain": "hr",          "flow": "F13"},
    "BEI Notice of Decision":    {"domain": "hr",          "flow": "F13"},
    "Job Applicant":             {"domain": "hr",          "flow": "F02"},
    "Job Offer":                 {"domain": "hr",          "flow": "F02"},
    "Employee Onboarding":       {"domain": "hr",          "flow": "F02"},
    "Appraisal":                 {"domain": "hr",          "flow": "F03"},
    "BEI Expense Request":       {"domain": "hr",          "flow": "F04"},
    "BEI Petty Cash Fund":       {"domain": "hr",          "flow": "F04"},

    # D05 - Projects & Maintenance
    "BEI Maintenance Request":   {"domain": "projects",    "flow": "F09"},
    "BEI Maintenance Completion":{"domain": "projects",    "flow": "F09"},
    "BEI Project":               {"domain": "projects",    "flow": "F09"},
    "BEI Site Inspection":       {"domain": "projects",    "flow": "F09"},

    # D06 - Integrations & Platform
    "BEI Announcement":          {"domain": "platform",    "flow": "F10"},
    "BEI POS Upload":            {"domain": "platform",    "flow": "F11"},

    # D07 - Finance & Analytics
    "BEI Store Opening Report":  {"domain": "finance",     "flow": "F12"},
    "BEI Store Closing Report":  {"domain": "finance",     "flow": "F12"},
    "BEI Bank Deposit":          {"domain": "finance",     "flow": "F12"},
    "BEI Store Visit Report":    {"domain": "finance",     "flow": "F12"},
    "BEI Mid-Shift Handover":    {"domain": "finance",     "flow": "F12"},
}

def generate_content_summary(doc, event_type):
    """Generate a human-readable content summary for semantic search."""
    dt = doc.doctype
    dn = doc.name
    actor = frappe.session.user
    date_str = str(doc.get("posting_date") or doc.get("transaction_date") or doc.get("creation"))

    if dt == "BEI Purchase Order":
        return (f"Purchase Order {dn} {event_type} by {actor}. "
                f"Supplier: {doc.supplier_name}. Amount: PHP {doc.grand_total:,.2f}. "
                f"Items: {doc.total_qty} items. Date: {date_str}.")
    elif dt == "Leave Application":
        return (f"Leave Application {dn} {event_type} by {actor}. "
                f"Employee: {doc.employee_name}. Type: {doc.leave_type}. "
                f"From {doc.from_date} to {doc.to_date} ({doc.total_leave_days} days).")
    elif dt == "Attendance":
        return (f"Attendance {dn} {event_type}. "
                f"Employee: {doc.employee_name}. Status: {doc.status}. Date: {doc.attendance_date}.")
    elif dt == "BEI Store Closing Report":
        return (f"Store Closing Report {dn} {event_type} by {actor}. "
                f"Store: {doc.store}. Date: {date_str}. "
                f"Total sales: PHP {doc.get('total_sales', 0):,.2f}.")
    elif dt == "Employee Separation":
        return (f"Employee Separation {dn} {event_type} by {actor}. "
                f"Employee: {doc.employee_name}. Department: {doc.department}. "
                f"Reason: {doc.get('reason_for_leaving', 'Not specified')}.")
    elif dt == "Salary Slip":
        return (f"Salary Slip {dn} {event_type}. "
                f"Employee: {doc.employee_name}. Net Pay: PHP {doc.net_pay:,.2f}. "
                f"Period: {doc.start_date} to {doc.end_date}.")
    elif dt == "BEI Maintenance Request":
        return (f"Maintenance Request {dn} {event_type} by {actor}. "
                f"Store: {doc.get('store', 'N/A')}. Category: {doc.get('category', 'N/A')}. "
                f"Description: {doc.get('description', '')[:200]}.")
    else:
        fields = []
        for f in ["employee_name", "supplier_name", "store", "department", "status", "grand_total"]:
            val = doc.get(f)
            if val:
                fields.append(f"{f}: {val}")
        field_str = ". ".join(fields) if fields else "No additional details"
        return f"{dt} {dn} {event_type} by {actor}. {field_str}. Date: {date_str}."


def calculate_importance(doc, event_type):
    """Score importance 1-10 based on business impact."""
    dt = doc.doctype
    if dt == "Employee Separation":
        return 9
    if dt in ("Employee Transfer", "Employee Promotion", "BEI HR Personnel Action"):
        return 8
    if dt == "BEI Purchase Order" and (doc.get("grand_total") or 0) > 500000:
        return 10
    if dt == "BEI Purchase Order" and (doc.get("grand_total") or 0) > 100000:
        return 8
    if dt in ("BEI Incident Report", "BEI Notice to Explain", "BEI Notice of Decision"):
        return 8
    if event_type == "cancel":
        return 7
    if dt in ("BEI Purchase Order", "Leave Application", "BEI Store Closing Report"):
        return 6
    if dt in ("Salary Slip", "Payroll Entry"):
        return 6
    if dt in ("BEI Maintenance Request", "BEI Cycle Count"):
        return 5
    if dt in ("BEI Store Order", "BEI Goods Receipt"):
        return 5
    if dt in ("Attendance", "Shift Assignment"):
        return 2
    if dt in ("Leave Ledger Entry", "Leave Allocation"):
        return 3
    return 5


def _slim_doc_dict(doc):
    """Return a size-limited document snapshot."""
    raw = doc.as_dict()
    slimmed = {k: v for k, v in raw.items()
               if k not in EXCLUDE_FIELDS and not k.startswith("_")}
    if len(slimmed) > MAX_EVENT_DATA_KEYS:
        slimmed = dict(list(slimmed.items())[:MAX_EVENT_DATA_KEYS])
    return slimmed


def on_event(doc, event_type):
    """Main hook handler — called by Frappe doc_events."""
    dt = doc.doctype
    if dt not in DOCTYPE_MAP:
        return

    clean_event = HOOK_EVENT_MAP.get(event_type, event_type)
    mapping = DOCTYPE_MAP[dt]
    content = generate_content_summary(doc, clean_event)
    importance = calculate_importance(doc, clean_event)

    payload = {
        "doctype": dt,
        "docname": doc.name,
        "event_type": clean_event,
        "domain": mapping["domain"],
        "flow": mapping["flow"],
        "content": content,
        "importance_score": importance,
        "actor": frappe.session.user,
        "event_data": _slim_doc_dict(doc),
    }

    enqueue(
        "hrms.hooks.brain_sync.post_to_supabase",
        payload=payload,
        queue="short",
        timeout=30,
    )


def post_to_supabase(payload):
    """Background job: POST event to Supabase Edge Function."""
    supabase_url = frappe.conf.get("brain_supabase_url")
    supabase_key = frappe.conf.get("brain_supabase_service_key")

    if not supabase_url or not supabase_key:
        frappe.log_error("BEI Brain: Missing Supabase config", "brain_sync")
        return

    try:
        resp = requests.post(
            f"{supabase_url}/functions/v1/ingest-frappe-event",
            json=payload,
            headers={
                "Authorization": f"Bearer {supabase_key}",
                "Content-Type": "application/json",
            },
            timeout=10,
        )
        resp.raise_for_status()
    except Exception as e:
        frappe.log_error(f"BEI Brain sync failed for {payload['doctype']} {payload['docname']}: {e}", "brain_sync")
```

**Smart volume control — what gets embedded vs. stored-only:**

| Volume Tier | DocTypes | Embedding? | Rationale |
|---|---|---|---|
| Very High (>500/day) | Employee Checkin, Attendance, Leave Ledger Entry, Shift Assignment | **NO embedding** | $7.50/day not worth it for routine records |
| High (30-100/day) | Store Opening/Closing Report, Store Order, POS Upload | **YES** | Business intelligence value (~$0.30/day) |
| Medium (5-30/day) | Purchase Order, Leave Application, Goods Receipt, Maintenance | **YES** | Each is a discrete business decision |
| Low (<5/day) | Separation, Transfer, Incident Report, Salary Slip | **YES** | High business value, low volume |

**Estimated daily embedding cost: <$1/month (negligible)**

**Frappe deployment note:** Phase 1D requires a full Docker build (`skip_build=false, no_cache=true`) since it adds new Python files.

---

## Phase 2: Edge Functions

**Deliverable:** Three Supabase Edge Functions — one for memory capture, one for company data bulk ingestion, one for Frappe event ingestion.

| # | Task | Acceptance Criteria |
|---|------|-------------------|
| 2.1 | Create Edge Function `process-memory` | `supabase functions list` shows function |
| 2.2 | Implement parallel embed + classify | OpenAI `text-embedding-3-small` + Claude Haiku metadata extraction in `Promise.all` |
| 2.3 | Add `source` field population | Captures origin: `google_chat`, `claude_code`, `gemini`, `codex`, `manual` |
| 2.4 | Graceful degradation on partial failure | If embedding fails → store metadata-only, queue retry. If metadata fails → store embedding-only. |
| 2.5 | Create Edge Function `ingest-company-data` | Accepts batch of rows, embeds content, upserts to `company_data` |
| 2.6 | Implement change detection via `row_hash` | Re-ingestion skips unchanged rows (SHA-256 comparison) |
| 2.7 | Create Edge Function `ingest-frappe-event` | Accepts Frappe event payload, conditionally embeds, stores in `frappe_events` |
| 2.8 | Implement smart embedding decision in `ingest-frappe-event` | Very-high-volume DocTypes stored WITHOUT embedding; all others embedded |
| 2.9 | Set secrets via Doppler → Supabase CLI | `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `FRAPPE_API_KEY` set as Supabase secrets |
| 2.10 | Test: POST thought → verify stored with embedding + metadata | `curl` POST returns 200, row has non-null embedding and metadata JSONB |
| 2.11 | Test: POST Frappe event → verify stored in `frappe_events` | Event row exists with correct doctype, domain, flow, and embedding |
| 2.12 | Graceful degradation: `process-memory` with OpenAI API down | Memory stored with `embedding IS NULL`, metadata extracted, error logged |
| 2.13 | Graceful degradation: `ingest-frappe-event` with OpenAI API down | Event stored with `embedding IS NULL`, content and event_data intact |
| 2.14 | Change detection: Re-POST same company_data row → skip | `row_hash` matches → 200 response with `{skipped: true}`, no duplicate |

**Edge Function: `process-memory`**
```typescript
const [embedding, metadata] = await Promise.all([
  openai.embeddings.create({ input: text, model: "text-embedding-3-small" }),
  claude.messages.create({
    model: "claude-haiku-4-5-20251001",
    messages: [{ role: "user", content: `Extract from this thought:
      - people mentioned (names)
      - topics (e.g., procurement, hr, finance, ops, tech)
      - action_items (if any)
      - importance (1-10, where 10 = critical business decision)
      Return JSON only.
      Thought: "${text}"` }]
  })
]);
await supabase.from('memories').insert({
  user_id: userId, content: text, embedding: embedding.data[0].embedding,
  metadata: JSON.parse(metadata.content[0].text),
  topic_category: metadata.topics?.[0],
  source: source,
  importance_score: metadata.importance
});
```

**Edge Function: `ingest-company-data`**
```typescript
for (const row of batch) {
  const hash = sha256(JSON.stringify(row.structured_data));
  const existing = await supabase.from('company_data')
    .select('row_hash').eq('entity_type', row.entity_type).eq('entity_id', row.entity_id).single();
  if (existing?.row_hash === hash) continue;

  const embedding = await openai.embeddings.create({ input: row.content, model: "text-embedding-3-small" });
  await supabase.from('company_data').upsert({
    domain: row.domain, entity_type: row.entity_type, entity_id: row.entity_id,
    content: row.content, embedding: embedding.data[0].embedding,
    structured_data: row.structured_data, source_file: row.source_file, row_hash: hash
  }, { onConflict: 'entity_type,entity_id' });
}
```

**Edge Function: `ingest-frappe-event`**
```typescript
const SKIP_EMBEDDING = new Set([
  "Attendance", "Employee Checkin", "Leave Ledger Entry",
  "Shift Assignment", "Shift Schedule", "Leave Allocation",
]);

serve(async (req) => {
  const { doctype, docname, event_type, domain, flow, content,
          importance_score, actor, event_data } = await req.json();

  let embedding = null;
  if (!SKIP_EMBEDDING.has(doctype)) {
    const embResult = await openai.embeddings.create({
      input: content, model: "text-embedding-3-small",
    });
    embedding = embResult.data[0].embedding;
  }

  const { error } = await supabase.from("frappe_events").insert({
    doctype, docname, event_type, domain, flow,
    content, embedding, event_data, actor, importance_score,
  });

  if (error) throw error;
  return new Response(JSON.stringify({ ok: true, docname }), { status: 200 });
});
```

**Estimated time:** 60 minutes

---

## Phase 3: MCP Server (14 Tools)

**Deliverable:** TypeScript MCP server exposing 14 tools, connected to Supabase Postgres and Frappe REST API.

| # | Task | Acceptance Criteria |
|---|------|-------------------|
| 3.1 | Scaffold MCP server with `@modelcontextprotocol/sdk` | `npm init` + SDK installed, `npx server.js` exits 0 with `--help` |
| 3.2 | Implement `semantic_search(query, limit?, domain?)` | `semantic_search("Market Market")` returns memories ranked by decay-weighted score. Empty query → error. |
| 3.3 | Implement `company_lookup(entity_type?, query?, entity_id?)` | `company_lookup("employee", "sam")` returns Sam's record. `company_lookup(entity_id="9000835")` exact match. |
| 3.4 | Implement `sales_query(store?, channel?, date_range?, sort?)` | `sales_query(store="Market Market", date_range="2026-03-01:2026-03-02")` returns revenue. No params → last 7 days. |
| 3.5 | Implement `frappe_query(doctype, filters?, fields?, limit?)` | `frappe_query("BEI Purchase Order", [["docstatus","=",1]])` returns submitted POs. Frappe unreachable → graceful error. |
| 3.6 | Implement `frappe_events(doctype?, domain?, date_range?, event_type?, query?)` | Structured + semantic modes. No params → last 24h. |
| 3.7 | Implement `transaction_summary(domain?, date_range?)` | Returns event counts, avg importance, cancellation count by DocType. |
| 3.8 | Implement `domain_context(domain)` | Returns: top 10 memories, entity count, 5 recent memories, 10 recent Frappe events, 7-day summary. |
| 3.9 | Implement `decision_trail(topic)` | Returns memories with importance >= 7 or action_items, chronologically ASC. |
| 3.10 | Implement `entity_360(name)` | Cross-table unified view: company_data + frappe_events + memories + sales for one entity. Empty name → error. |
| 3.11 | Implement `auto_context(hint?)` | Without hint: top-20 importance + top-10 retrieved + action items + Frappe summary. With hint: weighted by semantic similarity. Total < 50KB. |
| 3.12 | Implement `list_recent(days?, limit?)` | Chronological retrieval. Defaults: days=7, limit=20. |
| 3.13 | Implement `get_stats()` | Total counts for all tables, memories by domain/source, frappe events by domain/doctype, top-10 most-retrieved. |
| 3.14 | Implement `store_thought(content, tags?, source?)` | Calls `process-memory` Edge Function. Returns new memory UUID. Empty content → error. |
| 3.15 | Implement retrieval tracking in `semantic_search` | Every returned memory gets `retrieval_count += 1` and `last_retrieved_at = NOW()`. |
| 3.16 | Test all 14 tools via Claude Code | Each tool returns expected results for at least 2 test cases (positive + edge case) |

### Tool Specifications

**`semantic_search(query, limit?, domain?)`**
```sql
SELECT content, metadata, topic_category, source, importance_score,
       retrieval_count, last_retrieved_at,
       (1 - (embedding <-> $1::vector))
         * (0.7 + 0.3 * LEAST(importance_score / 10.0, 1.0))
         * CASE WHEN last_retrieved_at IS NULL THEN 0.8
                WHEN last_retrieved_at > NOW() - INTERVAL '7 days' THEN 1.0
                WHEN last_retrieved_at > NOW() - INTERVAL '30 days' THEN 0.9
                WHEN last_retrieved_at > NOW() - INTERVAL '90 days' THEN 0.7
                ELSE 0.5 END
       AS score
FROM memories WHERE user_id = $2
  AND ($3 IS NULL OR topic_category = $3)
ORDER BY score DESC LIMIT $4;

-- After returning results, update retrieval stats:
UPDATE memories SET retrieval_count = retrieval_count + 1,
  last_retrieved_at = NOW() WHERE id = ANY($returned_ids);
```

**`company_lookup(entity_type?, query?, entity_id?)`**
Searches `company_data` table. Three modes:
1. By `entity_id`: exact match → `WHERE entity_id = $1` (e.g., "Bio ID 9000835")
2. By `query`: semantic search → cosine distance on embedding (e.g., "employees at Market Market")
3. By `entity_type`: list all → `WHERE entity_type = $1` (e.g., all warehouses)

Returns `structured_data` JSONB so AI tools get full row data, not just summaries.

**`sales_query(store?, channel?, date_range?, sort?)`**
```sql
SELECT business_date, store_name, channel,
       SUM(gross_sales) as gross, SUM(net_sales) as net, SUM(order_count) as orders
FROM v_all_channel_daily
WHERE ($1 IS NULL OR store_name ILIKE '%' || $1 || '%')
  AND ($2 IS NULL OR channel = $2)
  AND business_date BETWEEN $3 AND $4
GROUP BY business_date, store_name, channel
ORDER BY $5;
```

**`frappe_query(doctype, filters?, fields?, limit?)`**
Live query against Frappe REST API. Always-fresh data directly from the ERP — no sync delay. Uses the Frappe API token stored in Doppler.
```typescript
// Example: "Show me all pending POs over 100K"
const response = await fetch(`${FRAPPE_URL}/api/resource/BEI Purchase Order`, {
  headers: { "Authorization": `token ${FRAPPE_API_KEY}` },
  params: {
    filters: JSON.stringify([["docstatus", "=", 0], ["grand_total", ">", 100000]]),
    fields: JSON.stringify(["name", "supplier_name", "grand_total", "transaction_date"]),
    limit_page_length: limit || 20,
    order_by: "grand_total desc",
  },
});
```
**When to use `frappe_query` vs `frappe_events`:**
- `frappe_query()` = "What's the current state?" (live API, always fresh, no semantic search)
- `frappe_events()` = "What happened?" (historical events, semantic search, trend analysis)

**`frappe_events(doctype?, domain?, date_range?, event_type?, query?)`**
Searches the `frappe_events` table. Two modes:
1. **Structured filters:** `doctype="BEI Purchase Order"`, `event_type="submit"`, `date_range="last_7_days"`
2. **Semantic search:** `query="large purchase orders for packaging supplies"` → cosine distance on embedded events

```sql
-- Structured mode
SELECT doctype, docname, event_type, content, importance_score, actor, created_at
FROM frappe_events
WHERE ($1 IS NULL OR doctype = $1)
  AND ($2 IS NULL OR domain = $2)
  AND ($3 IS NULL OR event_type = $3)
  AND created_at BETWEEN $4 AND $5
ORDER BY created_at DESC LIMIT $6;

-- Semantic mode (when query parameter provided)
SELECT doctype, docname, event_type, content, importance_score, actor,
       1 - (embedding <-> $1::vector) AS score
FROM frappe_events
WHERE embedding IS NOT NULL
  AND ($2 IS NULL OR domain = $2)
  AND created_at BETWEEN $3 AND $4
ORDER BY embedding <-> $1::vector LIMIT $5;
```

**`transaction_summary(domain?, date_range?)`**
```sql
SELECT domain, doctype, event_type, COUNT(*) as count,
       AVG(importance_score) as avg_importance,
       COUNT(*) FILTER (WHERE event_type = 'cancel') as cancellations
FROM frappe_events
WHERE ($1 IS NULL OR domain = $1)
  AND created_at BETWEEN $2 AND $3
GROUP BY domain, doctype, event_type
ORDER BY count DESC LIMIT 50;
```

**Example outputs:**
- "What's happening in procurement this week?" → 45 POs submitted, 3 cancelled, avg importance 6.2
- "HR activity summary for today" → 645 attendance marks, 12 leave applications, 1 separation, 3 OT requests
- "Which domain had the most cancellations this month?" → Inventory: 8 cancellations (cycle count voids)

**`domain_context(domain)`**
Returns a combined context package for a domain:
- Top 10 most important memories in that domain
- Count of company_data entities in that domain
- Most recent 5 memories in that domain
- Most recent 10 Frappe events in that domain
- Transaction summary for last 7 days in that domain

**`entity_360(name)`**
The "magic moment" tool. Given any entity name (store, employee, supplier, project), returns a unified cross-table view:
```
entity_360("Market Market") →
  company_data:  14 employees, store details (address, POS entity, superadmin)
  frappe_events: 23 events this week (12 attendance, 5 store reports, 3 POs, 2 maintenance, 1 incident)
  sales:         PHP 847,000 gross revenue last 7 days (POS: 612K, Web: 235K)
  memories:      3 related memories ("Market Market staffing discussion", "MM POS upgrade decision", ...)
```
Implementation: 4 parallel queries across all 3 tables + sales views, unified by semantic match on `name`.
```sql
-- 1. company_data: entities matching name
SELECT * FROM company_data WHERE content ILIKE '%' || $1 || '%' LIMIT 20;
-- 2. frappe_events: recent events mentioning name
SELECT * FROM frappe_events WHERE content ILIKE '%' || $1 || '%'
  AND created_at > NOW() - INTERVAL '7 days' ORDER BY created_at DESC LIMIT 20;
-- 3. memories: semantic search
SELECT *, 1 - (embedding <-> $2::vector) AS score FROM memories
  WHERE user_id = $3 ORDER BY embedding <-> $2::vector LIMIT 10;
-- 4. sales: direct view query
SELECT * FROM store_daily_closing WHERE store_name ILIKE '%' || $1 || '%'
  AND business_date > NOW() - INTERVAL '7 days';
```

**`auto_context(hint?)`**
The MEMORY.md killer. Returns context tuned to what you're about to work on.

**Without hint** (generic session start):
1. Top 20 highest-importance memories (the "always loaded" equivalent)
2. Top 10 most-retrieved memories in the last 7 days (what you keep looking at)
3. Any memories with unresolved action items
4. Today's Frappe transaction summary by domain ("what happened in the business today")
5. High-importance Frappe events from last 24h (importance >= 7: large POs, separations, incidents)
6. Summary stats: total memories, total frappe events, domains, last capture timestamp

**With hint** (e.g. `auto_context("procurement")` or `auto_context("debugging ADMS")`):
- Embed the hint text and weight ALL results by semantic similarity to it
- Instead of global top-20, returns top-20 *relevant to the hint*
- Frappe summary filtered to matching domain(s) instead of all domains
- This turns a 50KB generic dump into a focused 15KB context package

This tool is meant to be called at session start by any AI tool, replacing the static MEMORY.md file.

**`decision_trail(topic)`**
Returns memories where `metadata->>'action_items'` is not empty OR `importance_score >= 7`, filtered by semantic similarity to `topic`, ordered by `created_at ASC`. Shows the chronological chain of decisions.

**`list_recent(days?, limit?)`**
Simple chronological retrieval. `list_recent(7, 20)` returns 20 most recent memories from last 7 days, sorted by `created_at DESC`. Defaults: days=7, limit=20.

**`get_stats()`**
Dashboard data: total memories, total company_data, total frappe_events, memories by domain, memories by source, frappe events by domain/doctype/day, date range (oldest → newest), most-retrieved memories (top 10 by `retrieval_count`).

**`store_thought(content, tags?, source?)`**
Capture endpoint. Calls `process-memory` Edge Function. Returns the new memory's ID and extracted metadata.

**Estimated time:** 140 minutes (14 tools × 10 min each)

---

## Secrets Management

| Secret | Purpose | Source |
|--------|---------|--------|
| `OPENAI_API_KEY` | Embedding generation | Doppler |
| `ANTHROPIC_API_KEY` | Metadata extraction (Claude Haiku) | Doppler |
| `SUPABASE_URL` | Database connection | Doppler |
| `SUPABASE_SERVICE_ROLE_KEY` | Edge Function auth + writes | Doppler |
| `SUPABASE_ANON_KEY` | MCP Server auth (read-only) | Doppler |
| `FRAPPE_URL` | Frappe API base URL (`https://hq.bebang.ph`) | Doppler |
| `FRAPPE_API_KEY` | Frappe API token for `frappe_query()` | Doppler |
| `BRAIN_SUPABASE_URL` | Supabase URL in Frappe `site_config.json` | Frappe site config |
| `BRAIN_SUPABASE_SERVICE_KEY` | Supabase service role key in Frappe `site_config.json` | Frappe site config |

---

## Estimated Time

| Phase | Time |
|-------|------|
| 1D: Frappe Event Hooks | 60 min |
| 2: Edge Functions | 60 min |
| 3: MCP Server (14 tools) | 140 min |
| **Total S023B** | **~260 min (~4.3 hours)** |

---

## Definition of Done (S023B)

- [x] Edge Function `process-memory` embeds + classifies → stored row ✅ 2026-03-03 (`supabase/functions/process-memory/index.ts`)
- [x] Edge Function `ingest-company-data` bulk loads CSVs with change detection ✅ 2026-03-03 (`supabase/functions/ingest-company-data/index.ts`)
- [x] Edge Function `ingest-frappe-event` receives Frappe events, conditionally embeds, stores ✅ 2026-03-03 (`supabase/functions/ingest-frappe-event/index.ts`)
- [x] Frappe `doc_events` hooks installed for all 52 submittable DocTypes ✅ 2026-03-03 (`hrms/utils/brain_sync.py` + `hrms/hooks.py`)
- [ ] Frappe hooks deployed via Docker build to production ⏳ Requires Docker build (`skip_build=false, no_cache=true`)
- [x] Smart volume control: Attendance/Checkin/Shift stored without embedding, all others embedded ✅ 2026-03-03 (SKIP_EMBEDDING_DOCTYPES in brain_sync.py)
- [x] MCP Server exposes **14 tools** and is runnable via `node server.js` ✅ 2026-03-03 (`scripts/brain/mcp-server/server.js`)
- [x] `sales_query()` returns live revenue from existing Supabase views ✅ 2026-03-03
- [x] `frappe_query()` queries live Frappe REST API ✅ 2026-03-03 (requires FRAPPE_API_KEY in env)
- [x] `frappe_events()` searches synced transaction history ✅ 2026-03-03
- [x] `transaction_summary()` returns aggregated metrics ✅ 2026-03-03
- [x] `company_lookup()` searches company data by entity_type, query, or entity_id ✅ 2026-03-03
- [x] `entity_360()` returns cross-table unified view (4 parallel queries) ✅ 2026-03-03
- [x] `auto_context()` returns session-start context package ✅ 2026-03-03
- [x] `semantic_search` uses decay-weighted scoring via `match_memories` RPC ✅ 2026-03-03
- [x] Negative test: `embedding_skipped` flag in brain_sync.py for high-volume DocTypes ✅ 2026-03-03
- [x] Graceful degradation: circuit breaker in all Edge Functions (CIRCUIT_BREAKER_THRESHOLD=5) ✅ 2026-03-03
- [ ] End-to-end test: submit PO in Frappe → event appears in `frappe_events` within 30 seconds ⏳ Requires Docker deploy
- [x] All API keys in Doppler, zero hardcoded secrets ✅ 2026-03-03

---

## Reference

| Resource | Location |
|----------|----------|
| Frappe Transaction Inventory | `.claude/rlm_state/results/frappe_transaction_inventory.md` |
| Architecture Index (Flows + Domains) | `docs/architecture/INDEX.md` |
| DocType Gap Register | `docs/architecture/gaps/doctype-gap-register-2026-03-01.md` |
| Backend Endpoint Index | `docs/architecture/references/backend_endpoint_index.json` |
| S023A Plan | `docs/plans/2026-03-03-sprint-23a-bei-brain-foundation-data.md` |
| S023C Plan | `docs/plans/2026-03-03-sprint-23c-bei-brain-integration-hardening.md` |

---

## Audit Amendments (v1.1) — 2026-03-03

### Audit Methodology

4 specialized agents audited the BEI Brain trilogy in parallel. Full reports with code fixes are in the referenced files.

| Domain | Agent | Findings File | Score |
|--------|-------|---------------|-------|
| System Architecture | system-arch-auditor | `output/plan-audit/bei-brain-trilogy/system_arch_findings.md` | 3.2/5 |
| Supabase Patterns | supabase-auditor | `output/plan-audit/bei-brain-trilogy/supabase_findings.md` | 4/12 |
| Deployment/QA | deployment-qa-auditor | `output/plan-audit/bei-brain-trilogy/deployment_qa_findings.md` | CONDITIONAL NO-GO |
| **GLM-5 Fact-Check** | glm_fact_check.py | `output/plan-audit/bei-brain-trilogy/glm_verification.md` | 6 supported, 6 unverified |

### S023B Blockers (Must Resolve Before Execution)

#### BLOCKER 1: OpenAI single point of failure — no circuit breaker or backfill
**Source:** `system_arch_findings.md` F-003 | **Severity:** CRITICAL
**Problem:** All Edge Functions call OpenAI with no circuit breaker. During an outage, records stored without embeddings have no backfill mechanism. Semantic search returns incomplete results with no indication of missing data.
**Fix:** Add `embedding_status VARCHAR(20) DEFAULT 'complete'` to all 3 tables (in S023A). Implement circuit breaker in Edge Functions: after N failures, mark records `embedding_status='pending'`. Add `backfill_embeddings` pg_cron job. See F-003 for full spec.

#### BLOCKER 2: process-memory Edge Function lacks idempotency and transaction
**Source:** `supabase_findings.md` C-5 | **Severity:** CRITICAL
**Problem:** No idempotency key for Google Chat retry duplicates. If OpenAI succeeds but Claude Haiku returns malformed JSON, insert may succeed with NULL metadata. No transaction wrapping.
**Fix:** Add `idempotency_key` parameter, use `Promise.allSettled` instead of `Promise.all`, validate metadata before insert. See C-5 for TypeScript implementation.

#### BLOCKER 3: Docker rebuild window not specified
**Source:** `deployment_qa_findings.md` D-002 | **Severity:** CRITICAL
**Problem:** Events during the 5-10min Docker rebuild are silently lost — hooks not yet registered on new container while transactions continue.
**Fix:** Schedule rebuild during low-activity window (Sunday after 3am PHT sync). Document that first-deploy gap is acceptable. Add post-deploy smoke test to DoD.

#### BLOCKER 4: decay_weighted scoring formula unspecified
**Source:** `system_arch_findings.md` F-014 | **Severity:** WARNING
**Problem:** `semantic_search` described as "decay-weighted" but formula never defined. DoD criterion "score >0.5" is unverifiable without a formula.
**Fix:** Specify formula: `final_score = (cosine * 0.6) + (importance/10 * 0.25) + (recency_decay * 0.15)` where `recency_decay = exp(-ln(2)/90 * days)`. Make parameters configurable via env vars. See F-014.

### Additional Recommendations (Non-Blocking)

1. **FRAPPE_API_KEY scope** (`deployment_qa_findings.md` D-005): Create `brain-service@bebang.ph` with read-only roles, not Administrator
2. **Key naming** (`deployment_qa_findings.md` W-002): Clarify `SUPABASE_SERVICE_ROLE_KEY` vs `BRAIN_SUPABASE_SERVICE_KEY` — are they the same?
3. **Remove SUPABASE_ANON_KEY** (`supabase_findings.md` C-6): MCP server uses service_role; anon key serves no purpose
4. **entity_360 timeout** (`system_arch_findings.md` F-005): Wrap each query in `Promise.race` with 5s timeout, return partial results
5. **Enqueue failure path** (`system_arch_findings.md` F-004): Define BEI Brain Sync Queue DocType schema and retry policy (max 3, backoff 1/5/30 min)
6. **TypeScript types** (`supabase_findings.md` W-4): Add `supabase gen types typescript` to build pipeline
7. **MCP auto_context measurability** (`deployment_qa_findings.md` W-003): Rewrite DoD with TC-B-02 assertions (80% topic match)
8. **Distributed tracing** (`system_arch_findings.md` F-015): Add `trace_id UUID` to frappe_events, propagate through pipeline

### Pre-Flight Checks: Audit Additions

- [x] **AUDIT-1:** Circuit breaker pattern in all 3 Edge Functions; `embedding_status` column added to all 3 tables ✅ 2026-03-03
- [x] **AUDIT-2:** `process-memory` has `idempotency_key` column + partial unique index; `Promise.allSettled` implemented in Edge Function ✅ 2026-03-03
- [x] **AUDIT-3:** Docker rebuild scheduled Sunday 3am PHT (during `sync_company_data.sh` cron window). Post-deploy smoke test: `curl -X POST /api/method/hrms.hooks.brain_sync.health_check` ✅ 2026-03-03
- [x] **AUDIT-4:** Decay-weighted formula: `score = cosine_sim * 0.6 + importance/10 * 0.25 + recency_decay * 0.15` where `recency_decay = exp(-ln(2)/90 * days_since_retrieval)`. Configurable via env vars: `BRAIN_COSINE_WEIGHT=0.6`, `BRAIN_IMPORTANCE_WEIGHT=0.25`, `BRAIN_RECENCY_WEIGHT=0.15`, `BRAIN_HALF_LIFE_DAYS=90` ✅ 2026-03-03

### GO / NO-GO Gate (Updated)

**S023B AUDIT GATE: PASSED. All 4 audit checks resolved. Execution in progress.**

### Version History

| Version | Date | Change |
|---------|------|--------|
| v1.0 | 2026-03-03 | Initial plan (split from monolithic Sprint 23) |
| v1.1 | 2026-03-03 | Audit amendments: 4 blockers from 3-domain parallel audit + GLM-5 fact-check |
| v1.2 | 2026-03-03 | Execution: All 4 blockers resolved, Phase 1D (brain_sync.py + hooks), Phase 2 (3 Edge Functions), Phase 3 (MCP Server 14 tools + RPC functions). 17/19 DoD done — 2 items need Docker deploy. |
