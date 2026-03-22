-- 001_enable_pgvector.sql
-- Enable pgvector extension for vector similarity search
-- Required for RAG (Retrieval-Augmented Generation) knowledge hub

CREATE EXTENSION IF NOT EXISTS vector;

-- Verify extension is enabled
SELECT * FROM pg_extension WHERE extname = 'vector';
