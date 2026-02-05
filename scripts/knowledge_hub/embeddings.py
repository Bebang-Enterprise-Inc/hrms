"""Gemini embedding generation for Knowledge Hub."""

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
