"""
BEI Brain S023B: Deploy Supabase RPC functions for MCP Server.
- match_memories: decay-weighted semantic search
- increment_retrieval: update retrieval stats
Usage: python scripts/brain/deploy_rpc_functions.py
"""
import subprocess
import requests
import sys


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

RPC_SQL = """
-- ============================================================
-- match_memories: decay-weighted semantic search
-- Called by MCP semantic_search tool
-- Formula: score = cosine * W1 + importance/10 * W2 + recency_decay * W3
-- where recency_decay = exp(-ln(2)/half_life * days_since_retrieval)
-- ============================================================
CREATE OR REPLACE FUNCTION match_memories(
    query_embedding vector(1536),
    match_count int DEFAULT 10,
    filter_domain text DEFAULT NULL,
    cosine_weight float DEFAULT 0.6,
    importance_weight float DEFAULT 0.25,
    recency_weight float DEFAULT 0.15,
    half_life_days float DEFAULT 90
)
RETURNS TABLE (
    id uuid,
    content text,
    metadata jsonb,
    topic_category varchar,
    source varchar,
    importance_score int,
    retrieval_count int,
    last_retrieved_at timestamptz,
    created_at timestamptz,
    score float
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        m.id,
        m.content,
        m.metadata,
        m.topic_category,
        m.source,
        m.importance_score,
        m.retrieval_count,
        m.last_retrieved_at,
        m.created_at,
        (
            (1 - (m.embedding <=> query_embedding)) * cosine_weight
            + (LEAST(m.importance_score::float / 10.0, 1.0)) * importance_weight
            + (
                CASE
                    WHEN m.last_retrieved_at IS NULL THEN 0.5
                    ELSE EXP(
                        -LN(2.0) / half_life_days
                        * EXTRACT(EPOCH FROM (NOW() - m.last_retrieved_at)) / 86400.0
                    )
                END
            ) * recency_weight
        )::float AS score
    FROM memories m
    WHERE m.embedding IS NOT NULL
      AND (filter_domain IS NULL OR m.topic_category = filter_domain)
    ORDER BY score DESC
    LIMIT match_count;
END;
$$;

-- ============================================================
-- increment_retrieval: update retrieval stats after search
-- ============================================================
CREATE OR REPLACE FUNCTION increment_retrieval(memory_id uuid)
RETURNS void
LANGUAGE plpgsql
AS $$
BEGIN
    UPDATE memories
    SET retrieval_count = COALESCE(retrieval_count, 0) + 1,
        last_retrieved_at = NOW()
    WHERE id = memory_id;
END;
$$;
"""


def run_sql(sql, label):
    headers = {
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type": "application/json",
    }
    resp = requests.post(API_URL, json={"query": sql}, headers=headers, timeout=60)
    if resp.status_code in (200, 201):
        print(f"  OK: {label}")
        return True
    else:
        print(f"  FAIL ({resp.status_code}): {label}")
        print(f"  Response: {resp.text[:500]}")
        return False


def main():
    print("=== DEPLOYING RPC FUNCTIONS ===")
    if run_sql(RPC_SQL, "match_memories + increment_retrieval"):
        print("\nDONE — RPC functions deployed")
    else:
        print("\nFAILED")
        sys.exit(1)


if __name__ == "__main__":
    main()
