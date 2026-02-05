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
