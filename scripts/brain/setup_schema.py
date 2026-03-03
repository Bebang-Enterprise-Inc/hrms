"""
BEI Brain S023A Phase 1A: Database Schema Setup
Executes DDL against Supabase via Management API.
Resolves all 6 audit blockers (AUDIT-1 through AUDIT-6).

Usage: python scripts/brain/setup_schema.py [--dry-run]
"""
import sys
import os
import json
import subprocess

# Get secrets from Doppler
def get_doppler_secret(key):
    result = subprocess.run(
        ["C:/Users/Sam/bin/doppler.exe", "secrets", "get", key, "--plain",
         "--project", "bei-erp", "--config", "dev"],
        capture_output=True, text=True
    )
    return result.stdout.strip()

SUPABASE_ACCESS_TOKEN = get_doppler_secret("SUPABASE_ACCESS_TOKEN")
PROJECT_REF = "csnniykjrychgajfrgua"

DDL = """
-- ============================================================
-- BEI Brain S023A: Database Schema (v1.1 with Audit Fixes)
-- ============================================================

-- 1. Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- ============================================================
-- AUDIT-3: updated_at trigger function (must exist before tables)
-- ============================================================
CREATE OR REPLACE FUNCTION handle_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- ============================================================
-- Table 1: memories (Tier 2 — captured knowledge)
-- ============================================================
CREATE TABLE IF NOT EXISTS memories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    content TEXT NOT NULL,
    embedding vector(1536),
    metadata JSONB DEFAULT '{}',
    topic_category VARCHAR(100),
    source VARCHAR(50) DEFAULT 'manual',
    importance_score INT DEFAULT 5,
    retrieval_count INT DEFAULT 0,
    last_retrieved_at TIMESTAMPTZ,
    content_hash VARCHAR(64),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    -- AUDIT-4: CHECK constraints on enum fields
    CONSTRAINT chk_memories_source CHECK (
        source IN ('manual', 'google_chat', 'claude_code', 'gemini', 'codex', 'git', 'blip')
    ),
    CONSTRAINT chk_memories_importance CHECK (
        importance_score BETWEEN 1 AND 10
    )
);

-- ============================================================
-- Table 2: company_data (Tier 1 — structured master data)
-- ============================================================
CREATE TABLE IF NOT EXISTS company_data (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    domain VARCHAR(50) NOT NULL,
    entity_type VARCHAR(100) NOT NULL,
    entity_id VARCHAR(100),
    content TEXT NOT NULL,
    embedding vector(1536),
    structured_data JSONB NOT NULL,
    source_file VARCHAR(255),
    row_hash VARCHAR(64),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    -- AUDIT-4: CHECK constraint on domain
    CONSTRAINT chk_company_data_domain CHECK (
        domain IN ('hr', 'procurement', 'finance', 'inventory', 'stores', 'scm', 'commissary', 'projects', 'platform')
    )
);

-- Unique constraint for idempotent re-ingestion
ALTER TABLE company_data ADD CONSTRAINT uq_company_data_entity
    UNIQUE (entity_type, entity_id);

-- ============================================================
-- Table 3: frappe_events (Tier 1.5 — real-time Frappe sync)
-- ============================================================
CREATE TABLE IF NOT EXISTS frappe_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    doctype VARCHAR(140) NOT NULL,
    docname VARCHAR(140) NOT NULL,
    event_type VARCHAR(20) NOT NULL,
    domain VARCHAR(50) NOT NULL,
    content TEXT NOT NULL,
    embedding vector(1536),
    event_data JSONB NOT NULL,
    actor VARCHAR(140),
    flow VARCHAR(50),
    importance_score INT DEFAULT 5,
    created_at TIMESTAMPTZ DEFAULT NOW(),

    -- AUDIT-6: embedding metadata columns
    embedding_skipped BOOLEAN DEFAULT FALSE,
    embedding_model VARCHAR(100) DEFAULT 'text-embedding-3-small',
    hook_version VARCHAR(20) DEFAULT '1.0',

    -- AUDIT-4: CHECK constraints on enum fields
    CONSTRAINT chk_frappe_events_event_type CHECK (
        event_type IN ('submit', 'update', 'cancel', 'create')
    ),
    CONSTRAINT chk_frappe_events_domain CHECK (
        domain IN ('hr', 'procurement', 'finance', 'inventory', 'stores', 'scm', 'commissary', 'projects', 'platform')
    ),
    CONSTRAINT chk_frappe_events_flow CHECK (
        flow IS NULL OR flow IN ('F01','F02','F03','F04','F05','F06','F07','F08','F09','F10','F11','F12','F13')
    ),
    CONSTRAINT chk_frappe_events_importance CHECK (
        importance_score BETWEEN 1 AND 10
    )
);

-- ============================================================
-- Audit log table (Recommendation #3 from audit)
-- ============================================================
CREATE TABLE IF NOT EXISTS brain_audit_log (
    id BIGSERIAL PRIMARY KEY,
    table_name VARCHAR(50) NOT NULL,
    operation VARCHAR(10) NOT NULL,
    row_id UUID,
    old_data JSONB,
    new_data JSONB,
    actor VARCHAR(140),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- Performance indexes
-- ============================================================

-- memories indexes
CREATE INDEX IF NOT EXISTS idx_memories_user_id ON memories(user_id);
CREATE INDEX IF NOT EXISTS idx_memories_topic ON memories(topic_category);
CREATE INDEX IF NOT EXISTS idx_memories_importance ON memories(importance_score DESC);
CREATE INDEX IF NOT EXISTS idx_memories_created ON memories(created_at DESC);

-- frappe_events indexes
CREATE INDEX IF NOT EXISTS idx_frappe_events_doctype ON frappe_events(doctype);
CREATE INDEX IF NOT EXISTS idx_frappe_events_domain ON frappe_events(domain);
CREATE INDEX IF NOT EXISTS idx_frappe_events_created ON frappe_events(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_frappe_events_docname ON frappe_events(docname);

-- company_data indexes
CREATE INDEX IF NOT EXISTS idx_company_data_domain ON company_data(domain);
CREATE INDEX IF NOT EXISTS idx_company_data_entity_type ON company_data(entity_type);

-- AUDIT-1: Vector indexes (HNSW) for semantic search
-- Using HNSW for better query performance at current scale
CREATE INDEX IF NOT EXISTS idx_memories_embedding ON memories
    USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64);
CREATE INDEX IF NOT EXISTS idx_company_data_embedding ON company_data
    USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64);
CREATE INDEX IF NOT EXISTS idx_frappe_events_embedding ON frappe_events
    USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64);

-- Composite indexes for Smart Alerts (S023C prep)
CREATE INDEX IF NOT EXISTS idx_frappe_events_doctype_created ON frappe_events(doctype, created_at DESC);

-- ============================================================
-- AUDIT-3: updated_at triggers
-- ============================================================
DROP TRIGGER IF EXISTS set_updated_at_memories ON memories;
CREATE TRIGGER set_updated_at_memories
    BEFORE UPDATE ON memories
    FOR EACH ROW EXECUTE FUNCTION handle_updated_at();

DROP TRIGGER IF EXISTS set_updated_at_company_data ON company_data;
CREATE TRIGGER set_updated_at_company_data
    BEFORE UPDATE ON company_data
    FOR EACH ROW EXECUTE FUNCTION handle_updated_at();

-- ============================================================
-- AUDIT-2: Row Level Security (complete policies)
-- ============================================================

-- Enable RLS on all tables
ALTER TABLE memories ENABLE ROW LEVEL SECURITY;
ALTER TABLE company_data ENABLE ROW LEVEL SECURITY;
ALTER TABLE frappe_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE brain_audit_log ENABLE ROW LEVEL SECURITY;

-- memories: users see/manage own memories
CREATE POLICY "Users see own memories"
    ON memories FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "Users insert own memories"
    ON memories FOR INSERT WITH CHECK (auth.uid() = user_id);
CREATE POLICY "Users update own memories"
    ON memories FOR UPDATE USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);
CREATE POLICY "Users delete own memories"
    ON memories FOR DELETE USING (auth.uid() = user_id);

-- company_data: read-only for authenticated, no direct writes (service_role only)
CREATE POLICY "Authenticated users read company data"
    ON company_data FOR SELECT USING (auth.role() = 'authenticated');
CREATE POLICY "Deny direct inserts to company data"
    ON company_data FOR INSERT WITH CHECK (false);
CREATE POLICY "Deny direct updates to company data"
    ON company_data FOR UPDATE USING (false) WITH CHECK (false);
CREATE POLICY "Deny direct deletes from company data"
    ON company_data FOR DELETE USING (false);

-- frappe_events: read-only for authenticated, no direct writes (service_role only)
CREATE POLICY "Authenticated users read frappe events"
    ON frappe_events FOR SELECT USING (auth.role() = 'authenticated');
CREATE POLICY "Deny direct inserts to frappe events"
    ON frappe_events FOR INSERT WITH CHECK (false);
CREATE POLICY "Deny direct updates to frappe events"
    ON frappe_events FOR UPDATE USING (false) WITH CHECK (false);
CREATE POLICY "Deny direct deletes from frappe events"
    ON frappe_events FOR DELETE USING (false);

-- brain_audit_log: no direct access (service_role only)
CREATE POLICY "Deny all direct access to audit log"
    ON brain_audit_log FOR ALL USING (false);

-- ============================================================
-- Audit logging trigger function
-- ============================================================
CREATE OR REPLACE FUNCTION log_brain_audit()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        INSERT INTO brain_audit_log (table_name, operation, row_id, old_data, actor)
        VALUES (TG_TABLE_NAME, TG_OP, OLD.id, to_jsonb(OLD), current_setting('request.jwt.claims', true)::json->>'sub');
        RETURN OLD;
    ELSIF TG_OP = 'UPDATE' THEN
        INSERT INTO brain_audit_log (table_name, operation, row_id, old_data, new_data, actor)
        VALUES (TG_TABLE_NAME, TG_OP, NEW.id, to_jsonb(OLD), to_jsonb(NEW), current_setting('request.jwt.claims', true)::json->>'sub');
        RETURN NEW;
    ELSIF TG_OP = 'INSERT' THEN
        INSERT INTO brain_audit_log (table_name, operation, row_id, new_data, actor)
        VALUES (TG_TABLE_NAME, TG_OP, NEW.id, to_jsonb(NEW), current_setting('request.jwt.claims', true)::json->>'sub');
        RETURN NEW;
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Attach audit triggers
DROP TRIGGER IF EXISTS audit_memories ON memories;
CREATE TRIGGER audit_memories
    AFTER INSERT OR UPDATE OR DELETE ON memories
    FOR EACH ROW EXECUTE FUNCTION log_brain_audit();

DROP TRIGGER IF EXISTS audit_company_data ON company_data;
CREATE TRIGGER audit_company_data
    AFTER INSERT OR UPDATE OR DELETE ON company_data
    FOR EACH ROW EXECUTE FUNCTION log_brain_audit();

DROP TRIGGER IF EXISTS audit_frappe_events ON frappe_events;
CREATE TRIGGER audit_frappe_events
    AFTER INSERT OR UPDATE OR DELETE ON frappe_events
    FOR EACH ROW EXECUTE FUNCTION log_brain_audit();
"""

def execute_sql(sql, dry_run=False):
    """Execute SQL via Supabase Management API."""
    import urllib.request

    url = f"https://api.supabase.com/v1/projects/{PROJECT_REF}/database/query"
    headers = {
        "Authorization": f"Bearer {SUPABASE_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }

    if dry_run:
        wrapped = f"BEGIN;\n{sql}\nROLLBACK;"
        print("=== DRY RUN (ROLLBACK) ===")
    else:
        wrapped = sql

    data = json.dumps({"query": wrapped}).encode()
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read().decode())
            return result
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"HTTP {e.code}: {body}")
        return None


def main():
    dry_run = "--dry-run" in sys.argv

    if dry_run:
        print("Phase 1A: DRY RUN (AUDIT-5 — all DDL in BEGIN...ROLLBACK)")
        result = execute_sql(DDL, dry_run=True)
        if result is not None:
            print("DRY RUN PASSED — no errors detected")
            print(json.dumps(result, indent=2)[:500])
        else:
            print("DRY RUN FAILED — fix errors before real deploy")
            sys.exit(1)
    else:
        print("Phase 1A: EXECUTING DDL (real deploy)")
        # AUDIT-5: dry-run first
        print("Step 1: Dry-run validation...")
        dry_result = execute_sql(DDL, dry_run=True)
        if dry_result is None:
            print("Dry-run failed — aborting real deploy")
            sys.exit(1)
        print("Step 1: Dry-run passed")

        print("Step 2: Real deploy...")
        result = execute_sql(DDL, dry_run=False)
        if result is not None:
            print("SCHEMA DEPLOYED SUCCESSFULLY")
            print(json.dumps(result, indent=2)[:500])
        else:
            print("DEPLOY FAILED")
            sys.exit(1)


if __name__ == "__main__":
    main()
