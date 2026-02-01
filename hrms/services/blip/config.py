"""
Blip Configuration

Environment variables loaded from .env or system environment.
"""

from pydantic_settings import BaseSettings
from pydantic import field_validator
from typing import Optional, List


class Settings(BaseSettings):
    """Blip service configuration."""

    # Service
    SERVICE_NAME: str = "blip"
    SERVICE_PORT: int = 8766
    LOG_LEVEL: str = "INFO"

    # Frappe API
    FRAPPE_URL: str = "https://hq.bebang.ph"
    FRAPPE_API_KEY: str = ""
    FRAPPE_API_SECRET: str = ""

    # Claude AI - for intent parsing
    ANTHROPIC_API_KEY: str = ""
    CLAUDE_MODEL: str = "claude-haiku-4-5-20251001"  # Haiku 4.5 - fast intent detection

    # Gemini AI - for response formatting
    GEMINI_API_KEY: str = ""  # Gemini API key (maps to GOOGLE_API_KEY internally)
    GEMINI_MODEL: str = "gemini-3-flash-preview"  # Gemini 3 Flash - LATEST

    # Google Service Account (for sending proactive messages to Chat)
    GOOGLE_SERVICE_ACCOUNT_FILE: Optional[str] = None

    # Admin users (full access) - comma-separated in env var
    ADMIN_EMAILS: str = "sam@bebang.ph"

    @property
    def admin_email_list(self) -> List[str]:
        """Parse comma-separated admin emails into list."""
        return [e.strip() for e in self.ADMIN_EMAILS.split(",") if e.strip()]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
