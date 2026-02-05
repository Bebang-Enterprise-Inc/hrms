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

    assert len(chunks) >= 2
    if len(chunks) >= 2:
        chunk1_end = chunks[0]["content"][-100:]
        assert chunk1_end in chunks[1]["content"]


def test_chunk_text_preserves_all_content():
    """All original content should be in at least one chunk."""
    from scripts.knowledge_hub.chunker import chunk_text

    text = "The quick brown fox jumps over the lazy dog."
    chunks = chunk_text(text, chunk_size=20, overlap=5)

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


def test_chunk_text_single_small_text():
    """Small text that fits in one chunk should return single chunk."""
    from scripts.knowledge_hub.chunker import chunk_text

    text = "Short text"
    chunks = chunk_text(text, chunk_size=1000, overlap=200)

    assert len(chunks) == 1
    assert chunks[0]["content"] == text
    assert chunks[0]["chunk_index"] == 0
    assert chunks[0]["char_count"] == len(text)


def test_chunk_text_empty_string():
    """Empty string should return empty list or single empty chunk."""
    from scripts.knowledge_hub.chunker import chunk_text

    chunks = chunk_text("", chunk_size=1000, overlap=200)

    # Either empty list or single chunk with empty content is acceptable
    assert len(chunks) <= 1


def test_chunk_text_uses_config_defaults():
    """Should use config defaults when parameters not specified."""
    from scripts.knowledge_hub.chunker import chunk_text
    from scripts.knowledge_hub.config import config

    text = "word " * 300  # 1500 chars, will need chunking with default 1000 size
    chunks = chunk_text(text)  # No explicit chunk_size/overlap

    # Should use config.chunk_size (1000) and config.chunk_overlap (200)
    assert len(chunks) >= 2
    for chunk in chunks:
        assert len(chunk["content"]) <= config.chunk_size
