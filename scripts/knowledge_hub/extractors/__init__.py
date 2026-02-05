"""Document extractors for various file types."""

from .pptx import extract_pptx, pptx_to_text

__all__ = ["extract_pptx", "pptx_to_text"]
