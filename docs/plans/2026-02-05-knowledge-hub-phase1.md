# Knowledge Hub Phase 1 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a working RAG system that ingests documents into Supabase pgvector and enables semantic search via Claude Code.

**Architecture:** Python ingestion script chunks documents, generates embeddings via Gemini API, stores in Supabase pgvector. Search function retrieves relevant chunks and returns with citations.

**Tech Stack:** Python 3.11+, google-genai SDK, supabase-py, python-pptx, pgvector

---

## Task 1: Enable pgvector Extension in Supabase

**Files:**
- Create: `scripts/knowledge_hub/migrations/001_enable_pgvector.sql`

**Step 1: Create migration file**

```sql
-- 001_enable_pgvector.sql
-- Enable pgvector extension for vector similarity search

CREATE EXTENSION IF NOT EXISTS vector;

-- Verify extension is enabled
SELECT * FROM pg_extension WHERE extname = 'vector';
```

**Step 2: Run migration via Supabase MCP**

Run: Use `mcp__supabase__execute_sql` tool with the SQL above
Expected: Extension created successfully

**Step 3: Verify extension**

Run: `SELECT extversion FROM pg_extension WHERE extname = 'vector';`
Expected: Returns version (e.g., "0.7.0")

**Step 4: Commit**

```bash
git add scripts/knowledge_hub/migrations/001_enable_pgvector.sql
git commit -m "chore: add pgvector extension migration"
```

---

## Task 2: Create Knowledge Base Schema

**Files:**
- Create: `scripts/knowledge_hub/migrations/002_create_kb_schema.sql`

**Step 1: Create schema migration file**

```sql
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
```

**Step 2: Run migration via Supabase MCP**

Run: Use `mcp__supabase__execute_sql` tool with the SQL above
Expected: Tables and indexes created successfully

**Step 3: Verify tables exist**

Run: `SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' AND table_name LIKE 'kb_%';`
Expected: Returns `kb_documents` and `kb_chunks`

**Step 4: Commit**

```bash
git add scripts/knowledge_hub/migrations/002_create_kb_schema.sql
git commit -m "feat: add knowledge base schema with pgvector"
```

---

## Task 3: Create Search RPC Function

**Files:**
- Create: `scripts/knowledge_hub/migrations/003_create_search_function.sql`

**Step 1: Create search function migration**

```sql
-- 003_create_search_function.sql
-- RPC function for semantic search

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
```

**Step 2: Run migration via Supabase MCP**

Run: Use `mcp__supabase__execute_sql` tool with the SQL above
Expected: Function created successfully

**Step 3: Verify function exists**

Run: `SELECT routine_name FROM information_schema.routines WHERE routine_name = 'match_chunks';`
Expected: Returns `match_chunks`

**Step 4: Commit**

```bash
git add scripts/knowledge_hub/migrations/003_create_search_function.sql
git commit -m "feat: add match_chunks RPC for semantic search"
```

---

## Task 4: Create Python Package Structure

**Files:**
- Create: `scripts/knowledge_hub/__init__.py`
- Create: `scripts/knowledge_hub/config.py`
- Create: `scripts/knowledge_hub/requirements.txt`

**Step 1: Create package init**

```python
# scripts/knowledge_hub/__init__.py
"""BEI Knowledge Hub - RAG system for company documents."""

__version__ = "0.1.0"
```

**Step 2: Create config module**

```python
# scripts/knowledge_hub/config.py
"""Configuration for Knowledge Hub."""

import os
from dataclasses import dataclass


@dataclass
class Config:
    """Knowledge Hub configuration."""

    # Supabase
    supabase_url: str = os.getenv("SUPABASE_URL", "")
    supabase_key: str = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")

    # Gemini
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
    embedding_model: str = "gemini-embedding-001"
    embedding_dimensions: int = 768

    # Chunking
    chunk_size: int = 1000  # characters
    chunk_overlap: int = 200  # characters

    # Search
    default_match_count: int = 5
    default_match_threshold: float = 0.5

    def validate(self) -> None:
        """Validate required configuration."""
        missing = []
        if not self.supabase_url:
            missing.append("SUPABASE_URL")
        if not self.supabase_key:
            missing.append("SUPABASE_SERVICE_ROLE_KEY")
        if not self.gemini_api_key:
            missing.append("GEMINI_API_KEY")

        if missing:
            raise ValueError(f"Missing required environment variables: {', '.join(missing)}")


# Global config instance
config = Config()
```

**Step 3: Create requirements file**

```text
# scripts/knowledge_hub/requirements.txt
google-genai>=0.1.0
supabase>=2.0.0
python-pptx>=0.6.21
python-docx>=0.8.11
PyPDF2>=3.0.0
tiktoken>=0.5.0
```

**Step 4: Commit**

```bash
git add scripts/knowledge_hub/__init__.py scripts/knowledge_hub/config.py scripts/knowledge_hub/requirements.txt
git commit -m "feat: add knowledge hub package structure"
```

---

## Task 5: Write Embedding Module with Tests

**Files:**
- Create: `scripts/knowledge_hub/embeddings.py`
- Create: `scripts/knowledge_hub/tests/__init__.py`
- Create: `scripts/knowledge_hub/tests/test_embeddings.py`

**Step 1: Write the failing test**

```python
# scripts/knowledge_hub/tests/__init__.py
"""Tests for Knowledge Hub."""
```

```python
# scripts/knowledge_hub/tests/test_embeddings.py
"""Tests for embedding generation."""

import pytest
from unittest.mock import Mock, patch


def test_generate_embedding_returns_768_dimensions():
    """Embedding should return 768-dimensional vector."""
    from scripts.knowledge_hub.embeddings import generate_embedding

    # Mock the Gemini API response
    mock_response = Mock()
    mock_response.embeddings = [Mock(values=[0.1] * 768)]

    with patch("scripts.knowledge_hub.embeddings.client") as mock_client:
        mock_client.models.embed_content.return_value = mock_response

        result = generate_embedding("test text", task_type="RETRIEVAL_DOCUMENT")

        assert len(result) == 768
        assert all(isinstance(v, float) for v in result)


def test_generate_embedding_uses_correct_task_type():
    """Should pass task_type to Gemini API."""
    from scripts.knowledge_hub.embeddings import generate_embedding

    mock_response = Mock()
    mock_response.embeddings = [Mock(values=[0.1] * 768)]

    with patch("scripts.knowledge_hub.embeddings.client") as mock_client:
        mock_client.models.embed_content.return_value = mock_response

        generate_embedding("test", task_type="RETRIEVAL_QUERY")

        call_args = mock_client.models.embed_content.call_args
        assert call_args.kwargs["config"]["task_type"] == "RETRIEVAL_QUERY"


def test_batch_embeddings_returns_list():
    """Batch embedding should return list of vectors."""
    from scripts.knowledge_hub.embeddings import generate_embeddings_batch

    mock_response = Mock()
    mock_response.embeddings = [Mock(values=[0.1] * 768), Mock(values=[0.2] * 768)]

    with patch("scripts.knowledge_hub.embeddings.client") as mock_client:
        mock_client.models.embed_content.return_value = mock_response

        result = generate_embeddings_batch(["text1", "text2"])

        assert len(result) == 2
        assert len(result[0]) == 768
```

**Step 2: Run test to verify it fails**

Run: `cd scripts/knowledge_hub && python -m pytest tests/test_embeddings.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'scripts.knowledge_hub.embeddings'"

**Step 3: Write minimal implementation**

```python
# scripts/knowledge_hub/embeddings.py
"""Gemini embedding generation for Knowledge Hub."""

import os
from typing import List

from google import genai

from .config import config

# Initialize Gemini client
client = genai.Client(api_key=config.gemini_api_key)


def generate_embedding(
    text: str,
    task_type: str = "RETRIEVAL_DOCUMENT"
) -> List[float]:
    """
    Generate embedding for a single text.

    Args:
        text: Text to embed
        task_type: One of RETRIEVAL_DOCUMENT, RETRIEVAL_QUERY, SEMANTIC_SIMILARITY

    Returns:
        768-dimensional embedding vector
    """
    response = client.models.embed_content(
        model=config.embedding_model,
        contents=text,
        config={"task_type": task_type, "output_dimensionality": config.embedding_dimensions}
    )

    return list(response.embeddings[0].values)


def generate_embeddings_batch(
    texts: List[str],
    task_type: str = "RETRIEVAL_DOCUMENT"
) -> List[List[float]]:
    """
    Generate embeddings for multiple texts in one API call.

    Args:
        texts: List of texts to embed
        task_type: Task type for all texts

    Returns:
        List of 768-dimensional embedding vectors
    """
    response = client.models.embed_content(
        model=config.embedding_model,
        contents=texts,
        config={"task_type": task_type, "output_dimensionality": config.embedding_dimensions}
    )

    return [list(emb.values) for emb in response.embeddings]
```

**Step 4: Run test to verify it passes**

Run: `cd scripts/knowledge_hub && python -m pytest tests/test_embeddings.py -v`
Expected: PASS (3 tests)

**Step 5: Commit**

```bash
git add scripts/knowledge_hub/embeddings.py scripts/knowledge_hub/tests/
git commit -m "feat: add Gemini embedding generation with tests"
```

---

## Task 6: Write Chunking Module with Tests

**Files:**
- Create: `scripts/knowledge_hub/chunker.py`
- Create: `scripts/knowledge_hub/tests/test_chunker.py`

**Step 1: Write the failing test**

```python
# scripts/knowledge_hub/tests/test_chunker.py
"""Tests for text chunking."""

import pytest


def test_chunk_text_respects_size_limit():
    """Chunks should not exceed max size."""
    from scripts.knowledge_hub.chunker import chunk_text

    text = "word " * 500  # 2500 characters
    chunks = chunk_text(text, chunk_size=1000, overlap=200)

    for chunk in chunks:
        assert len(chunk["content"]) <= 1000


def test_chunk_text_has_overlap():
    """Adjacent chunks should have overlapping content."""
    from scripts.knowledge_hub.chunker import chunk_text

    text = "A" * 500 + "B" * 500 + "C" * 500  # 1500 chars
    chunks = chunk_text(text, chunk_size=600, overlap=100)

    # With overlap, chunk 1 end should overlap with chunk 2 start
    assert len(chunks) >= 2
    # Check overlap exists (last 100 chars of chunk 1 should be in chunk 2)
    if len(chunks) >= 2:
        chunk1_end = chunks[0]["content"][-100:]
        assert chunk1_end in chunks[1]["content"]


def test_chunk_text_preserves_all_content():
    """All original content should be in at least one chunk."""
    from scripts.knowledge_hub.chunker import chunk_text

    text = "The quick brown fox jumps over the lazy dog."
    chunks = chunk_text(text, chunk_size=20, overlap=5)

    # Reconstruct by removing overlaps
    all_words = set(text.split())
    chunked_words = set()
    for chunk in chunks:
        chunked_words.update(chunk["content"].split())

    assert all_words.issubset(chunked_words)


def test_chunk_text_returns_metadata():
    """Each chunk should have index and char_count."""
    from scripts.knowledge_hub.chunker import chunk_text

    text = "Hello world " * 100
    chunks = chunk_text(text, chunk_size=500, overlap=50)

    for i, chunk in enumerate(chunks):
        assert chunk["chunk_index"] == i
        assert chunk["char_count"] == len(chunk["content"])
        assert "content" in chunk
```

**Step 2: Run test to verify it fails**

Run: `cd scripts/knowledge_hub && python -m pytest tests/test_chunker.py -v`
Expected: FAIL with "ModuleNotFoundError"

**Step 3: Write minimal implementation**

```python
# scripts/knowledge_hub/chunker.py
"""Text chunking for Knowledge Hub."""

from typing import List, Dict, Any

from .config import config


def chunk_text(
    text: str,
    chunk_size: int = None,
    overlap: int = None,
    separators: List[str] = None
) -> List[Dict[str, Any]]:
    """
    Split text into overlapping chunks.

    Args:
        text: Text to chunk
        chunk_size: Max characters per chunk (default from config)
        overlap: Characters of overlap between chunks (default from config)
        separators: Preferred split points (default: paragraph, sentence, word)

    Returns:
        List of chunk dicts with content, chunk_index, char_count
    """
    chunk_size = chunk_size or config.chunk_size
    overlap = overlap or config.chunk_overlap
    separators = separators or ["\n\n", "\n", ". ", " "]

    if len(text) <= chunk_size:
        return [{"content": text, "chunk_index": 0, "char_count": len(text)}]

    chunks = []
    start = 0
    chunk_index = 0

    while start < len(text):
        # Determine end position
        end = min(start + chunk_size, len(text))

        # If not at the end, try to break at a separator
        if end < len(text):
            # Look for best separator within the chunk
            best_break = end
            for sep in separators:
                # Search backwards from end for separator
                search_start = max(start + chunk_size // 2, start)  # Don't break too early
                last_sep = text.rfind(sep, search_start, end)
                if last_sep != -1:
                    best_break = last_sep + len(sep)
                    break
            end = best_break

        chunk_content = text[start:end].strip()
        if chunk_content:
            chunks.append({
                "content": chunk_content,
                "chunk_index": chunk_index,
                "char_count": len(chunk_content)
            })
            chunk_index += 1

        # Move start with overlap
        start = end - overlap if end < len(text) else end

        # Prevent infinite loop
        if start >= len(text):
            break

    return chunks


def chunk_document(
    content: str,
    title: str = None,
    sections: List[Dict[str, str]] = None
) -> List[Dict[str, Any]]:
    """
    Chunk a document, preserving section context.

    Args:
        content: Full document text
        title: Document title (added to metadata)
        sections: List of {"title": str, "content": str} for section-aware chunking

    Returns:
        List of chunks with section_title metadata
    """
    if sections:
        all_chunks = []
        chunk_index = 0
        for section in sections:
            section_chunks = chunk_text(section.get("content", ""))
            for chunk in section_chunks:
                chunk["section_title"] = section.get("title")
                chunk["chunk_index"] = chunk_index
                chunk_index += 1
                all_chunks.append(chunk)
        return all_chunks

    return chunk_text(content)
```

**Step 4: Run test to verify it passes**

Run: `cd scripts/knowledge_hub && python -m pytest tests/test_chunker.py -v`
Expected: PASS (4 tests)

**Step 5: Commit**

```bash
git add scripts/knowledge_hub/chunker.py scripts/knowledge_hub/tests/test_chunker.py
git commit -m "feat: add text chunking with overlap support"
```

---

## Task 7: Write Supabase Storage Module with Tests

**Files:**
- Create: `scripts/knowledge_hub/storage.py`
- Create: `scripts/knowledge_hub/tests/test_storage.py`

**Step 1: Write the failing test**

```python
# scripts/knowledge_hub/tests/test_storage.py
"""Tests for Supabase storage."""

import pytest
from unittest.mock import Mock, patch, MagicMock
import uuid


def test_store_document_returns_id():
    """Storing document should return UUID."""
    from scripts.knowledge_hub.storage import store_document

    mock_response = MagicMock()
    mock_response.data = [{"id": str(uuid.uuid4())}]

    with patch("scripts.knowledge_hub.storage.supabase") as mock_sb:
        mock_sb.table.return_value.insert.return_value.execute.return_value = mock_response

        doc_id = store_document(
            title="Test Doc",
            source_type="local",
            source_path="/test/path.txt"
        )

        assert doc_id is not None
        assert isinstance(doc_id, str)


def test_store_chunks_with_embeddings():
    """Should store chunks with their embeddings."""
    from scripts.knowledge_hub.storage import store_chunks

    mock_response = MagicMock()
    mock_response.data = [{"id": str(uuid.uuid4())}, {"id": str(uuid.uuid4())}]

    with patch("scripts.knowledge_hub.storage.supabase") as mock_sb:
        mock_sb.table.return_value.insert.return_value.execute.return_value = mock_response

        chunks = [
            {"content": "chunk 1", "chunk_index": 0, "char_count": 7},
            {"content": "chunk 2", "chunk_index": 1, "char_count": 7}
        ]
        embeddings = [[0.1] * 768, [0.2] * 768]

        chunk_ids = store_chunks("doc-123", chunks, embeddings)

        assert len(chunk_ids) == 2


def test_document_exists_by_file_id():
    """Should check if document already exists."""
    from scripts.knowledge_hub.storage import document_exists

    mock_response = MagicMock()
    mock_response.data = [{"id": "existing-id"}]

    with patch("scripts.knowledge_hub.storage.supabase") as mock_sb:
        mock_sb.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_response

        exists = document_exists(file_id="drive-file-123")

        assert exists is True


def test_search_returns_results():
    """Search should return matching chunks."""
    from scripts.knowledge_hub.storage import search_chunks

    mock_response = MagicMock()
    mock_response.data = [
        {
            "chunk_id": str(uuid.uuid4()),
            "document_title": "Test Doc",
            "content": "relevant content",
            "similarity": 0.85
        }
    ]

    with patch("scripts.knowledge_hub.storage.supabase") as mock_sb:
        mock_sb.rpc.return_value.execute.return_value = mock_response

        results = search_chunks([0.1] * 768)

        assert len(results) == 1
        assert results[0]["similarity"] == 0.85
```

**Step 2: Run test to verify it fails**

Run: `cd scripts/knowledge_hub && python -m pytest tests/test_storage.py -v`
Expected: FAIL with "ModuleNotFoundError"

**Step 3: Write minimal implementation**

```python
# scripts/knowledge_hub/storage.py
"""Supabase storage for Knowledge Hub."""

import hashlib
from typing import List, Dict, Any, Optional

from supabase import create_client

from .config import config

# Initialize Supabase client
supabase = create_client(config.supabase_url, config.supabase_key)


def store_document(
    title: str,
    source_type: str,
    source_path: str,
    file_id: str = None,
    mime_type: str = None,
    file_size_bytes: int = None,
    owner_email: str = None,
    category: str = None,
    metadata: Dict = None
) -> str:
    """
    Store a document record.

    Returns:
        Document UUID
    """
    doc_data = {
        "title": title,
        "source_type": source_type,
        "source_path": source_path,
        "file_id": file_id,
        "mime_type": mime_type,
        "file_size_bytes": file_size_bytes,
        "owner_email": owner_email,
        "category": category,
        "metadata": metadata or {},
        "status": "processing"
    }

    response = supabase.table("kb_documents").insert(doc_data).execute()
    return response.data[0]["id"]


def store_chunks(
    document_id: str,
    chunks: List[Dict[str, Any]],
    embeddings: List[List[float]]
) -> List[str]:
    """
    Store chunks with their embeddings.

    Returns:
        List of chunk UUIDs
    """
    chunk_records = []
    for chunk, embedding in zip(chunks, embeddings):
        content_hash = hashlib.sha256(chunk["content"].encode()).hexdigest()
        chunk_records.append({
            "document_id": document_id,
            "chunk_index": chunk["chunk_index"],
            "section_title": chunk.get("section_title"),
            "content": chunk["content"],
            "content_hash": content_hash,
            "char_count": chunk["char_count"],
            "embedding": embedding
        })

    response = supabase.table("kb_chunks").insert(chunk_records).execute()
    return [r["id"] for r in response.data]


def update_document_status(document_id: str, status: str, error_message: str = None) -> None:
    """Update document processing status."""
    update_data = {"status": status}
    if error_message:
        update_data["error_message"] = error_message

    supabase.table("kb_documents").update(update_data).eq("id", document_id).execute()


def document_exists(file_id: str) -> bool:
    """Check if document already exists by file_id."""
    response = supabase.table("kb_documents").select("id").eq("file_id", file_id).execute()
    return len(response.data) > 0


def search_chunks(
    query_embedding: List[float],
    match_count: int = None,
    match_threshold: float = None
) -> List[Dict[str, Any]]:
    """
    Search for similar chunks using vector similarity.

    Returns:
        List of matching chunks with similarity scores
    """
    match_count = match_count or config.default_match_count
    match_threshold = match_threshold or config.default_match_threshold

    response = supabase.rpc(
        "match_chunks",
        {
            "query_embedding": query_embedding,
            "match_count": match_count,
            "match_threshold": match_threshold
        }
    ).execute()

    return response.data
```

**Step 4: Run test to verify it passes**

Run: `cd scripts/knowledge_hub && python -m pytest tests/test_storage.py -v`
Expected: PASS (4 tests)

**Step 5: Commit**

```bash
git add scripts/knowledge_hub/storage.py scripts/knowledge_hub/tests/test_storage.py
git commit -m "feat: add Supabase storage with search"
```

---

## Task 8: Write Document Extractors

**Files:**
- Create: `scripts/knowledge_hub/extractors/__init__.py`
- Create: `scripts/knowledge_hub/extractors/pptx.py`
- Create: `scripts/knowledge_hub/tests/test_extractors.py`

**Step 1: Write the failing test**

```python
# scripts/knowledge_hub/tests/test_extractors.py
"""Tests for document extractors."""

import pytest
from unittest.mock import Mock, patch, MagicMock


def test_pptx_extractor_returns_slides():
    """PPTX extractor should return slide content."""
    from scripts.knowledge_hub.extractors.pptx import extract_pptx

    # Create mock presentation
    mock_shape = Mock()
    mock_shape.has_text_frame = True
    mock_shape.text = "Slide content"

    mock_slide = Mock()
    mock_slide.shapes = [mock_shape]
    mock_slide.has_notes_slide = False

    mock_prs = Mock()
    mock_prs.slides = [mock_slide]

    with patch("scripts.knowledge_hub.extractors.pptx.Presentation", return_value=mock_prs):
        result = extract_pptx("/fake/path.pptx")

        assert "slides" in result
        assert len(result["slides"]) == 1
        assert "Slide content" in result["slides"][0]["content"]


def test_pptx_extractor_includes_speaker_notes():
    """PPTX extractor should include speaker notes."""
    from scripts.knowledge_hub.extractors.pptx import extract_pptx

    mock_shape = Mock()
    mock_shape.has_text_frame = True
    mock_shape.text = "Slide"

    mock_notes_frame = Mock()
    mock_notes_frame.text = "Speaker notes here"

    mock_notes_slide = Mock()
    mock_notes_slide.notes_text_frame = mock_notes_frame

    mock_slide = Mock()
    mock_slide.shapes = [mock_shape]
    mock_slide.has_notes_slide = True
    mock_slide.notes_slide = mock_notes_slide

    mock_prs = Mock()
    mock_prs.slides = [mock_slide]

    with patch("scripts.knowledge_hub.extractors.pptx.Presentation", return_value=mock_prs):
        result = extract_pptx("/fake/path.pptx")

        assert "speaker_notes" in result
        assert len(result["speaker_notes"]) == 1
        assert "Speaker notes here" in result["speaker_notes"][0]["notes"]
```

**Step 2: Run test to verify it fails**

Run: `cd scripts/knowledge_hub && python -m pytest tests/test_extractors.py -v`
Expected: FAIL with "ModuleNotFoundError"

**Step 3: Write minimal implementation**

```python
# scripts/knowledge_hub/extractors/__init__.py
"""Document extractors for various file types."""

from .pptx import extract_pptx

__all__ = ["extract_pptx"]
```

```python
# scripts/knowledge_hub/extractors/pptx.py
"""PowerPoint extraction for Knowledge Hub."""

from typing import Dict, Any, List
from pptx import Presentation


def extract_pptx(file_path: str) -> Dict[str, Any]:
    """
    Extract text content from PowerPoint file.

    Args:
        file_path: Path to .pptx file

    Returns:
        Dict with slides content and speaker notes
    """
    prs = Presentation(file_path)

    result = {
        "slides": [],
        "speaker_notes": [],
        "metadata": {
            "slide_count": len(prs.slides)
        }
    }

    for slide_num, slide in enumerate(prs.slides, 1):
        slide_text = []

        for shape in slide.shapes:
            if hasattr(shape, "text") and shape.text.strip():
                slide_text.append(shape.text)

        if slide_text:
            result["slides"].append({
                "slide_num": slide_num,
                "content": "\n".join(slide_text)
            })

        # Extract speaker notes
        if slide.has_notes_slide:
            notes = slide.notes_slide.notes_text_frame.text
            if notes.strip():
                result["speaker_notes"].append({
                    "slide_num": slide_num,
                    "notes": notes.strip()
                })

    return result


def pptx_to_text(file_path: str, include_notes: bool = True) -> str:
    """
    Convert PPTX to plain text for chunking.

    Args:
        file_path: Path to .pptx file
        include_notes: Whether to include speaker notes

    Returns:
        Plain text content
    """
    extracted = extract_pptx(file_path)

    sections = []
    for slide in extracted["slides"]:
        sections.append(f"--- Slide {slide['slide_num']} ---\n{slide['content']}")

    if include_notes and extracted["speaker_notes"]:
        sections.append("\n--- Speaker Notes ---")
        for note in extracted["speaker_notes"]:
            sections.append(f"Slide {note['slide_num']}: {note['notes']}")

    return "\n\n".join(sections)
```

**Step 4: Run test to verify it passes**

Run: `cd scripts/knowledge_hub && python -m pytest tests/test_extractors.py -v`
Expected: PASS (2 tests)

**Step 5: Commit**

```bash
git add scripts/knowledge_hub/extractors/
git commit -m "feat: add PPTX extractor with speaker notes"
```

---

## Task 9: Write Main Ingestion Pipeline

**Files:**
- Create: `scripts/knowledge_hub/ingest.py`
- Create: `scripts/knowledge_hub/tests/test_ingest.py`

**Step 1: Write the failing test**

```python
# scripts/knowledge_hub/tests/test_ingest.py
"""Tests for ingestion pipeline."""

import pytest
from unittest.mock import Mock, patch, MagicMock


def test_ingest_local_file_creates_document():
    """Ingesting local file should create document and chunks."""
    from scripts.knowledge_hub.ingest import ingest_local_file

    with patch("scripts.knowledge_hub.ingest.extract_content") as mock_extract, \
         patch("scripts.knowledge_hub.ingest.chunk_text") as mock_chunk, \
         patch("scripts.knowledge_hub.ingest.generate_embeddings_batch") as mock_embed, \
         patch("scripts.knowledge_hub.ingest.store_document") as mock_store_doc, \
         patch("scripts.knowledge_hub.ingest.store_chunks") as mock_store_chunks, \
         patch("scripts.knowledge_hub.ingest.update_document_status") as mock_update:

        mock_extract.return_value = "Document content"
        mock_chunk.return_value = [{"content": "chunk", "chunk_index": 0, "char_count": 5}]
        mock_embed.return_value = [[0.1] * 768]
        mock_store_doc.return_value = "doc-123"
        mock_store_chunks.return_value = ["chunk-456"]

        result = ingest_local_file("/test/file.pptx", category="mancom")

        assert result["document_id"] == "doc-123"
        assert result["chunks_created"] == 1
        mock_update.assert_called_with("doc-123", "completed", None)


def test_ingest_skips_existing_file():
    """Should skip if file already ingested (by file_id)."""
    from scripts.knowledge_hub.ingest import ingest_drive_file

    with patch("scripts.knowledge_hub.ingest.document_exists") as mock_exists:
        mock_exists.return_value = True

        result = ingest_drive_file(file_id="existing-123", title="Test")

        assert result["skipped"] is True
        assert "already exists" in result["reason"]
```

**Step 2: Run test to verify it fails**

Run: `cd scripts/knowledge_hub && python -m pytest tests/test_ingest.py -v`
Expected: FAIL with "ModuleNotFoundError"

**Step 3: Write minimal implementation**

```python
# scripts/knowledge_hub/ingest.py
"""Document ingestion pipeline for Knowledge Hub."""

import os
import hashlib
from pathlib import Path
from typing import Dict, Any, Optional

from .chunker import chunk_text
from .embeddings import generate_embeddings_batch
from .storage import store_document, store_chunks, update_document_status, document_exists
from .extractors import extract_pptx


def extract_content(file_path: str) -> str:
    """
    Extract text content from file based on extension.

    Args:
        file_path: Path to file

    Returns:
        Extracted text content
    """
    ext = Path(file_path).suffix.lower()

    if ext == ".pptx":
        from .extractors.pptx import pptx_to_text
        return pptx_to_text(file_path)
    elif ext == ".txt":
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    elif ext == ".md":
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    else:
        raise ValueError(f"Unsupported file type: {ext}")


def ingest_local_file(
    file_path: str,
    category: str = None,
    metadata: Dict = None
) -> Dict[str, Any]:
    """
    Ingest a local file into the knowledge base.

    Args:
        file_path: Path to local file
        category: Document category (e.g., 'mancom', 'hr')
        metadata: Additional metadata

    Returns:
        Dict with document_id and chunks_created
    """
    path = Path(file_path)

    # Create document record
    doc_id = store_document(
        title=path.name,
        source_type="local",
        source_path=str(path.absolute()),
        mime_type=_get_mime_type(path.suffix),
        file_size_bytes=path.stat().st_size,
        category=category,
        metadata=metadata
    )

    try:
        # Extract content
        content = extract_content(file_path)

        # Chunk content
        chunks = chunk_text(content)

        # Generate embeddings
        chunk_texts = [c["content"] for c in chunks]
        embeddings = generate_embeddings_batch(chunk_texts, task_type="RETRIEVAL_DOCUMENT")

        # Store chunks
        chunk_ids = store_chunks(doc_id, chunks, embeddings)

        # Update status
        update_document_status(doc_id, "completed")

        return {
            "document_id": doc_id,
            "chunks_created": len(chunk_ids),
            "skipped": False
        }

    except Exception as e:
        update_document_status(doc_id, "failed", str(e))
        raise


def ingest_drive_file(
    file_id: str,
    title: str,
    source_path: str = None,
    mime_type: str = None,
    owner_email: str = None,
    category: str = None,
    local_path: str = None
) -> Dict[str, Any]:
    """
    Ingest a Google Drive file into the knowledge base.

    Args:
        file_id: Google Drive file ID (used for deduplication)
        title: File title
        source_path: Google Drive URL/path
        local_path: Path to downloaded file (if already downloaded)

    Returns:
        Dict with document_id, chunks_created, or skipped status
    """
    # Check for existing document
    if document_exists(file_id):
        return {
            "skipped": True,
            "reason": f"Document already exists with file_id: {file_id}"
        }

    # Create document record
    doc_id = store_document(
        title=title,
        source_type="google_drive",
        source_path=source_path or f"https://drive.google.com/file/d/{file_id}",
        file_id=file_id,
        mime_type=mime_type,
        owner_email=owner_email,
        category=category
    )

    if not local_path:
        # TODO: Download file from Google Drive
        update_document_status(doc_id, "failed", "local_path required - Drive download not implemented")
        return {"document_id": doc_id, "skipped": True, "reason": "Drive download not implemented"}

    try:
        # Extract content
        content = extract_content(local_path)

        # Chunk content
        chunks = chunk_text(content)

        # Generate embeddings
        chunk_texts = [c["content"] for c in chunks]
        embeddings = generate_embeddings_batch(chunk_texts, task_type="RETRIEVAL_DOCUMENT")

        # Store chunks
        chunk_ids = store_chunks(doc_id, chunks, embeddings)

        # Update status
        update_document_status(doc_id, "completed")

        return {
            "document_id": doc_id,
            "chunks_created": len(chunk_ids),
            "skipped": False
        }

    except Exception as e:
        update_document_status(doc_id, "failed", str(e))
        raise


def _get_mime_type(suffix: str) -> str:
    """Get MIME type from file suffix."""
    mime_types = {
        ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".pdf": "application/pdf",
        ".txt": "text/plain",
        ".md": "text/markdown"
    }
    return mime_types.get(suffix.lower(), "application/octet-stream")
```

**Step 4: Run test to verify it passes**

Run: `cd scripts/knowledge_hub && python -m pytest tests/test_ingest.py -v`
Expected: PASS (2 tests)

**Step 5: Commit**

```bash
git add scripts/knowledge_hub/ingest.py scripts/knowledge_hub/tests/test_ingest.py
git commit -m "feat: add document ingestion pipeline"
```

---

## Task 10: Write Search/Query Interface

**Files:**
- Create: `scripts/knowledge_hub/search.py`
- Create: `scripts/knowledge_hub/tests/test_search.py`

**Step 1: Write the failing test**

```python
# scripts/knowledge_hub/tests/test_search.py
"""Tests for search interface."""

import pytest
from unittest.mock import Mock, patch


def test_search_returns_formatted_results():
    """Search should return formatted results with citations."""
    from scripts.knowledge_hub.search import search

    mock_chunks = [
        {
            "document_title": "Test Doc",
            "content": "relevant content here",
            "source_path": "/path/to/doc.pptx",
            "similarity": 0.85
        }
    ]

    with patch("scripts.knowledge_hub.search.generate_embedding") as mock_embed, \
         patch("scripts.knowledge_hub.search.search_chunks") as mock_search:

        mock_embed.return_value = [0.1] * 768
        mock_search.return_value = mock_chunks

        results = search("test query")

        assert len(results) == 1
        assert results[0]["title"] == "Test Doc"
        assert results[0]["score"] == 0.85
        mock_embed.assert_called_with("test query", task_type="RETRIEVAL_QUERY")


def test_search_with_no_results():
    """Search with no matches should return empty list."""
    from scripts.knowledge_hub.search import search

    with patch("scripts.knowledge_hub.search.generate_embedding") as mock_embed, \
         patch("scripts.knowledge_hub.search.search_chunks") as mock_search:

        mock_embed.return_value = [0.1] * 768
        mock_search.return_value = []

        results = search("obscure query")

        assert results == []
```

**Step 2: Run test to verify it fails**

Run: `cd scripts/knowledge_hub && python -m pytest tests/test_search.py -v`
Expected: FAIL with "ModuleNotFoundError"

**Step 3: Write minimal implementation**

```python
# scripts/knowledge_hub/search.py
"""Search interface for Knowledge Hub."""

from typing import List, Dict, Any

from .embeddings import generate_embedding
from .storage import search_chunks


def search(
    query: str,
    top_k: int = 5,
    threshold: float = 0.5
) -> List[Dict[str, Any]]:
    """
    Search the knowledge base.

    Args:
        query: Natural language search query
        top_k: Maximum number of results
        threshold: Minimum similarity score

    Returns:
        List of results with title, content, source, and score
    """
    # Generate query embedding
    query_embedding = generate_embedding(query, task_type="RETRIEVAL_QUERY")

    # Search for similar chunks
    chunks = search_chunks(query_embedding, match_count=top_k, match_threshold=threshold)

    # Format results
    results = []
    for chunk in chunks:
        results.append({
            "title": chunk.get("document_title", "Unknown"),
            "section": chunk.get("section_title"),
            "content": chunk.get("content", ""),
            "source": chunk.get("source_path", ""),
            "score": chunk.get("similarity", 0.0)
        })

    return results


def search_with_context(
    query: str,
    top_k: int = 5
) -> Dict[str, Any]:
    """
    Search and format results for RAG context.

    Returns:
        Dict with context string and sources list
    """
    results = search(query, top_k=top_k)

    if not results:
        return {
            "context": "No relevant documents found.",
            "sources": []
        }

    context_parts = []
    sources = []

    for i, result in enumerate(results, 1):
        context_parts.append(f"[{i}] {result['title']}")
        if result.get("section"):
            context_parts.append(f"    Section: {result['section']}")
        context_parts.append(f"    {result['content']}")
        context_parts.append("")

        sources.append({
            "citation": f"[{i}]",
            "title": result["title"],
            "source": result["source"],
            "score": result["score"]
        })

    return {
        "context": "\n".join(context_parts),
        "sources": sources
    }
```

**Step 4: Run test to verify it passes**

Run: `cd scripts/knowledge_hub && python -m pytest tests/test_search.py -v`
Expected: PASS (2 tests)

**Step 5: Commit**

```bash
git add scripts/knowledge_hub/search.py scripts/knowledge_hub/tests/test_search.py
git commit -m "feat: add search interface with citations"
```

---

## Task 11: Write CLI for Testing

**Files:**
- Create: `scripts/knowledge_hub/cli.py`

**Step 1: Create CLI**

```python
# scripts/knowledge_hub/cli.py
"""CLI for Knowledge Hub operations."""

import argparse
import json
import sys
from pathlib import Path


def cmd_ingest(args):
    """Ingest a local file."""
    from .ingest import ingest_local_file

    result = ingest_local_file(args.file, category=args.category)
    print(json.dumps(result, indent=2))


def cmd_search(args):
    """Search the knowledge base."""
    from .search import search_with_context

    result = search_with_context(args.query, top_k=args.top_k)

    print("=" * 60)
    print("CONTEXT:")
    print("=" * 60)
    print(result["context"])
    print()
    print("=" * 60)
    print("SOURCES:")
    print("=" * 60)
    for source in result["sources"]:
        print(f"  {source['citation']} {source['title']} (score: {source['score']:.2f})")
        print(f"      {source['source']}")


def cmd_stats(args):
    """Show knowledge base statistics."""
    from .storage import supabase

    docs = supabase.table("kb_documents").select("id, status", count="exact").execute()
    chunks = supabase.table("kb_chunks").select("id", count="exact").execute()

    print(f"Documents: {docs.count}")
    print(f"Chunks: {chunks.count}")

    # Status breakdown
    by_status = supabase.table("kb_documents").select("status").execute()
    status_counts = {}
    for doc in by_status.data:
        s = doc["status"]
        status_counts[s] = status_counts.get(s, 0) + 1

    print("\nBy Status:")
    for status, count in status_counts.items():
        print(f"  {status}: {count}")


def main():
    parser = argparse.ArgumentParser(description="Knowledge Hub CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Ingest command
    ingest_parser = subparsers.add_parser("ingest", help="Ingest a local file")
    ingest_parser.add_argument("file", help="Path to file")
    ingest_parser.add_argument("--category", help="Document category")
    ingest_parser.set_defaults(func=cmd_ingest)

    # Search command
    search_parser = subparsers.add_parser("search", help="Search knowledge base")
    search_parser.add_argument("query", help="Search query")
    search_parser.add_argument("--top-k", type=int, default=5, help="Max results")
    search_parser.set_defaults(func=cmd_search)

    # Stats command
    stats_parser = subparsers.add_parser("stats", help="Show statistics")
    stats_parser.set_defaults(func=cmd_stats)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
```

**Step 2: Test CLI help**

Run: `cd scripts/knowledge_hub && python -m cli --help`
Expected: Shows CLI help with ingest, search, stats commands

**Step 3: Commit**

```bash
git add scripts/knowledge_hub/cli.py
git commit -m "feat: add CLI for knowledge hub operations"
```

---

## Task 12: Integration Test with Sample Document

**Files:**
- Use existing: `CEO/Weekly Reports/26.02.03 - Status report.pptx` (Arnold's R&D report)

**Step 1: Install dependencies**

Run: `pip install -r scripts/knowledge_hub/requirements.txt`
Expected: All packages installed successfully

**Step 2: Set environment variables**

Run: `doppler run --project bei-erp --config dev -- echo "Credentials loaded"`
Expected: "Credentials loaded"

**Step 3: Run migrations (if not already done)**

Run: Use Supabase MCP to execute all 3 migration files
Expected: Tables and functions created

**Step 4: Ingest test document**

Run: `doppler run --project bei-erp --config dev -- python -m scripts.knowledge_hub.cli ingest "CEO/Weekly Reports/26.02.03 - Status report.pptx" --category mancom`

Expected:
```json
{
  "document_id": "uuid-here",
  "chunks_created": 5,
  "skipped": false
}
```

**Step 5: Search test**

Run: `doppler run --project bei-erp --config dev -- python -m scripts.knowledge_hub.cli search "R&D status update"`

Expected: Returns chunks from the ingested document with similarity scores

**Step 6: View stats**

Run: `doppler run --project bei-erp --config dev -- python -m scripts.knowledge_hub.cli stats`

Expected:
```
Documents: 1
Chunks: N
By Status:
  completed: 1
```

**Step 7: Commit integration test results**

```bash
git add .
git commit -m "test: verify end-to-end ingestion and search"
```

---

## Summary

| Task | Component | Tests |
|------|-----------|-------|
| 1 | pgvector extension | - |
| 2 | KB schema | - |
| 3 | Search RPC | - |
| 4 | Package structure | - |
| 5 | Embeddings | 3 |
| 6 | Chunker | 4 |
| 7 | Storage | 4 |
| 8 | PPTX extractor | 2 |
| 9 | Ingest pipeline | 2 |
| 10 | Search interface | 2 |
| 11 | CLI | - |
| 12 | Integration test | - |
| **Total** | **12 tasks** | **17 tests** |

## Dependencies

```
google-genai>=0.1.0
supabase>=2.0.0
python-pptx>=0.6.21
python-docx>=0.8.11
PyPDF2>=3.0.0
tiktoken>=0.5.0
pytest>=7.0.0
```

## Environment Variables Required

```
SUPABASE_URL
SUPABASE_SERVICE_ROLE_KEY
GEMINI_API_KEY
```

All available in Doppler: `bei-erp/dev`

---

# Phase 2: Enhanced RAG with Recency, Metadata & Quality Scoring

> **Research-backed enhancements** from 2025-2026 studies on context rot, AI forgetting, and RAG optimization.

**Goal:** Improve retrieval quality by adding recency weighting, LLM-generated metadata, chunk quality scoring, and selective forgetting.

**Key Research Sources:**
- [Chroma: Context Rot Study (July 2025)](https://research.trychroma.com/context-rot)
- [arXiv: Recency Prior for RAG (2509.19376)](https://arxiv.org/html/2509.19376)
- [arXiv: ChunkRAG Filtering (2410.19572)](https://arxiv.org/abs/2410.19572)
- [arXiv: Dynamic RAG with Selective Memory (2601.02428)](https://arxiv.org/abs/2601.02428)

**Tech Stack:** Same as Phase 1 (Supabase pgvector + Gemini) - no new services required.

---

## Task 13: Add Schema Fields for Metadata & Quality

**Files:**
- Create: `scripts/knowledge_hub/migrations/004_add_metadata_fields.sql`

**Step 1: Create migration file**

```sql
-- 004_add_metadata_fields.sql
-- Add metadata, quality scoring, and forgetting fields

-- Document-level metadata
ALTER TABLE kb_documents ADD COLUMN IF NOT EXISTS summary TEXT;
ALTER TABLE kb_documents ADD COLUMN IF NOT EXISTS keywords TEXT[];
ALTER TABLE kb_documents ADD COLUMN IF NOT EXISTS entities JSONB DEFAULT '[]';

-- Chunk-level enhancements
ALTER TABLE kb_chunks ADD COLUMN IF NOT EXISTS summary TEXT;
ALTER TABLE kb_chunks ADD COLUMN IF NOT EXISTS keywords TEXT[];
ALTER TABLE kb_chunks ADD COLUMN IF NOT EXISTS quality_score FLOAT DEFAULT 1.0;
ALTER TABLE kb_chunks ADD COLUMN IF NOT EXISTS potential_questions TEXT[];

-- Forgetting/TTL tracking
ALTER TABLE kb_chunks ADD COLUMN IF NOT EXISTS access_count INT DEFAULT 0;
ALTER TABLE kb_chunks ADD COLUMN IF NOT EXISTS last_accessed TIMESTAMPTZ;
ALTER TABLE kb_chunks ADD COLUMN IF NOT EXISTS ttl_days INT DEFAULT 365;

-- Index for quality filtering
CREATE INDEX IF NOT EXISTS idx_kb_chunks_quality ON kb_chunks(quality_score);
CREATE INDEX IF NOT EXISTS idx_kb_chunks_access ON kb_chunks(access_count);
```

**Step 2: Run migration via Supabase MCP**

Run: Use `mcp__supabase__execute_sql` with the SQL above
Expected: Columns added successfully

**Step 3: Commit**

```bash
git add scripts/knowledge_hub/migrations/004_add_metadata_fields.sql
git commit -m "feat: add metadata, quality, and forgetting fields"
```

---

## Task 14: Update Search Function with Recency Scoring

**Files:**
- Modify: `scripts/knowledge_hub/migrations/005_search_with_recency.sql`

**Step 1: Create updated search function**

```sql
-- 005_search_with_recency.sql
-- Search with recency weighting (half-life decay)

CREATE OR REPLACE FUNCTION match_chunks_with_recency(
    query_embedding vector(768),
    match_threshold FLOAT DEFAULT 0.5,
    match_count INT DEFAULT 5,
    decay_rate FLOAT DEFAULT 0.01,  -- Higher = faster decay
    recency_weight FLOAT DEFAULT 0.3  -- 0-1, how much recency matters
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

-- Update access tracking on search
CREATE OR REPLACE FUNCTION track_chunk_access(chunk_ids UUID[])
RETURNS VOID
LANGUAGE plpgsql
AS $$
BEGIN
    UPDATE kb_chunks
    SET
        access_count = access_count + 1,
        last_accessed = NOW()
    WHERE id = ANY(chunk_ids);
END;
$$;
```

**Step 2: Run migration**

**Step 3: Commit**

```bash
git add scripts/knowledge_hub/migrations/005_search_with_recency.sql
git commit -m "feat: add recency-weighted search function"
```

---

## Task 15: Write Metadata Generation Module

**Files:**
- Create: `scripts/knowledge_hub/metadata.py`
- Create: `scripts/knowledge_hub/tests/test_metadata.py`

**Step 1: Write the failing test**

```python
# scripts/knowledge_hub/tests/test_metadata.py
"""Tests for metadata generation."""

import pytest
from unittest.mock import Mock, patch


def test_generate_chunk_metadata_returns_expected_fields():
    """Should return summary, keywords, and potential questions."""
    from scripts.knowledge_hub.metadata import generate_chunk_metadata

    mock_response = Mock()
    mock_response.text = '''
    {
        "summary": "This chunk describes R&D projects",
        "keywords": ["R&D", "frozen milk", "toller"],
        "potential_questions": ["What R&D projects are active?"],
        "quality_score": 0.85
    }
    '''

    with patch("scripts.knowledge_hub.metadata.model") as mock_model:
        mock_model.generate_content.return_value = mock_response

        result = generate_chunk_metadata("R&D Status Update content...")

        assert "summary" in result
        assert "keywords" in result
        assert "potential_questions" in result
        assert "quality_score" in result
        assert 0 <= result["quality_score"] <= 1


def test_generate_document_metadata():
    """Should generate document-level summary and entities."""
    from scripts.knowledge_hub.metadata import generate_document_metadata

    mock_response = Mock()
    mock_response.text = '''
    {
        "summary": "Weekly R&D status report covering toller projects",
        "keywords": ["R&D", "weekly report", "toller"],
        "entities": [
            {"type": "Organization", "name": "Griffith"},
            {"type": "Product", "name": "Frozen Milk"}
        ]
    }
    '''

    with patch("scripts.knowledge_hub.metadata.model") as mock_model:
        mock_model.generate_content.return_value = mock_response

        result = generate_document_metadata("Full document content...", "R&D Report")

        assert "summary" in result
        assert "entities" in result
        assert len(result["entities"]) > 0
```

**Step 2: Write implementation**

```python
# scripts/knowledge_hub/metadata.py
"""LLM-powered metadata generation for Knowledge Hub.

Uses Gemini to generate:
- Summaries (1-2 sentences)
- Keywords (5-10 relevant terms)
- Potential questions (what this chunk can answer)
- Quality score (0-1, how useful/relevant the content is)
- Named entities (people, organizations, products)
"""

import json
import re
from typing import Dict, Any, List

from google import genai

from .config import config

# Initialize Gemini client for generation (not embedding)
client = genai.Client(api_key=config.gemini_api_key)
model = client.models


CHUNK_METADATA_PROMPT = '''Analyze this text chunk and return JSON with:
- summary: 1-2 sentence summary of the content
- keywords: 5-10 relevant keywords/phrases (lowercase)
- potential_questions: 2-3 questions this chunk could answer
- quality_score: 0.0-1.0 rating (1.0 = highly informative, 0.0 = noise/boilerplate)

Quality scoring guide:
- 1.0: Specific facts, data, decisions, action items
- 0.7-0.9: Useful context, explanations, summaries
- 0.4-0.6: General info, some value
- 0.1-0.3: Boilerplate, headers, minimal content
- 0.0: Empty, corrupted, or irrelevant

TEXT:
{content}

Return ONLY valid JSON, no markdown:'''


DOCUMENT_METADATA_PROMPT = '''Analyze this document and return JSON with:
- summary: 2-3 sentence summary of the entire document
- keywords: 10-15 relevant keywords/phrases (lowercase)
- entities: list of {{type, name}} for people, organizations, products, locations mentioned

Entity types: Person, Organization, Product, Location, Date, Project

DOCUMENT TITLE: {title}

CONTENT (first 5000 chars):
{content}

Return ONLY valid JSON, no markdown:'''


def generate_chunk_metadata(content: str) -> Dict[str, Any]:
    """
    Generate metadata for a single chunk using Gemini.

    Args:
        content: Chunk text content

    Returns:
        Dict with summary, keywords, potential_questions, quality_score
    """
    if not content.strip():
        return {
            "summary": "",
            "keywords": [],
            "potential_questions": [],
            "quality_score": 0.0
        }

    prompt = CHUNK_METADATA_PROMPT.format(content=content[:2000])  # Limit context

    response = model.generate_content(
        model="gemini-2.0-flash",
        contents=prompt
    )

    try:
        # Parse JSON from response
        text = response.text.strip()
        # Remove markdown code blocks if present
        if text.startswith("```"):
            text = re.sub(r'^```json?\s*', '', text)
            text = re.sub(r'\s*```$', '', text)

        result = json.loads(text)

        # Validate quality_score is in range
        result["quality_score"] = max(0.0, min(1.0, float(result.get("quality_score", 0.5))))

        return result
    except (json.JSONDecodeError, KeyError) as e:
        # Return defaults on parse error
        return {
            "summary": "",
            "keywords": [],
            "potential_questions": [],
            "quality_score": 0.5  # Default to neutral
        }


def generate_document_metadata(content: str, title: str) -> Dict[str, Any]:
    """
    Generate metadata for an entire document.

    Args:
        content: Full document text
        title: Document title

    Returns:
        Dict with summary, keywords, entities
    """
    prompt = DOCUMENT_METADATA_PROMPT.format(
        title=title,
        content=content[:5000]  # First 5000 chars
    )

    response = model.generate_content(
        model="gemini-2.0-flash",
        contents=prompt
    )

    try:
        text = response.text.strip()
        if text.startswith("```"):
            text = re.sub(r'^```json?\s*', '', text)
            text = re.sub(r'\s*```$', '', text)

        return json.loads(text)
    except (json.JSONDecodeError, KeyError):
        return {
            "summary": "",
            "keywords": [],
            "entities": []
        }


def batch_generate_chunk_metadata(chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Generate metadata for multiple chunks.

    Note: Currently sequential. Could be parallelized with rate limiting.

    Args:
        chunks: List of chunk dicts with "content" key

    Returns:
        List of metadata dicts (same order as input)
    """
    results = []
    for chunk in chunks:
        metadata = generate_chunk_metadata(chunk.get("content", ""))
        results.append(metadata)
    return results
```

**Step 3: Run tests**

Run: `python -m pytest scripts/knowledge_hub/tests/test_metadata.py -v`
Expected: PASS (2 tests)

**Step 4: Commit**

```bash
git add scripts/knowledge_hub/metadata.py scripts/knowledge_hub/tests/test_metadata.py
git commit -m "feat: add LLM-powered metadata generation"
```

---

## Task 16: Update Ingest Pipeline with Metadata

**Files:**
- Modify: `scripts/knowledge_hub/ingest.py`
- Modify: `scripts/knowledge_hub/storage.py`

**Step 1: Update ingest.py to generate metadata**

Add to `ingest_local_file()` after chunking:

```python
# In ingest.py, after chunk_text():

# Generate metadata for each chunk (optional, can be slow)
if generate_metadata:
    from .metadata import batch_generate_chunk_metadata, generate_document_metadata

    # Document-level metadata
    doc_metadata = generate_document_metadata(content, doc_title)

    # Chunk-level metadata
    chunk_metadata = batch_generate_chunk_metadata(chunks)

    # Merge metadata into chunks
    for chunk, meta in zip(chunks, chunk_metadata):
        chunk["summary"] = meta.get("summary", "")
        chunk["keywords"] = meta.get("keywords", [])
        chunk["quality_score"] = meta.get("quality_score", 1.0)
        chunk["potential_questions"] = meta.get("potential_questions", [])
```

**Step 2: Update storage.py to save new fields**

```python
# In store_chunks(), update chunk_records:

chunk_records.append({
    "document_id": document_id,
    "chunk_index": chunk["chunk_index"],
    "section_title": chunk.get("section_title"),
    "content": chunk["content"],
    "content_hash": content_hash,
    "char_count": chunk["char_count"],
    "embedding": embedding,
    # New metadata fields
    "summary": chunk.get("summary"),
    "keywords": chunk.get("keywords"),
    "quality_score": chunk.get("quality_score", 1.0),
    "potential_questions": chunk.get("potential_questions"),
})
```

**Step 3: Run tests**

Run: `python -m pytest scripts/knowledge_hub/tests/ -v`
Expected: All tests pass

**Step 4: Commit**

```bash
git add scripts/knowledge_hub/ingest.py scripts/knowledge_hub/storage.py
git commit -m "feat: integrate metadata generation into ingest pipeline"
```

---

## Task 17: Update Search Module with Recency

**Files:**
- Modify: `scripts/knowledge_hub/search.py`
- Modify: `scripts/knowledge_hub/tests/test_search.py`

**Step 1: Add recency-aware search function**

```python
# In search.py, add new function:

def search_with_recency(
    query: str,
    top_k: int = 5,
    threshold: float = 0.5,
    decay_rate: float = 0.01,
    recency_weight: float = 0.3
) -> List[Dict[str, Any]]:
    """
    Search with recency weighting.

    Formula: final_score = (1-w) * semantic_score + w * exp(-decay * age_days)

    Args:
        query: Search query
        top_k: Max results
        threshold: Min similarity
        decay_rate: How fast old docs lose value (0.01 = slow, 0.1 = fast)
        recency_weight: 0-1, how much recency matters vs relevance

    Returns:
        Results sorted by final_score (semantic + recency combined)
    """
    query_embedding = generate_embedding(query, task_type="RETRIEVAL_QUERY")

    # Use new RPC function
    response = supabase.rpc(
        "match_chunks_with_recency",
        {
            "query_embedding": query_embedding,
            "match_threshold": threshold,
            "match_count": top_k,
            "decay_rate": decay_rate,
            "recency_weight": recency_weight
        }
    ).execute()

    results = []
    chunk_ids = []

    for chunk in response.data:
        results.append({
            "title": chunk.get("document_title", "Unknown"),
            "section": chunk.get("section_title"),
            "content": chunk.get("content", ""),
            "source": chunk.get("source_path", ""),
            "similarity": chunk.get("similarity", 0.0),
            "recency": chunk.get("recency_score", 1.0),
            "score": chunk.get("final_score", 0.0),
            "date": chunk.get("document_date")
        })
        chunk_ids.append(chunk["chunk_id"])

    # Track access for forgetting system
    if chunk_ids:
        supabase.rpc("track_chunk_access", {"chunk_ids": chunk_ids}).execute()

    return results
```

**Step 2: Add test**

```python
# In test_search.py:

def test_search_with_recency_weights_recent_docs():
    """Recent docs should score higher with recency weighting."""
    from scripts.knowledge_hub.search import search_with_recency

    # Test that function accepts recency parameters
    with patch("scripts.knowledge_hub.search.generate_embedding") as mock_embed, \
         patch("scripts.knowledge_hub.search.supabase") as mock_sb:

        mock_embed.return_value = [0.1] * 768
        mock_sb.rpc.return_value.execute.return_value.data = [
            {
                "chunk_id": "123",
                "document_title": "Recent Doc",
                "content": "content",
                "source_path": "/path",
                "similarity": 0.8,
                "recency_score": 0.95,
                "final_score": 0.85,
                "document_date": "2026-02-05"
            }
        ]

        results = search_with_recency(
            "test query",
            decay_rate=0.01,
            recency_weight=0.3
        )

        assert len(results) == 1
        assert results[0]["recency"] == 0.95
        assert results[0]["score"] == 0.85
```

**Step 3: Run tests**

**Step 4: Commit**

```bash
git add scripts/knowledge_hub/search.py scripts/knowledge_hub/tests/test_search.py
git commit -m "feat: add recency-weighted search"
```

---

## Task 18: Add Forgetting/Cleanup Function

**Files:**
- Create: `scripts/knowledge_hub/maintenance.py`
- Create: `scripts/knowledge_hub/tests/test_maintenance.py`

**Step 1: Create maintenance module**

```python
# scripts/knowledge_hub/maintenance.py
"""Maintenance functions for Knowledge Hub - cleanup, forgetting, optimization."""

from datetime import datetime, timedelta
from typing import Dict, Any, List

from .storage import get_supabase_client


def cleanup_unused_chunks(
    min_age_days: int = 90,
    min_access_count: int = 0,
    dry_run: bool = True
) -> Dict[str, Any]:
    """
    Remove chunks that haven't been accessed and are past their TTL.

    Implements "selective forgetting" from ARM research:
    - Frequently accessed items are retained
    - Rarely accessed old items are candidates for removal

    Args:
        min_age_days: Only consider chunks older than this
        min_access_count: Only remove if access_count <= this
        dry_run: If True, just report what would be deleted

    Returns:
        Dict with counts of chunks identified/deleted
    """
    supabase = get_supabase_client()

    cutoff_date = datetime.now() - timedelta(days=min_age_days)

    # Find candidates for removal
    candidates = supabase.table("kb_chunks")\
        .select("id, document_id, access_count, created_at")\
        .lt("created_at", cutoff_date.isoformat())\
        .lte("access_count", min_access_count)\
        .execute()

    result = {
        "candidates_found": len(candidates.data),
        "dry_run": dry_run,
        "deleted": 0
    }

    if not dry_run and candidates.data:
        chunk_ids = [c["id"] for c in candidates.data]
        supabase.table("kb_chunks")\
            .delete()\
            .in_("id", chunk_ids)\
            .execute()
        result["deleted"] = len(chunk_ids)

    return result


def cleanup_low_quality_chunks(
    quality_threshold: float = 0.3,
    dry_run: bool = True
) -> Dict[str, Any]:
    """
    Remove chunks below quality threshold.

    Based on ChunkRAG filtering - low-quality chunks hurt retrieval.

    Args:
        quality_threshold: Remove chunks below this score
        dry_run: If True, just report

    Returns:
        Dict with counts
    """
    supabase = get_supabase_client()

    candidates = supabase.table("kb_chunks")\
        .select("id, quality_score")\
        .lt("quality_score", quality_threshold)\
        .execute()

    result = {
        "candidates_found": len(candidates.data),
        "dry_run": dry_run,
        "deleted": 0
    }

    if not dry_run and candidates.data:
        chunk_ids = [c["id"] for c in candidates.data]
        supabase.table("kb_chunks")\
            .delete()\
            .in_("id", chunk_ids)\
            .execute()
        result["deleted"] = len(chunk_ids)

    return result


def get_forgetting_stats() -> Dict[str, Any]:
    """
    Get statistics about chunk access patterns for forgetting decisions.

    Returns:
        Stats on access patterns, age distribution, quality distribution
    """
    supabase = get_supabase_client()

    # Get basic counts
    total = supabase.table("kb_chunks").select("id", count="exact").execute()

    # Never accessed
    never_accessed = supabase.table("kb_chunks")\
        .select("id", count="exact")\
        .eq("access_count", 0)\
        .execute()

    # Low quality
    low_quality = supabase.table("kb_chunks")\
        .select("id", count="exact")\
        .lt("quality_score", 0.5)\
        .execute()

    return {
        "total_chunks": total.count,
        "never_accessed": never_accessed.count,
        "low_quality": low_quality.count,
        "never_accessed_pct": (never_accessed.count / total.count * 100) if total.count > 0 else 0,
        "low_quality_pct": (low_quality.count / total.count * 100) if total.count > 0 else 0
    }
```

**Step 2: Add tests**

```python
# scripts/knowledge_hub/tests/test_maintenance.py
"""Tests for maintenance functions."""

import pytest
from unittest.mock import Mock, patch


def test_cleanup_unused_chunks_dry_run():
    """Dry run should not delete anything."""
    from scripts.knowledge_hub.maintenance import cleanup_unused_chunks

    mock_response = Mock()
    mock_response.data = [{"id": "1"}, {"id": "2"}]

    with patch("scripts.knowledge_hub.maintenance.get_supabase_client") as mock_sb:
        mock_client = Mock()
        mock_client.table.return_value.select.return_value.lt.return_value.lte.return_value.execute.return_value = mock_response
        mock_sb.return_value = mock_client

        result = cleanup_unused_chunks(dry_run=True)

        assert result["candidates_found"] == 2
        assert result["deleted"] == 0
        assert result["dry_run"] is True


def test_get_forgetting_stats():
    """Should return access pattern statistics."""
    from scripts.knowledge_hub.maintenance import get_forgetting_stats

    with patch("scripts.knowledge_hub.maintenance.get_supabase_client") as mock_sb:
        mock_client = Mock()

        # Mock responses
        total_resp = Mock()
        total_resp.count = 100

        never_resp = Mock()
        never_resp.count = 30

        low_q_resp = Mock()
        low_q_resp.count = 10

        mock_client.table.return_value.select.return_value.execute.return_value = total_resp
        mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = never_resp
        mock_client.table.return_value.select.return_value.lt.return_value.execute.return_value = low_q_resp
        mock_sb.return_value = mock_client

        stats = get_forgetting_stats()

        assert "total_chunks" in stats
        assert "never_accessed" in stats
        assert "low_quality" in stats
```

**Step 3: Run tests**

**Step 4: Commit**

```bash
git add scripts/knowledge_hub/maintenance.py scripts/knowledge_hub/tests/test_maintenance.py
git commit -m "feat: add forgetting/cleanup maintenance functions"
```

---

## Task 19: Update CLI with New Commands

**Files:**
- Modify: `scripts/knowledge_hub/cli.py`

**Step 1: Add new CLI commands**

```python
# Add to cli.py:

def cmd_ingest_with_metadata(args):
    """Ingest with full metadata generation."""
    from .ingest import ingest_local_file

    result = ingest_local_file(
        args.file,
        category=args.category,
        generate_metadata=True  # New flag
    )
    print(json.dumps(result, indent=2))


def cmd_search_recency(args):
    """Search with recency weighting."""
    from .search import search_with_recency

    results = search_with_recency(
        args.query,
        top_k=args.top_k,
        decay_rate=args.decay_rate,
        recency_weight=args.recency_weight
    )

    print("=" * 60)
    print(f"RESULTS (decay={args.decay_rate}, recency_weight={args.recency_weight}):")
    print("=" * 60)

    for i, r in enumerate(results, 1):
        print(f"\n[{i}] {r['title']} (score: {r['score']:.2f})")
        print(f"    Semantic: {r['similarity']:.2f} | Recency: {r['recency']:.2f}")
        print(f"    Date: {r.get('date', 'Unknown')}")
        print(f"    {r['content'][:200]}...")


def cmd_maintenance(args):
    """Run maintenance/cleanup tasks."""
    from .maintenance import cleanup_unused_chunks, cleanup_low_quality_chunks, get_forgetting_stats

    if args.action == "stats":
        stats = get_forgetting_stats()
        print("Forgetting Statistics:")
        for k, v in stats.items():
            print(f"  {k}: {v}")

    elif args.action == "cleanup-unused":
        result = cleanup_unused_chunks(
            min_age_days=args.min_age,
            dry_run=args.dry_run
        )
        print(f"Cleanup unused: {result}")

    elif args.action == "cleanup-low-quality":
        result = cleanup_low_quality_chunks(
            quality_threshold=args.quality_threshold,
            dry_run=args.dry_run
        )
        print(f"Cleanup low-quality: {result}")


# Add to main() parser:

# Search with recency
search_recency_parser = subparsers.add_parser("search-recency", help="Search with recency weighting")
search_recency_parser.add_argument("query", help="Search query")
search_recency_parser.add_argument("--top-k", type=int, default=5)
search_recency_parser.add_argument("--decay-rate", type=float, default=0.01, help="Higher = faster decay")
search_recency_parser.add_argument("--recency-weight", type=float, default=0.3, help="0-1, how much recency matters")
search_recency_parser.set_defaults(func=cmd_search_recency)

# Maintenance
maint_parser = subparsers.add_parser("maintenance", help="Run maintenance tasks")
maint_parser.add_argument("action", choices=["stats", "cleanup-unused", "cleanup-low-quality"])
maint_parser.add_argument("--dry-run", action="store_true", default=True)
maint_parser.add_argument("--no-dry-run", dest="dry_run", action="store_false")
maint_parser.add_argument("--min-age", type=int, default=90, help="Days before considering for cleanup")
maint_parser.add_argument("--quality-threshold", type=float, default=0.3)
maint_parser.set_defaults(func=cmd_maintenance)
```

**Step 2: Test CLI**

Run: `doppler run -- python -m scripts.knowledge_hub.cli --help`
Expected: Shows new commands (search-recency, maintenance)

**Step 3: Commit**

```bash
git add scripts/knowledge_hub/cli.py
git commit -m "feat: add recency search and maintenance CLI commands"
```

---

## Task 20: Integration Test Phase 2

**Step 1: Ingest document with metadata**

```bash
doppler run --project bei-erp --config dev -- python -m scripts.knowledge_hub.cli ingest "CEO/Weekly Reports/MANCOM WW5 (2026) - OPERATIONS.pptx" --category mancom --with-metadata
```

Expected: Document ingested with quality scores and summaries

**Step 2: Test recency search**

```bash
# High recency weight (prefer recent)
doppler run -- python -m scripts.knowledge_hub.cli search-recency "operations update" --recency-weight 0.5

# Low recency weight (prefer relevance)
doppler run -- python -m scripts.knowledge_hub.cli search-recency "operations update" --recency-weight 0.1
```

Expected: Different result ordering based on recency weight

**Step 3: Check maintenance stats**

```bash
doppler run -- python -m scripts.knowledge_hub.cli maintenance stats
```

Expected: Shows chunk access patterns

**Step 4: Run cleanup dry-run**

```bash
doppler run -- python -m scripts.knowledge_hub.cli maintenance cleanup-unused --dry-run
doppler run -- python -m scripts.knowledge_hub.cli maintenance cleanup-low-quality --dry-run
```

Expected: Reports candidates without deleting

---

## Phase 2 Summary

| Task | Component | Description |
|------|-----------|-------------|
| 13 | Schema migration | Add metadata, quality, forgetting fields |
| 14 | Search RPC | Recency-weighted search function |
| 15 | Metadata module | LLM-generated summaries, keywords, quality |
| 16 | Ingest update | Integrate metadata generation |
| 17 | Search update | Add recency-aware search |
| 18 | Maintenance | Forgetting/cleanup functions |
| 19 | CLI update | New commands for recency + maintenance |
| 20 | Integration test | Verify end-to-end |

**Total: 8 new tasks (Phase 2)**

## Research References

| Topic | Key Finding | Source |
|-------|-------------|--------|
| Context Rot | Accuracy drops at 32K+ tokens | [Chroma July 2025](https://research.trychroma.com/context-rot) |
| Recency Scoring | `score = sim * exp(-decay * age)` | [arXiv:2509.19376](https://arxiv.org/html/2509.19376) |
| ChunkRAG | Multi-stage LLM quality filtering | [arXiv:2410.19572](https://arxiv.org/abs/2410.19572) |
| Selective Forgetting | +2-5 EM points, 30% smaller memory | [arXiv:2601.02428](https://arxiv.org/abs/2601.02428) |
| Machine Unlearning | 224s unlearning vs months retraining | [IBM Research](https://www.ibm.com/think/insights/machine-unlearning)
