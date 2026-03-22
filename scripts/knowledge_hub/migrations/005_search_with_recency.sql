-- 005_search_with_recency.sql
-- Search with recency weighting (half-life decay)
-- Phase 2: Enhanced RAG with recency scoring

-- ============================================
-- Recency-weighted search function
-- ============================================
-- Combines semantic similarity with document age
-- Formula: final_score = (1-w) * similarity + w * recency
-- Where recency = exp(-decay_rate * age_in_days)

CREATE OR REPLACE FUNCTION match_chunks_with_recency(
    query_embedding vector(768),
    match_threshold FLOAT DEFAULT 0.5,
    match_count INT DEFAULT 5,
    decay_rate FLOAT DEFAULT 0.01,  -- Higher = faster decay (0.01 = ~70 day half-life)
    recency_weight FLOAT DEFAULT 0.3  -- 0-1, how much recency matters vs similarity
)
RETURNS TABLE (
    chunk_id UUID,
    document_id UUID,
    document_title TEXT,
    section_title TEXT,
    content TEXT,
    source_path TEXT,
    similarity FLOAT,
    recency_score FLOAT,
    final_score FLOAT,
    document_date TIMESTAMPTZ
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        c.id AS chunk_id,
        c.document_id,
        d.title AS document_title,
        c.section_title,
        c.content,
        d.source_path,
        (1 - (c.embedding <=> query_embedding))::FLOAT AS similarity,
        EXP(-decay_rate * EXTRACT(EPOCH FROM (NOW() - d.created_at)) / 86400)::FLOAT AS recency_score,
        (
            (1 - recency_weight) * (1 - (c.embedding <=> query_embedding)) +
            recency_weight * EXP(-decay_rate * EXTRACT(EPOCH FROM (NOW() - d.created_at)) / 86400)
        )::FLOAT AS final_score,
        d.created_at AS document_date
    FROM kb_chunks c
    JOIN kb_documents d ON c.document_id = d.id
    WHERE d.status = 'completed'
      AND c.quality_score >= 0.5  -- Filter low-quality chunks
      AND 1 - (c.embedding <=> query_embedding) > match_threshold
    ORDER BY final_score DESC
    LIMIT match_count;
END;
$$;

-- Add documentation
COMMENT ON FUNCTION match_chunks_with_recency IS
'Semantic search with recency weighting for RAG system.
Parameters:
- query_embedding: 768-dim vector from Gemini
- match_threshold: minimum cosine similarity (0.5 default)
- match_count: max results to return (5 default)
- decay_rate: exponential decay rate (0.01 = ~70 day half-life)
- recency_weight: balance between similarity and recency (0.3 = 70% similarity, 30% recency)

Recency formula: exp(-decay_rate * age_days)
- decay_rate=0.01: 70-day half-life (ManCom minutes)
- decay_rate=0.001: 693-day half-life (HR policies)
- decay_rate=0.1: 7-day half-life (daily reports)

Only returns chunks with quality_score >= 0.5.';
