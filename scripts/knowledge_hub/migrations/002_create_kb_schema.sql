-- 002_create_kb_schema.sql
-- Knowledge Base schema for RAG system

-- Documents table (source files)
CREATE TABLE IF NOT EXISTS kb_documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    file_id TEXT UNIQUE,                    -- Google Drive ID (dedup key)
    title TEXT NOT NULL,
    source_type TEXT NOT NULL,              -- 'google_drive', 'local', 'frappe'
    source_path TEXT,                       -- Original file path/URL
    mime_type TEXT,
    file_size_bytes BIGINT,
    owner_email TEXT,
    shared_with TEXT[],                     -- Array of users with access
    extraction_hash TEXT,                   -- Hash of extraction parameters
    content_hash TEXT,                      -- SHA-256 of extracted content
    category TEXT,                          -- 'mancom', 'hr', 'operations', etc.
    metadata JSONB DEFAULT '{}',
    status TEXT DEFAULT 'pending',          -- 'pending', 'processing', 'completed', 'failed'
    error_message TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Chunks table (text segments with embeddings)
CREATE TABLE IF NOT EXISTS kb_chunks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES kb_documents(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    section_title TEXT,
    content TEXT NOT NULL,
    content_hash TEXT,                      -- SHA-256 of chunk content
    char_count INTEGER,
    embedding vector(768),                  -- Gemini embedding (truncated from 3072)
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Constraints for data integrity
ALTER TABLE kb_chunks ADD CONSTRAINT unique_document_chunk_index
    UNIQUE(document_id, chunk_index);

ALTER TABLE kb_chunks ADD CONSTRAINT chunk_index_positive
    CHECK(chunk_index >= 0);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_kb_documents_file_id ON kb_documents(file_id);
CREATE INDEX IF NOT EXISTS idx_kb_documents_status ON kb_documents(status);
CREATE INDEX IF NOT EXISTS idx_kb_documents_category ON kb_documents(category);
CREATE INDEX IF NOT EXISTS idx_kb_chunks_document_id ON kb_chunks(document_id);
CREATE INDEX IF NOT EXISTS idx_kb_chunks_content_hash ON kb_chunks(content_hash);

-- Vector similarity search index (IVFFlat for performance)
CREATE INDEX IF NOT EXISTS idx_kb_chunks_embedding ON kb_chunks
USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- Update timestamp trigger
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER kb_documents_updated_at
    BEFORE UPDATE ON kb_documents
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at();
