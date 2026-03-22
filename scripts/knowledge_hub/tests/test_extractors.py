"""Tests for document extractors."""

import pytest
from unittest.mock import Mock, patch, MagicMock


def test_pptx_extractor_returns_slides():
    """PPTX extractor should return slide content."""
    from scripts.knowledge_hub.extractors.pptx import extract_pptx

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


def test_pptx_extractor_returns_metadata():
    """PPTX extractor should return slide count in metadata."""
    from scripts.knowledge_hub.extractors.pptx import extract_pptx

    mock_shape = Mock()
    mock_shape.text = "Content"

    mock_slide1 = Mock()
    mock_slide1.shapes = [mock_shape]
    mock_slide1.has_notes_slide = False

    mock_slide2 = Mock()
    mock_slide2.shapes = [mock_shape]
    mock_slide2.has_notes_slide = False

    mock_prs = Mock()
    mock_prs.slides = [mock_slide1, mock_slide2]

    with patch("scripts.knowledge_hub.extractors.pptx.Presentation", return_value=mock_prs):
        result = extract_pptx("/fake/path.pptx")

        assert "metadata" in result
        assert result["metadata"]["slide_count"] == 2


def test_pptx_to_text_conversion():
    """pptx_to_text should convert extraction to plain text."""
    from scripts.knowledge_hub.extractors.pptx import pptx_to_text

    mock_shape = Mock()
    mock_shape.text = "Slide content"

    mock_notes_frame = Mock()
    mock_notes_frame.text = "Notes content"

    mock_notes_slide = Mock()
    mock_notes_slide.notes_text_frame = mock_notes_frame

    mock_slide = Mock()
    mock_slide.shapes = [mock_shape]
    mock_slide.has_notes_slide = True
    mock_slide.notes_slide = mock_notes_slide

    mock_prs = Mock()
    mock_prs.slides = [mock_slide]

    with patch("scripts.knowledge_hub.extractors.pptx.Presentation", return_value=mock_prs):
        result = pptx_to_text("/fake/path.pptx")

        assert "Slide 1" in result
        assert "Slide content" in result
        assert "Speaker Notes" in result
        assert "Notes content" in result


def test_pptx_to_text_without_notes():
    """pptx_to_text should exclude notes when include_notes=False."""
    from scripts.knowledge_hub.extractors.pptx import pptx_to_text

    mock_shape = Mock()
    mock_shape.text = "Slide content"

    mock_notes_frame = Mock()
    mock_notes_frame.text = "Notes content"

    mock_notes_slide = Mock()
    mock_notes_slide.notes_text_frame = mock_notes_frame

    mock_slide = Mock()
    mock_slide.shapes = [mock_shape]
    mock_slide.has_notes_slide = True
    mock_slide.notes_slide = mock_notes_slide

    mock_prs = Mock()
    mock_prs.slides = [mock_slide]

    with patch("scripts.knowledge_hub.extractors.pptx.Presentation", return_value=mock_prs):
        result = pptx_to_text("/fake/path.pptx", include_notes=False)

        assert "Slide content" in result
        assert "Speaker Notes" not in result
        assert "Notes content" not in result
