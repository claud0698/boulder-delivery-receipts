"""Application configuration management."""

from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Telegram Bot
    telegram_bot_token: str

    # Google Cloud Platform - Vertex AI
    gcp_project_id: str
    gcp_location: str = "us-central1"  # Default Vertex AI location

    # Google Sheets
    google_sheets_id: str
    google_application_credentials: Optional[str] = None

    # Google Cloud Storage
    gcs_bucket_name: Optional[str] = None

    # Application
    environment: str = "development"
    log_level: str = "INFO"
    port: int = 8080

    # OCR Configuration
    # Reject extractions below 50% confidence
    min_confidence_threshold: float = 0.5

    # Webhook (for production)
    webhook_url: Optional[str] = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    @property
    def is_production(self) -> bool:
        """Check if running in production."""
        return self.environment.lower() == "production"

    @property
    def credentials_path(self) -> Path:
        """Get Path object for credentials file."""
        return Path(self.google_application_credentials)

    def validate_credentials(self) -> bool:
        """Check if credentials file exists."""
        return self.credentials_path.exists()


# Global settings instance
settings = Settings()
