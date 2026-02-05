"""Tests for ingestion pipeline."""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, call


class TestExtractContent:
    """Tests for extract_content function."""

    def test_extract_pptx_content(self, tmp_path):
        """Extracting .pptx should delegate to pptx_to_text."""
        from scripts.knowledge_hub.ingest import extract_content

        with patch("scripts.knowledge_hub.ingest.pptx_to_text") as mock_pptx:
            mock_pptx.return_value = "Slide content"

            result = extract_content(str(tmp_path / "test.pptx"))

            mock_pptx.assert_called_once()
            assert result == "Slide content"

    def test_extract_txt_content(self, tmp_path):
        """Extracting .txt should read file directly."""
        from scripts.knowledge_hub.ingest import extract_content

        test_file = tmp_path / "test.txt"
        test_file.write_text("Plain text content", encoding="utf-8")

        result = extract_content(str(test_file))

        assert result == "Plain text content"

    def test_extract_md_content(self, tmp_path):
        """Extracting .md should read file directly."""
        from scripts.knowledge_hub.ingest import extract_content

        test_file = tmp_path / "test.md"
        test_file.write_text("# Markdown content", encoding="utf-8")

        result = extract_content(str(test_file))

        assert result == "# Markdown content"

    def test_extract_unsupported_extension_raises(self, tmp_path):
        """Unsupported file extension should raise ValueError."""
        from scripts.knowledge_hub.ingest import extract_content

        with pytest.raises(ValueError, match="Unsupported file type"):
            extract_content(str(tmp_path / "test.xyz"))


class TestGetMimeType:
    """Tests for _get_mime_type helper."""

    def test_pptx_mime_type(self):
        """Should return correct MIME type for .pptx."""
        from scripts.knowledge_hub.ingest import _get_mime_type

        assert _get_mime_type(".pptx") == "application/vnd.openxmlformats-officedocument.presentationml.presentation"

    def test_txt_mime_type(self):
        """Should return correct MIME type for .txt."""
        from scripts.knowledge_hub.ingest import _get_mime_type

        assert _get_mime_type(".txt") == "text/plain"

    def test_md_mime_type(self):
        """Should return correct MIME type for .md."""
        from scripts.knowledge_hub.ingest import _get_mime_type

        assert _get_mime_type(".md") == "text/markdown"

    def test_unknown_extension_returns_octet_stream(self):
        """Unknown extension should return application/octet-stream."""
        from scripts.knowledge_hub.ingest import _get_mime_type

        assert _get_mime_type(".xyz") == "application/octet-stream"


class TestIngestLocalFile:
    """Tests for ingest_local_file function."""

    def test_ingest_local_file_creates_document(self):
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
            mock_update.assert_called_with("doc-123", "completed", None, doc_metadata=None)

    def test_ingest_local_file_passes_metadata(self):
        """Custom metadata should be passed to store_document."""
        from scripts.knowledge_hub.ingest import ingest_local_file

        with patch("scripts.knowledge_hub.ingest.extract_content") as mock_extract, \
             patch("scripts.knowledge_hub.ingest.chunk_text") as mock_chunk, \
             patch("scripts.knowledge_hub.ingest.generate_embeddings_batch") as mock_embed, \
             patch("scripts.knowledge_hub.ingest.store_document") as mock_store_doc, \
             patch("scripts.knowledge_hub.ingest.store_chunks") as mock_store_chunks, \
             patch("scripts.knowledge_hub.ingest.update_document_status"):

            mock_extract.return_value = "Content"
            mock_chunk.return_value = [{"content": "chunk", "chunk_index": 0, "char_count": 5}]
            mock_embed.return_value = [[0.1] * 768]
            mock_store_doc.return_value = "doc-123"
            mock_store_chunks.return_value = ["chunk-456"]

            custom_metadata = {"author": "John", "department": "HR"}
            ingest_local_file("/test/file.txt", metadata=custom_metadata)

            # Check metadata was passed
            call_kwargs = mock_store_doc.call_args.kwargs
            assert call_kwargs["metadata"] == custom_metadata

    def test_ingest_local_file_handles_extraction_error(self):
        """Extraction error should update status to failed."""
        from scripts.knowledge_hub.ingest import ingest_local_file

        with patch("scripts.knowledge_hub.ingest.extract_content") as mock_extract, \
             patch("scripts.knowledge_hub.ingest.store_document") as mock_store_doc, \
             patch("scripts.knowledge_hub.ingest.update_document_status") as mock_update:

            mock_extract.side_effect = Exception("Extraction failed")
            mock_store_doc.return_value = "doc-123"

            result = ingest_local_file("/test/file.pptx")

            assert result["error"] is not None
            assert "Extraction failed" in result["error"]
            mock_update.assert_called_with("doc-123", "failed", "Extraction failed")

    def test_ingest_local_file_uses_filename_as_title(self):
        """Title should default to filename stem."""
        from scripts.knowledge_hub.ingest import ingest_local_file

        with patch("scripts.knowledge_hub.ingest.extract_content") as mock_extract, \
             patch("scripts.knowledge_hub.ingest.chunk_text") as mock_chunk, \
             patch("scripts.knowledge_hub.ingest.generate_embeddings_batch") as mock_embed, \
             patch("scripts.knowledge_hub.ingest.store_document") as mock_store_doc, \
             patch("scripts.knowledge_hub.ingest.store_chunks"), \
             patch("scripts.knowledge_hub.ingest.update_document_status"):

            mock_extract.return_value = "Content"
            mock_chunk.return_value = [{"content": "chunk", "chunk_index": 0, "char_count": 5}]
            mock_embed.return_value = [[0.1] * 768]
            mock_store_doc.return_value = "doc-123"

            ingest_local_file("/path/to/MyPresentation.pptx")

            call_kwargs = mock_store_doc.call_args.kwargs
            assert call_kwargs["title"] == "MyPresentation"


class TestIngestDriveFile:
    """Tests for ingest_drive_file function."""

    def test_ingest_skips_existing_file(self):
        """Should skip if file already ingested (by file_id)."""
        from scripts.knowledge_hub.ingest import ingest_drive_file

        with patch("scripts.knowledge_hub.ingest.document_exists") as mock_exists:
            mock_exists.return_value = True

            result = ingest_drive_file(file_id="existing-123", title="Test")

            assert result["skipped"] is True
            assert "already exists" in result["reason"]

    def test_ingest_drive_file_creates_document(self):
        """Ingesting new Drive file should create document and chunks."""
        from scripts.knowledge_hub.ingest import ingest_drive_file

        with patch("scripts.knowledge_hub.ingest.document_exists") as mock_exists, \
             patch("scripts.knowledge_hub.ingest.chunk_text") as mock_chunk, \
             patch("scripts.knowledge_hub.ingest.generate_embeddings_batch") as mock_embed, \
             patch("scripts.knowledge_hub.ingest.store_document") as mock_store_doc, \
             patch("scripts.knowledge_hub.ingest.store_chunks") as mock_store_chunks, \
             patch("scripts.knowledge_hub.ingest.update_document_status") as mock_update:

            mock_exists.return_value = False
            mock_chunk.return_value = [{"content": "chunk", "chunk_index": 0, "char_count": 5}]
            mock_embed.return_value = [[0.1] * 768]
            mock_store_doc.return_value = "doc-456"
            mock_store_chunks.return_value = ["chunk-789"]

            result = ingest_drive_file(
                file_id="drive-file-123",
                title="ManCom Deck",
                content="Extracted content from Drive",
                category="mancom",
                mime_type="application/vnd.google-apps.presentation",
                owner_email="sam@bebang.ph"
            )

            assert result["document_id"] == "doc-456"
            assert result["chunks_created"] == 1
            assert result["skipped"] is False
            mock_update.assert_called_with("doc-456", "completed", None, doc_metadata=None)

    def test_ingest_drive_file_stores_source_type_gdrive(self):
        """Drive files should have source_type='gdrive'."""
        from scripts.knowledge_hub.ingest import ingest_drive_file

        with patch("scripts.knowledge_hub.ingest.document_exists") as mock_exists, \
             patch("scripts.knowledge_hub.ingest.chunk_text") as mock_chunk, \
             patch("scripts.knowledge_hub.ingest.generate_embeddings_batch") as mock_embed, \
             patch("scripts.knowledge_hub.ingest.store_document") as mock_store_doc, \
             patch("scripts.knowledge_hub.ingest.store_chunks"), \
             patch("scripts.knowledge_hub.ingest.update_document_status"):

            mock_exists.return_value = False
            mock_chunk.return_value = [{"content": "chunk", "chunk_index": 0, "char_count": 5}]
            mock_embed.return_value = [[0.1] * 768]
            mock_store_doc.return_value = "doc-456"

            ingest_drive_file(
                file_id="drive-123",
                title="Test Doc",
                content="Content"
            )

            call_kwargs = mock_store_doc.call_args.kwargs
            assert call_kwargs["source_type"] == "gdrive"
            assert call_kwargs["file_id"] == "drive-123"

    def test_ingest_drive_file_handles_error(self):
        """Error during ingestion should update status to failed."""
        from scripts.knowledge_hub.ingest import ingest_drive_file

        with patch("scripts.knowledge_hub.ingest.document_exists") as mock_exists, \
             patch("scripts.knowledge_hub.ingest.store_document") as mock_store_doc, \
             patch("scripts.knowledge_hub.ingest.chunk_text") as mock_chunk, \
             patch("scripts.knowledge_hub.ingest.update_document_status") as mock_update:

            mock_exists.return_value = False
            mock_store_doc.return_value = "doc-456"
            mock_chunk.side_effect = Exception("Chunking failed")

            result = ingest_drive_file(
                file_id="drive-123",
                title="Test Doc",
                content="Content"
            )

            assert result["error"] is not None
            assert "Chunking failed" in result["error"]
            mock_update.assert_called_with("doc-456", "failed", "Chunking failed")


class TestIngestWithMetadataGeneration:
    """Tests for metadata generation during ingestion."""

    def test_ingest_local_file_with_metadata_generation(self):
        """When generate_metadata=True, should call metadata functions and merge into chunks."""
        from scripts.knowledge_hub.ingest import ingest_local_file

        mock_chunk_metadata = {
            "summary": "Test chunk summary",
            "keywords": ["test", "keyword"],
            "potential_questions": ["What is test?"],
            "quality_score": 0.85
        }
        mock_doc_metadata = {
            "summary": "Test document summary",
            "keywords": ["document", "test"],
            "entities": {"organizations": ["BEI"], "people": [], "topics": ["testing"]}
        }

        with patch("scripts.knowledge_hub.ingest.extract_content") as mock_extract, \
             patch("scripts.knowledge_hub.ingest.chunk_text") as mock_chunk, \
             patch("scripts.knowledge_hub.ingest.generate_embeddings_batch") as mock_embed, \
             patch("scripts.knowledge_hub.ingest.store_document") as mock_store_doc, \
             patch("scripts.knowledge_hub.ingest.store_chunks") as mock_store_chunks, \
             patch("scripts.knowledge_hub.ingest.update_document_status") as mock_update, \
             patch("scripts.knowledge_hub.metadata.batch_generate_chunk_metadata") as mock_batch_meta, \
             patch("scripts.knowledge_hub.metadata.generate_document_metadata") as mock_doc_meta:

            mock_extract.return_value = "Document content for testing"
            mock_chunk.return_value = [
                {"content": "chunk1", "chunk_index": 0, "char_count": 6},
                {"content": "chunk2", "chunk_index": 1, "char_count": 6}
            ]
            mock_embed.return_value = [[0.1] * 768, [0.2] * 768]
            mock_store_doc.return_value = "doc-meta-123"
            mock_store_chunks.return_value = ["chunk-1", "chunk-2"]
            mock_batch_meta.return_value = [mock_chunk_metadata, mock_chunk_metadata]
            mock_doc_meta.return_value = mock_doc_metadata

            result = ingest_local_file("/test/file.txt", generate_metadata=True)

            # Verify metadata functions were called
            mock_batch_meta.assert_called_once()
            mock_doc_meta.assert_called_once()

            # Verify chunks were updated with metadata before storage
            stored_chunks = mock_store_chunks.call_args[0][1]
            assert stored_chunks[0]["summary"] == "Test chunk summary"
            assert stored_chunks[0]["keywords"] == ["test", "keyword"]
            assert stored_chunks[0]["quality_score"] == 0.85
            assert stored_chunks[0]["potential_questions"] == ["What is test?"]

            # Verify document metadata was passed to update
            mock_update.assert_called_with(
                "doc-meta-123", "completed", None, doc_metadata=mock_doc_metadata
            )

            assert result["document_id"] == "doc-meta-123"
            assert result["chunks_created"] == 2
            assert result["error"] is None

    def test_ingest_local_file_without_metadata_generation(self):
        """When generate_metadata=False (default), should not call metadata functions."""
        from scripts.knowledge_hub.ingest import ingest_local_file

        with patch("scripts.knowledge_hub.ingest.extract_content") as mock_extract, \
             patch("scripts.knowledge_hub.ingest.chunk_text") as mock_chunk, \
             patch("scripts.knowledge_hub.ingest.generate_embeddings_batch") as mock_embed, \
             patch("scripts.knowledge_hub.ingest.store_document") as mock_store_doc, \
             patch("scripts.knowledge_hub.ingest.store_chunks") as mock_store_chunks, \
             patch("scripts.knowledge_hub.ingest.update_document_status") as mock_update:

            mock_extract.return_value = "Content"
            mock_chunk.return_value = [{"content": "chunk", "chunk_index": 0, "char_count": 5}]
            mock_embed.return_value = [[0.1] * 768]
            mock_store_doc.return_value = "doc-123"
            mock_store_chunks.return_value = ["chunk-456"]

            result = ingest_local_file("/test/file.txt", generate_metadata=False)

            # Verify chunks do not have metadata fields
            stored_chunks = mock_store_chunks.call_args[0][1]
            assert "summary" not in stored_chunks[0]
            assert "keywords" not in stored_chunks[0]

            # Verify update was called with doc_metadata=None
            mock_update.assert_called_with("doc-123", "completed", None, doc_metadata=None)

    def test_ingest_drive_file_with_metadata_generation(self):
        """Drive file ingestion should also support metadata generation."""
        from scripts.knowledge_hub.ingest import ingest_drive_file

        mock_chunk_metadata = {
            "summary": "Drive chunk summary",
            "keywords": ["drive", "file"],
            "potential_questions": ["How to use Drive?"],
            "quality_score": 0.9
        }
        mock_doc_metadata = {
            "summary": "Drive document summary",
            "keywords": ["google", "drive"],
            "entities": {"organizations": [], "people": ["Sam"], "topics": ["file sharing"]}
        }

        with patch("scripts.knowledge_hub.ingest.document_exists") as mock_exists, \
             patch("scripts.knowledge_hub.ingest.chunk_text") as mock_chunk, \
             patch("scripts.knowledge_hub.ingest.generate_embeddings_batch") as mock_embed, \
             patch("scripts.knowledge_hub.ingest.store_document") as mock_store_doc, \
             patch("scripts.knowledge_hub.ingest.store_chunks") as mock_store_chunks, \
             patch("scripts.knowledge_hub.ingest.update_document_status") as mock_update, \
             patch("scripts.knowledge_hub.metadata.batch_generate_chunk_metadata") as mock_batch_meta, \
             patch("scripts.knowledge_hub.metadata.generate_document_metadata") as mock_doc_meta:

            mock_exists.return_value = False
            mock_chunk.return_value = [
                {"content": "drive content", "chunk_index": 0, "char_count": 13}
            ]
            mock_embed.return_value = [[0.1] * 768]
            mock_store_doc.return_value = "doc-drive-456"
            mock_store_chunks.return_value = ["chunk-drive-1"]
            mock_batch_meta.return_value = [mock_chunk_metadata]
            mock_doc_meta.return_value = mock_doc_metadata

            result = ingest_drive_file(
                file_id="drive-123",
                title="Test Drive Doc",
                content="Drive file content for testing",
                generate_metadata=True
            )

            # Verify metadata functions were called
            mock_batch_meta.assert_called_once()
            mock_doc_meta.assert_called_once()

            # Verify chunks have metadata
            stored_chunks = mock_store_chunks.call_args[0][1]
            assert stored_chunks[0]["summary"] == "Drive chunk summary"
            assert stored_chunks[0]["quality_score"] == 0.9

            # Verify document metadata was passed
            mock_update.assert_called_with(
                "doc-drive-456", "completed", None, doc_metadata=mock_doc_metadata
            )

            assert result["document_id"] == "doc-drive-456"
            assert result["skipped"] is False

    def test_ingest_drive_file_empty_content_skips_metadata(self):
        """Empty content should not attempt metadata generation."""
        from scripts.knowledge_hub.ingest import ingest_drive_file

        with patch("scripts.knowledge_hub.ingest.document_exists") as mock_exists, \
             patch("scripts.knowledge_hub.ingest.chunk_text") as mock_chunk, \
             patch("scripts.knowledge_hub.ingest.generate_embeddings_batch") as mock_embed, \
             patch("scripts.knowledge_hub.ingest.store_document") as mock_store_doc, \
             patch("scripts.knowledge_hub.ingest.store_chunks") as mock_store_chunks, \
             patch("scripts.knowledge_hub.ingest.update_document_status") as mock_update:

            mock_exists.return_value = False
            mock_chunk.return_value = []  # Empty chunks
            mock_embed.return_value = []
            mock_store_doc.return_value = "doc-empty"

            result = ingest_drive_file(
                file_id="drive-empty",
                title="Empty Doc",
                content="",
                generate_metadata=True
            )

            # Should complete without error even with generate_metadata=True
            assert result["document_id"] == "doc-empty"
            assert result["chunks_created"] == 0
            assert result["error"] is None
