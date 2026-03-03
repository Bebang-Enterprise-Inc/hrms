# Sprint 23-A BEI Brain: Foundation + Data

**Canonical Sprint ID:** `S023A` (Sprint 23 Lane A)
**Status:** `EXECUTING — Phase 1A ✅ Phase 1B ✅ Phase 1C ✅ (3,924 rows loaded)`
**Created:** 2026-03-03
**Owner:** Sam Karazi (CEO)
**Parent Plan:** This is Lane A of the BEI Brain trilogy. See also: `S023B` (Intelligence Layer), `S023C` (Integration + Hardening).

**Goal:** Create the database foundation and pre-load all BEI company data into Supabase with pgvector, making ~3,500 rows of structured company data semantically searchable. This is the data layer that all downstream sprints depend on.

**Research:** `.claude/rlm_state/OPEN_BRAIN_RESEARCH_SYNTHESIS.md` (6-agent parallel research, 60+ sources)
**Brainstorm:** `.claude/rlm_state/results/brainstorm_sota_research.md` (enterprise SOTA: Mem0, Cognee, Zep patterns)

---

## Why "BEI Brain"

| Problem | Impact | Current Workaround |
|---------|--------|-------------------|
| MEMORY.md at 221 lines, truncated at 200 | Critical lessons lost every session | Manual topic file maintenance (14 files) |
| 40+ progress/context files (50K+ tokens) | 53% accuracy when scanning all files | Index-first pattern (manual discipline) |
| Cross-session knowledge loss | Every new session re-discovers the same facts | Re-reading same docs repeatedly |
| Cross-tool amnesia | Claude Code, Gemini CLI, Codex CLI each start from zero | Copy-paste context between tools |
| No queryable company data | "How many employees at Market Market?" requires CSV grep | Ad-hoc scripts, no semantic layer |
| Sales data locked in Supabase views | AI tools can't query live revenue without custom code | `/sales` skill, manual queries |
| ERP transactions invisible to AI | "How many POs this week?" requires MariaDB query via SSH | Manual bench console |

**BEI Brain** is an enterprise knowledge fabric with three tiers:

```
Tier 1: COMPANY DATA (Pre-loaded, always available)          ← THIS SPRINT
├─ Employee Master (645 employees, all attributes)
├─ Store Mapping (44 stores, addresses, POS entities)
├─ Item Master (348 SKUs, UOM, valuation rates)
├─ Supplier Master (82 active + 32 inactive suppliers)
├─ Chart of Accounts (310 GL codes, account types)
├─ Warehouse Tree (47 warehouses, hierarchy)
├─ Procurement (POs, PRs, GRs, approval matrix)
├─ AR Aging (receivables by store)
├─ Bank Directory (account details)
└─ Supabase Sales (live POS + Web revenue via SQL views)

Tier 1.5: FRAPPE TRANSACTIONS (Real-time sync)               → S023B
Tier 2: CAPTURED KNOWLEDGE (Grows over time)                  → S023C
Tier 3: INTELLIGENT RETRIEVAL (MCP tools — 14 tools)          → S023B
```

---

## Architecture

```
COMPANY DATA (this sprint)
───────────────
data/_FINAL/*.csv  ──→  scripts/brain/ingest_company_data.py  ──→  Supabase API
Supabase sales views (already exist, verify only)
       │
       ▼
┌────────────────────────────────────────────────────────────┐
│  PostgreSQL + pgvector (Supabase: csnniykjrychgajfrgua)    │
│                                                            │
│  ┌───────────────────┐  ┌────────────────────┐             │
│  │ memories           │  │ company_data       │             │
│  │  id, content,      │  │  id, domain,       │             │
│  │  embedding(1536),  │  │  entity_type,      │             │
│  │  metadata JSONB,   │  │  entity_id,        │             │
│  │  topic_category,   │  │  content,          │             │
│  │  source, importance│  │  embedding(1536),  │             │
│  │  retrieval_count,  │  │  structured_data,  │             │
│  │  last_retrieved_at │  │  source_file,      │             │
│  │                    │  │  row_hash           │             │
│  └───────────────────┘  └────────────────────┘             │
│                                                            │
│  ┌──────────────────┐                                      │
│  │ frappe_events     │  (schema only — populated in S023B) │
│  └──────────────────┘                                      │
│                                                            │
│  ┌──────────────────────┐  ┌──────────────────────┐        │
│  │ v_all_channel_daily  │  │ store_daily_closing   │        │
│  │ (existing sales view)│  │ (existing sales view) │        │
│  └──────────────────────┘  └──────────────────────┘        │
└────────────────────────────────────────────────────────────┘
```

---

## Scope

In-scope (`S023A`):

1. PostgreSQL + pgvector `memories` table on BEI's **existing** Supabase project (`csnniykjrychgajfrgua`).
2. `company_data` table for structured master data (Employee, Store, Item, Supplier, COA, Warehouse, Procurement, AR, Bank).
3. `frappe_events` table schema (created here, populated in S023B).
4. RLS policies on all three tables.
5. Company data ingestion script + one-time bulk load (~3,500 rows).
6. Supabase sales view verification.
7. Weekly re-ingestion cron for company data freshness.

Out-of-scope (`S023A`):

1. Edge Functions (S023B).
2. MCP Server (S023B).
3. Frappe hooks (S023B).
4. Google Chat capture (S023C).
5. Multi-CLI config (S023C).

---

## Phase 1A: Database Schema

| # | Task | Acceptance Criteria |
|---|------|-------------------|
| 1A.1 | Enable `vector` extension on BEI Supabase project | `SELECT * FROM pg_extension WHERE extname = 'vector'` returns row |
| 1A.2 | Create `memories` table | Table exists with all columns, constraints, defaults |
| 1A.3 | Create `company_data` table | Table exists with domain partitioning |
| 1A.4 | Create `frappe_events` table | Table exists for real-time Frappe transaction sync |
| 1A.5 | Enable RLS on all three tables | Policies restrict appropriately per table |

**Acceptance criteria before moving to Phase 1B:**
- `SELECT * FROM pg_extension WHERE extname = 'vector'` returns a row
- All three tables (`memories`, `company_data`, `frappe_events`) appear in `information_schema.tables`
- All three have RLS enabled (`SELECT * FROM information_schema.tables WHERE row_security_enabled = true`)
- `frappe_events` indexes exist: `SELECT indexname FROM pg_indexes WHERE tablename = 'frappe_events'` returns 4 indexes
- `memories` indexes exist: `idx_memories_user_id`, `idx_memories_topic`, `idx_memories_importance`
- `company_data` unique constraint exists: `SELECT conname FROM pg_constraint WHERE conname = 'uq_company_data_entity'` returns row

**Estimated time:** 15 minutes (mostly Supabase UI clicks)

**Schema:**
```sql
CREATE EXTENSION IF NOT EXISTS vector;

-- Tier 2: Captured knowledge (thoughts, decisions, bugs, patterns)
CREATE TABLE memories (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL,
  content TEXT NOT NULL,
  embedding vector(1536),
  metadata JSONB DEFAULT '{}',       -- {people: [], topics: [], action_items: []}
  topic_category VARCHAR(100),       -- hr, procurement, finance, ops, tech, etc.
  source VARCHAR(50) DEFAULT 'manual', -- manual, google_chat, claude_code, gemini, codex, git
  importance_score INT DEFAULT 5,
  retrieval_count INT DEFAULT 0,           -- how many times this memory was returned in search results
  last_retrieved_at TIMESTAMP,             -- last time this memory was returned in a search
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);

-- Tier 1: Structured company data (pre-loaded from _FINAL + _CLEANROOM)
CREATE TABLE company_data (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  domain VARCHAR(50) NOT NULL,       -- hr, procurement, finance, inventory, stores, scm
  entity_type VARCHAR(100) NOT NULL, -- employee, supplier, item, gl_account, warehouse, store, po, pr
  entity_id VARCHAR(100),            -- employee_name, supplier_code, item_code, etc.
  content TEXT NOT NULL,             -- human-readable summary for semantic search
  embedding vector(1536),
  structured_data JSONB NOT NULL,    -- full row data as JSON
  source_file VARCHAR(255),          -- e.g. "data/_FINAL/EMPLOYEE_MASTER.csv"
  row_hash VARCHAR(64),              -- SHA-256 of structured_data for change detection
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);

-- Tier 1.5: Frappe ERP transactions (real-time sync from doc_events hooks)
CREATE TABLE frappe_events (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  doctype VARCHAR(140) NOT NULL,       -- e.g. "BEI Purchase Order", "Leave Application"
  docname VARCHAR(140) NOT NULL,       -- Frappe document name (e.g. "PO-2026-00042")
  event_type VARCHAR(20) NOT NULL,     -- submit, update, cancel, create
  domain VARCHAR(50) NOT NULL,         -- hr, procurement, finance, inventory, stores, commissary, projects
  content TEXT NOT NULL,               -- human-readable summary for semantic search
  embedding vector(1536),
  event_data JSONB NOT NULL,           -- full document snapshot at event time
  actor VARCHAR(140),                  -- user who triggered the event (e.g. "mae@bebang.ph")
  flow VARCHAR(50),                    -- which business flow (F01-F13) this belongs to
  importance_score INT DEFAULT 5,      -- auto-scored: PO >500K = 10, routine attendance = 2
  created_at TIMESTAMP DEFAULT NOW()
);

-- Performance indexes
CREATE INDEX idx_memories_user_id ON memories(user_id);
CREATE INDEX idx_memories_topic ON memories(topic_category);
CREATE INDEX idx_memories_importance ON memories(importance_score DESC);

CREATE INDEX idx_frappe_events_doctype ON frappe_events(doctype);
CREATE INDEX idx_frappe_events_domain ON frappe_events(domain);
CREATE INDEX idx_frappe_events_created ON frappe_events(created_at DESC);
CREATE INDEX idx_frappe_events_docname ON frappe_events(docname);

-- Unique constraint for idempotent re-ingestion
ALTER TABLE company_data ADD CONSTRAINT uq_company_data_entity
  UNIQUE (entity_type, entity_id);

-- RLS policies
ALTER TABLE memories ENABLE ROW LEVEL SECURITY;
ALTER TABLE company_data ENABLE ROW LEVEL SECURITY;
ALTER TABLE frappe_events ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users see own memories"
  ON memories FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "Users insert own memories"
  ON memories FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Authenticated users read company data"
  ON company_data FOR SELECT USING (auth.role() = 'authenticated');

CREATE POLICY "Authenticated users read frappe events"
  ON frappe_events FOR SELECT USING (auth.role() = 'authenticated');
```

---

## Phase 1B: Company Data Ingestion

**This is what makes BEI Brain a company brain, not a personal notebook.**

| # | Task | Acceptance Criteria |
|---|------|-------------------|
| 1B.1 | Build ingestion script (`scripts/brain/ingest_company_data.py`) | Reads all `_FINAL` CSVs, generates embeddings, bulk upserts to `company_data` |
| 1B.2 | Ingest Employee Master (645 rows) | `SELECT count(*) FROM company_data WHERE entity_type = 'employee'` = 645 |
| 1B.3 | Ingest Store Mapping (44 rows) | All stores searchable by name, address, city |
| 1B.4 | Ingest Item Master (348 rows) | All SKUs searchable by name, group, UOM |
| 1B.5 | Ingest Supplier Master (82 active + 32 inactive) | Searchable with active/inactive status |
| 1B.6 | Ingest Chart of Accounts (310 GL codes) | Searchable by code, description, account type |
| 1B.7 | Ingest Warehouse Tree (47 warehouses) | Hierarchy preserved in structured_data |
| 1B.8 | Ingest Procurement data (POs, PRs, GRs, approval matrix) | All procurement records queryable |
| 1B.9 | Ingest AR Aging data | Receivables by store searchable |
| 1B.10 | Ingest Bank Directory | Bank accounts searchable |
| 1B.11 | Verify total: ~2,500+ company_data rows | Count matches sum of all source files |
| 1B.12 | Create scheduled re-ingestion script (`scripts/brain/sync_company_data.sh`) | Weekly cron re-runs ingestion; unchanged rows skipped via `row_hash`; new/modified rows re-embedded. `crontab -e` entry: `0 3 * * 0 /path/to/sync_company_data.sh` (Sunday 3am) |

**Ingestion pattern for each CSV row:**
```python
# For each row in EMPLOYEE_MASTER.csv:
content = f"{row['employee_name']} — {row['designation']} at {row['store_location']}. "
         f"Bio ID: {row['new_attendance_device_id']}. "
         f"Department: {row['department']}. Status: {row['status']}. "
         f"Joined: {row['date_of_joining']}."

# This content gets embedded, so asking "who works at Market Market?"
# semantically matches employees with store_location containing Market Market.
```

**Data source inventory:**

| Source File | Domain | Entity Type | Rows | Key Fields |
|-------------|--------|-------------|------|------------|
| `_FINAL/EMPLOYEE_MASTER.csv` | hr | employee | 645 | name, bio_id, designation, store, department, status |
| `_FINAL/EMPLOYEE_MASTER_ENRICHED.csv` | hr | employee_payroll | 640 | payroll, gov IDs, bank accounts |
| `_FINAL/STORE_MAPPING.csv` | stores | store | 44 | name, address, city, POS entity, superadmin_id |
| `_FINAL/ITEM_MASTER.csv` | inventory | item | 348 | code, name, UOM, item group, valuation rate |
| `_FINAL/SUPPLIER_MASTER.csv` | procurement | supplier | 82 | name, contact, payment terms, status |
| `_FINAL/SUPPLIER_MASTER_INACTIVE.csv` | procurement | supplier | 32 | name, reason inactive |
| `_FINAL/COA.csv` | finance | gl_account | 310 | GL code, description, type, nature, class |
| `_FINAL/WAREHOUSE_TREE.csv` | inventory | warehouse | 47 | name, parent, type |
| `_FINAL/AP_OPENING.csv` | finance | ap_balance | ~100 | supplier, amount, aging bucket |
| `_FINAL/BANK_DIRECTORY.csv` | finance | bank_account | ~20 | bank, branch, account number |
| `_FINAL/procurement/Purchase_Order.csv` | procurement | po | 701 | PO#, supplier, amount, status, date |
| `_FINAL/procurement/Purchase_Requisitions.csv` | procurement | pr | 339 | PR#, requestor, items, status |
| `_FINAL/procurement/Goods_Receipts.csv` | procurement | gr | 672 | GR#, PO ref, received date, qty |
| `_FINAL/procurement/Approval_Matrix.csv` | procurement | approval_rule | 8 | threshold, approvers, conditions |
| `_FINAL/procurement/Suppliers.csv` | procurement | supplier_app | 80 | from procurement app |
| `_FINAL/procurement/Item_List.csv` | procurement | item_procurement | 324 | items used in procurement flows |
| `_FINAL/ar_aging/AR_AGING_DETAILS.csv` | finance | ar_aging | ~50 | store, amount, aging buckets |
| `_FINAL/ar_aging/SUMMARY_AGING.csv` | finance | ar_summary | ~20 | aging summary by bucket |
| **Total** | | | **~3,500** | |

**Acceptance criteria before moving to S023B:**
- `SELECT count(*) FROM company_data` returns ~3,500
- Random spot-checks: `SELECT * FROM company_data WHERE entity_type='employee' LIMIT 1` has non-null `embedding` and `structured_data`
- Semantic search works: `SELECT *, 1 - (embedding <-> query_embedding) as score FROM company_data WHERE entity_type = 'employee' ORDER BY embedding <-> query_embedding LIMIT 5` returns relevant employees with score > 0.5

**Estimated time:** 45 minutes (script writing + one-time ingestion)

---

## Phase 1C: Supabase Sales Integration (PARALLEL with 1B)

BEI's Supabase project already has live sales data. Instead of duplicating, the MCP server (S023B) will query **existing views** directly.

| # | Task | Acceptance Criteria |
|---|------|-------------------|
| 1C.1 | Verify `v_all_channel_daily` view is accessible via service role | Query returns POS + Web daily sales |
| 1C.2 | Verify `store_daily_closing` view is accessible | Query returns per-store daily closing figures |
| 1C.3 | Document view schemas for MCP `sales_query()` tool | Column names, filters, date ranges documented |

**Existing sales views (no new tables needed):**
```sql
-- v_all_channel_daily: Combined POS + Web daily revenue
-- Columns: business_date, channel, store_name, gross_sales, net_sales, order_count
-- Filters: WHERE order_status = 'Completed' (Web), payment_status = 'PAID' (POS)

-- store_daily_closing: Per-store daily closing
-- Columns: business_date, store_name, total_gross, total_net, pos_gross, web_gross
```

**What this enables (S023B MCP `sales_query()` tool):**
- "What was Market Market's revenue last week?" → `sales_query(store="Market Market", date_range="last_7_days")`
- "Which store had the highest sales yesterday?" → `sales_query(date_range="yesterday", sort="desc")`
- "Show me web vs POS split for February" → `sales_query(channel="all", date_range="2026-02-01:2026-02-28")`

**Acceptance criteria:**
- `SELECT count(*) FROM v_all_channel_daily WHERE business_date >= '2026-03-01'` returns >0
- Same for `store_daily_closing`

**Estimated time:** 10 minutes (SQL verification only)

---

## Secrets Management

All keys managed via Doppler (`bei-erp` project, `dev` config):

| Secret | Purpose | Source |
|--------|---------|--------|
| `OPENAI_API_KEY` | Embedding generation (`text-embedding-3-small`) | Doppler |
| `SUPABASE_URL` | Database connection (`csnniykjrychgajfrgua`) | Doppler |
| `SUPABASE_SERVICE_ROLE_KEY` | Edge Function auth + company data writes | Doppler |

---

## Technology Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Supabase project | Existing `csnniykjrychgajfrgua` | Already paid, already has sales data |
| Embedding model | `text-embedding-3-small` (1536D) | 62.3% MTEB, sufficient for BEI scale |
| Vector index | None (exact search) until >10K rows | Sub-500ms at current volumes |
| Company data storage | Separate `company_data` table | Structured data needs different schema than memories |
| Sales data | Query existing views (no duplication) | Views already correct and maintained |

---

## Estimated Time

| Phase | Time |
|-------|------|
| 1A: Database Schema | 15 min |
| 1B: Company Data Ingestion | 45 min |
| 1C: Sales View Verification | 10 min |
| **Total S023A** | **~70 min** |

---

## Definition of Done (S023A)

- [x] `memories` table exists on Supabase with pgvector and RLS enabled ✅ 2026-03-03
- [x] `company_data` table exists with all BEI master data pre-loaded (3,924 rows — exceeds ~3,500 target) ✅ 2026-03-03
- [x] `frappe_events` table schema created with indexes on doctype, domain, created_at (7 indexes) ✅ 2026-03-03
- [x] `memories` indexes exist: `idx_memories_user_id`, `idx_memories_topic`, `idx_memories_importance` (+ HNSW vector) ✅ 2026-03-03
- [x] `company_data` unique constraint `uq_company_data_entity` exists ✅ 2026-03-03
- [x] RLS policies on all three tables (+ brain_audit_log) ✅ 2026-03-03
- [x] Sales views `v_all_channel_daily` (275 rows) and `store_daily_closing` (8,546 rows) verified accessible ✅ 2026-03-03
- [x] Company data weekly re-ingestion script created (`scripts/brain/sync_company_data.sh`) with `row_hash` change detection ✅ 2026-03-03
- [x] All API keys in Doppler, zero hardcoded secrets ✅ 2026-03-03
- [x] Semantic search on `company_data` returns relevant results with score > 0.5 ("employees at Market Market" → 0.52 top score) ✅ 2026-03-03
- [x] Sales view filter documentation: `v_all_channel_daily` has pos/web split columns; `store_daily_closing` has per-store daily closing with discount/VAT breakdown ✅ 2026-03-03

---

## Reference

| Resource | Location |
|----------|----------|
| Research Synthesis | `.claude/rlm_state/OPEN_BRAIN_RESEARCH_SYNTHESIS.md` |
| SOTA Research | `.claude/rlm_state/results/brainstorm_sota_research.md` |
| Company Data SSOT | `data/_FINAL/README.md` + `data/_FINAL/MANIFEST.json` |
| Sales Schema | `memory/supabase-schema.md` |
| S023B Plan | `docs/plans/2026-03-03-sprint-23b-bei-brain-intelligence-layer.md` |
| S023C Plan | `docs/plans/2026-03-03-sprint-23c-bei-brain-integration-hardening.md` |

---

## Audit Amendments (v1.1) — 2026-03-03

### Audit Methodology

4 specialized agents audited this plan (part of BEI Brain trilogy audit), each writing detailed findings to disk. A GLM-5 adversarial fact-check verified all blockers. Full reports with SQL/code fixes are in the referenced files.

| Domain | Agent | Findings File | Score |
|--------|-------|---------------|-------|
| System Architecture | system-arch-auditor | `output/plan-audit/bei-brain-trilogy/system_arch_findings.md` | 3.2/5 architecture |
| Supabase Patterns | supabase-auditor | `output/plan-audit/bei-brain-trilogy/supabase_findings.md` | 4/12 compliance |
| Deployment/QA | deployment-qa-auditor | `output/plan-audit/bei-brain-trilogy/deployment_qa_findings.md` | CONDITIONAL NO-GO |
| **Code Verification** | N/A (unbuilt system) | — | Skipped — plan audit only |
| **GLM-5 Fact-Check** | glm_fact_check.py | `output/plan-audit/bei-brain-trilogy/glm_verification.md` | 6 supported, 6 unverified |

### S023A Blockers (Must Resolve Before Execution)

#### BLOCKER 1: Missing pgvector vector indexes
**Source:** `system_arch_findings.md` F-002 + `supabase_findings.md` W-1 | **Severity:** CRITICAL
**Problem:** Zero HNSW/IVFFlat indexes on any embedding column. All semantic search is sequential scan. At 1M frappe_events rows (12 months), queries will time out.
**Fix:** Add `CREATE INDEX ... USING hnsw/ivfflat` to Phase 1A DDL for all 3 tables. See F-002 for exact SQL.

#### BLOCKER 2: RLS policies incomplete
**Source:** `supabase_findings.md` C-1, C-2 | **Severity:** CRITICAL
**Problem:** memories missing UPDATE/DELETE policies. company_data and frappe_events missing all write policies. service_role_key bypasses RLS with no application-layer auth documented.
**Fix:** Add explicit UPDATE/DELETE policies on memories, explicit `WITH CHECK (false)` INSERT/UPDATE/DELETE on company_data and frappe_events. See C-1, C-2 for SQL.

#### BLOCKER 3: updated_at trigger must be in S023A, not S023C
**Source:** `supabase_findings.md` C-3 | **Severity:** CRITICAL
**Problem:** Trigger deferred to S023C but upserts begin in S023A/B — stale timestamps until S023C.
**Fix:** Add `handle_updated_at()` trigger function and attach to memories + company_data in Phase 1A DDL. See C-3 for SQL.

#### BLOCKER 4: No CHECK constraints on enum fields
**Source:** `supabase_findings.md` C-4 | **Severity:** CRITICAL
**Problem:** source, event_type, domain, flow columns accept any string — typos poison queries and Smart Alerts silently.
**Fix:** Add CHECK constraints with allowed values to Phase 1A DDL. See C-4 for SQL.

#### BLOCKER 5: No DDL dry-run path
**Source:** `deployment_qa_findings.md` D-001 | **Severity:** CRITICAL
**Problem:** If any of the 7 DDL statements fails partway, schema is left partially created.
**Fix:** Execute all Phase 1A DDL within `BEGIN; ... ROLLBACK;` first (dry-run), then `BEGIN; ... COMMIT;` for real deploy.

#### BLOCKER 6: Add embedding_skipped and embedding_model columns
**Source:** `system_arch_findings.md` F-006, F-010 | **Severity:** WARNING
**Problem:** Cannot distinguish "failed embed" from "intentionally skipped". No migration path if OpenAI deprecates text-embedding-3-small.
**Fix:** Add `embedding_skipped BOOLEAN DEFAULT FALSE`, `embedding_model VARCHAR(100) DEFAULT 'text-embedding-3-small'`, and `hook_version VARCHAR(20)` to frappe_events in Phase 1A DDL.

### Additional Recommendations (Non-Blocking)

1. **Memory dedup** (`system_arch_findings.md` F-007): Add `content_hash VARCHAR(64)` + partial unique index on memories
2. **Schema versioning** (`system_arch_findings.md` F-012): Create `migrations/` directory with numbered SQL files
3. **Audit log early** (`supabase_findings.md` W-5): Move `brain_audit_log` creation to S023A DDL
4. **Importance score range** (`supabase_findings.md` I-3): Add `CHECK (importance_score BETWEEN 1 AND 10)` to memories and frappe_events
5. **Supabase tier** (`deployment_qa_findings.md` W-010): Verify project is on Pro+ plan before committing to 1M+ rows/year

### Pre-Flight Checks: Audit Additions

- [x] **AUDIT-1:** HNSW vector indexes on all 3 embedding columns (m=16, ef_construction=64) ✅ 2026-03-03
- [x] **AUDIT-2:** UPDATE/DELETE RLS on memories; explicit deny INSERT/UPDATE/DELETE on company_data, frappe_events, brain_audit_log ✅ 2026-03-03
- [x] **AUDIT-3:** `handle_updated_at()` trigger attached to memories + company_data ✅ 2026-03-03
- [x] **AUDIT-4:** CHECK constraints on source, event_type, domain, flow, importance_score (all tables) ✅ 2026-03-03
- [x] **AUDIT-5:** DDL dry-run (`BEGIN...ROLLBACK`) passed before real deploy ✅ 2026-03-03
- [x] **AUDIT-6:** `embedding_skipped`, `embedding_model`, `hook_version` columns in frappe_events ✅ 2026-03-03

### GO / NO-GO Gate (Updated)

**S023A AUDIT GATE: PASSED. All 6 audit checks resolved. 11/11 DoD items COMPLETE.**

### Version History

| Version | Date | Change |
|---------|------|--------|
| v1.0 | 2026-03-03 | Initial plan (split from monolithic Sprint 23) |
| v1.1 | 2026-03-03 | Audit amendments: 6 blockers from 3-domain parallel audit + GLM-5 fact-check |
| v1.2 | 2026-03-03 | Execution: Phase 1A (schema + 6 audit fixes), 1B (3,924 rows ingested), 1C (sales views verified) |
