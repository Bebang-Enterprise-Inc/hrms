"""
BEI Brain S023B BLOCKER 1: Add embedding_status column to all 3 tables.
Also adds idempotency_key to memories (BLOCKER 2 prep).
Usage: python scripts/brain/add_embedding_status.py [--dry-run]
"""
import sys
import subprocess
import requests


def get_doppler_secret(key):
    result = subprocess.run(
        ["C:/Users/Sam/bin/doppler.exe", "secrets", "get", key, "--plain",
         "--project", "bei-erp", "--config", "dev"],
        capture_output=True, text=True
    )
    return result.stdout.strip()


TOKEN = get_doppler_secret("SUPABASE_ACCESS_TOKEN")
PROJECT_REF = "csnniykjrychgajfrgua"
API_URL = f"https://api.supabase.com/v1/projects/{PROJECT_REF}/database/query"

ALTER_DDL = """
-- S023B BLOCKER 1: Add embedding_status column to all 3 tables
-- Values: 'complete', 'pending', 'failed', 'skipped'
ALTER TABLE memories
    ADD COLUMN IF NOT EXISTS embedding_status VARCHAR(20) DEFAULT 'complete';

ALTER TABLE company_data
    ADD COLUMN IF NOT EXISTS embedding_status VARCHAR(20) DEFAULT 'complete';

ALTER TABLE frappe_events
    ADD COLUMN IF NOT EXISTS embedding_status VARCHAR(20) DEFAULT 'complete';

-- CHECK constraints for embedding_status
DO $$ BEGIN
    ALTER TABLE memories ADD CONSTRAINT chk_memories_embedding_status
        CHECK (embedding_status IN ('complete', 'pending', 'failed', 'skipped'));
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    ALTER TABLE company_data ADD CONSTRAINT chk_company_data_embedding_status
        CHECK (embedding_status IN ('complete', 'pending', 'failed', 'skipped'));
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    ALTER TABLE frappe_events ADD CONSTRAINT chk_frappe_events_embedding_status
        CHECK (embedding_status IN ('complete', 'pending', 'failed', 'skipped'));
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- S023B BLOCKER 2 prep: Add idempotency_key to memories for dedup
ALTER TABLE memories
    ADD COLUMN IF NOT EXISTS idempotency_key VARCHAR(255);

-- Partial unique index for idempotency (only non-null keys)
CREATE UNIQUE INDEX IF NOT EXISTS idx_memories_idempotency
    ON memories(idempotency_key) WHERE idempotency_key IS NOT NULL;

-- Index for backfill query: find records needing embedding
CREATE INDEX IF NOT EXISTS idx_memories_embedding_status
    ON memories(embedding_status) WHERE embedding_status != 'complete';
CREATE INDEX IF NOT EXISTS idx_company_data_embedding_status
    ON company_data(embedding_status) WHERE embedding_status != 'complete';
CREATE INDEX IF NOT EXISTS idx_frappe_events_embedding_status
    ON frappe_events(embedding_status) WHERE embedding_status != 'complete';
"""

VERIFY_SQL = """
SELECT column_name, table_name
FROM information_schema.columns
WHERE table_schema = 'public'
  AND column_name IN ('embedding_status', 'idempotency_key')
  AND table_name IN ('memories', 'company_data', 'frappe_events')
ORDER BY table_name, column_name;
"""


def run_sql(sql, label):
    headers = {
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type": "application/json",
    }
    resp = requests.post(API_URL, json={"query": sql}, headers=headers, timeout=60)
    if resp.status_code in (200, 201):
        data = resp.json()
        print(f"  OK: {label}")
        if isinstance(data, list) and len(data) > 0:
            for row in data[:10]:
                print(f"    -> {row}")
        return True
    else:
        print(f"  FAIL ({resp.status_code}): {label}")
        print(f"  Response: {resp.text[:500]}")
        return False


def main():
    dry_run = "--dry-run" in sys.argv

    if dry_run:
        print("=== DRY RUN ===")
        ok = run_sql(f"BEGIN;\n{ALTER_DDL}\nROLLBACK;", "ALTER DDL dry-run")
        if ok:
            print("\nDRY RUN PASSED — safe to run without --dry-run")
        else:
            print("\nDRY RUN FAILED")
            sys.exit(1)
    else:
        print("=== DEPLOYING S023B BLOCKER FIXES ===")
        if not run_sql(ALTER_DDL, "Add embedding_status + idempotency_key columns"):
            print("\nFAILED")
            sys.exit(1)

        print("\n=== VERIFICATION ===")
        run_sql(VERIFY_SQL, "Column existence check")
        print("\nDONE")


if __name__ == "__main__":
    main()
