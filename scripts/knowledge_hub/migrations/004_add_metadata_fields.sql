-- 004_add_metadata_fields.sql
-- Add metadata, quality scoring, and forgetting fields
-- Phase 2: Enhanced RAG with LLM-generated metadata

-- ============================================
-- Document-level metadata enhancements
-- ============================================

-- LLM-generated summary of the document
ALTER TABLE kb_documents ADD COLUMN IF NOT EXISTS summary TEXT;

-- Extracted keywords for better searchability
ALTER TABLE kb_documents ADD COLUMN IF NOT EXISTS keywords TEXT[];

-- Named entities (people, orgs, dates, etc.)
ALTER TABLE kb_documents ADD COLUMN IF NOT EXISTS entities JSONB DEFAULT '[]';

-- ============================================
-- Chunk-level enhancements
-- ============================================

-- LLM-generated summary of the chunk
ALTER TABLE kb_chunks ADD COLUMN IF NOT EXISTS summary TEXT;

-- Extracted keywords for the chunk
ALTER TABLE kb_chunks ADD COLUMN IF NOT EXISTS keywords TEXT[];

-- Quality score (0.0 to 1.0) for ranking
-- Higher scores = more relevant/useful content
ALTER TABLE kb_chunks ADD COLUMN IF NOT EXISTS quality_score FLOAT DEFAULT 1.0;

-- Pre-generated questions this chunk can answer
-- Enables hypothetical document embedding (HyDE)
ALTER TABLE kb_chunks ADD COLUMN IF NOT EXISTS potential_questions TEXT[];

-- ============================================
-- Forgetting/TTL tracking for memory management
-- ============================================

-- Number of times this chunk was accessed/retrieved
ALTER TABLE kb_chunks ADD COLUMN IF NOT EXISTS access_count INT DEFAULT 0;

-- Timestamp of last access (for LRU-style forgetting)
ALTER TABLE kb_chunks ADD COLUMN IF NOT EXISTS last_accessed TIMESTAMPTZ;

-- Time-to-live in days (chunks can expire)
-- Default 365 days; frequently accessed chunks may get extended
ALTER TABLE kb_chunks ADD COLUMN IF NOT EXISTS ttl_days INT DEFAULT 365;

-- ============================================
-- Performance indexes
-- ============================================

-- Index for quality-based filtering (get high-quality chunks first)
CREATE INDEX IF NOT EXISTS idx_kb_chunks_quality ON kb_chunks(quality_score);

-- Index for access tracking (find stale/unused chunks)
CREATE INDEX IF NOT EXISTS idx_kb_chunks_access ON kb_chunks(access_count);

-- Composite index for forgetting queries (last accessed + TTL)
CREATE INDEX IF NOT EXISTS idx_kb_chunks_forgetting ON kb_chunks(last_accessed, ttl_days);

-- ============================================
-- Helper function to track chunk access
-- ============================================

CREATE OR REPLACE FUNCTION track_chunk_access(chunk_ids UUID[])
RETURNS void AS $$
BEGIN
    UPDATE kb_chunks
    SET access_count = access_count + 1,
        last_accessed = NOW()
    WHERE id = ANY(chunk_ids);
END;
$$ LANGUAGE plpgsql;

-- ============================================
-- Constraint for quality score range (idempotent)
-- ============================================

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'quality_score_range'
    ) THEN
        ALTER TABLE kb_chunks ADD CONSTRAINT quality_score_range
            CHECK (quality_score >= 0.0 AND quality_score <= 1.0);
    END IF;
END $$;
