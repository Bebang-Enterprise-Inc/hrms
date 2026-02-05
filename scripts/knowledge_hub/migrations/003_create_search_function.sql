-- 003_create_search_function.sql
-- RPC function for semantic search
-- Task 3: Create match_chunks function for RAG system

CREATE OR REPLACE FUNCTION match_chunks(
    query_embedding vector(768),
    match_threshold FLOAT DEFAULT 0.5,
    match_count INT DEFAULT 5
)
RETURNS TABLE (
    chunk_id UUID,
    document_id UUID,
    document_title TEXT,
    section_title TEXT,
    content TEXT,
    source_path TEXT,
    similarity FLOAT
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
        1 - (c.embedding <=> query_embedding) AS similarity
    FROM kb_chunks c
    JOIN kb_documents d ON c.document_id = d.id
    WHERE d.status = 'completed'
      AND 1 - (c.embedding <=> query_embedding) > match_threshold
    ORDER BY c.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;

-- Add comment for documentation
COMMENT ON FUNCTION match_chunks IS 'Semantic search function for RAG system. Takes a 768-dim query embedding and returns matching chunks above similarity threshold.';
