"""LLM-powered metadata generation for Knowledge Hub."""

import json
import re
from typing import Dict, Any, List

from google import genai

from .config import config

# Initialize Gemini client
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
- entities: object with:
  - organizations: list of company/organization names mentioned
  - people: list of person names mentioned
  - topics: list of main topics/themes

DOCUMENT TITLE: {title}

DOCUMENT CONTENT:
{content}

Return ONLY valid JSON, no markdown:'''


def _parse_json_response(text: str) -> Dict[str, Any]:
    """Parse JSON from API response, handling markdown wrapping."""
    text = text.strip()

    # Remove markdown code block wrapper if present
    if text.startswith("```"):
        text = re.sub(r'^```json?\s*', '', text)
        text = re.sub(r'\s*```$', '', text)

    return json.loads(text)


def generate_chunk_metadata(content: str) -> Dict[str, Any]:
    """
    Generate metadata for a single chunk using Gemini.

    Args:
        content: Text content of the chunk

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

    # Truncate content to avoid token limits
    prompt = CHUNK_METADATA_PROMPT.format(content=content[:2000])

    response = model.generate_content(
        model="gemini-2.0-flash",
        contents=prompt
    )

    try:
        result = _parse_json_response(response.text)
        # Clamp quality_score between 0.0 and 1.0
        result["quality_score"] = max(0.0, min(1.0, float(result.get("quality_score", 0.5))))
        return result
    except (json.JSONDecodeError, KeyError, ValueError):
        return {
            "summary": "",
            "keywords": [],
            "potential_questions": [],
            "quality_score": 0.5
        }


def generate_document_metadata(content: str, title: str) -> Dict[str, Any]:
    """
    Generate metadata for an entire document using Gemini.

    Args:
        content: Full text content of the document
        title: Document title

    Returns:
        Dict with summary, keywords, entities
    """
    if not content.strip():
        return {
            "summary": "",
            "keywords": [],
            "entities": {
                "organizations": [],
                "people": [],
                "topics": []
            }
        }

    # Truncate content for document-level analysis (larger context)
    prompt = DOCUMENT_METADATA_PROMPT.format(
        title=title,
        content=content[:8000]
    )

    response = model.generate_content(
        model="gemini-2.0-flash",
        contents=prompt
    )

    try:
        result = _parse_json_response(response.text)
        # Ensure entities structure exists
        if "entities" not in result:
            result["entities"] = {
                "organizations": [],
                "people": [],
                "topics": []
            }
        return result
    except (json.JSONDecodeError, KeyError, ValueError):
        return {
            "summary": "",
            "keywords": [],
            "entities": {
                "organizations": [],
                "people": [],
                "topics": []
            }
        }


def batch_generate_chunk_metadata(chunks: List[str]) -> List[Dict[str, Any]]:
    """
    Generate metadata for multiple chunks.

    Args:
        chunks: List of text chunks

    Returns:
        List of metadata dicts, one per chunk
    """
    results = []
    for chunk in chunks:
        metadata = generate_chunk_metadata(chunk)
        results.append(metadata)
    return results
