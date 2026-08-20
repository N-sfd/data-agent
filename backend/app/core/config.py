from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_ROOT_ENV = Path(__file__).resolve().parents[3] / ".env"
_BACKEND_ENV = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    app_name: str = "Enterprise Financial Data Agent"
    app_env: str = "development"
    debug: bool = True

    upload_directory: str = "uploads"
    max_upload_mb: int = 100
    max_pdf_pages: int = 1000
    allow_encrypted_pdf: bool = False

    database_url: str = "sqlite:///./data_agent.db"

    oracle_base_url: str = "https://example.fa.oraclecloud.com"
    oracle_api_version: str = "11.13.18.05"
    oracle_dry_run: bool = True

    frontend_url: str = "http://localhost:3000"

    ai_provider: str = "gemini"

    convera_enabled: bool = False
    convera_api_url: str = "http://localhost:8000"
    convera_api_key: str | None = None
    convera_timeout_seconds: int = 120
    convera_documents_enabled: bool = False
    convera_ai_enabled: bool = False

    gemini_api_key: str | None = None
    gemini_model: str = "gemini-2.5-flash"

    openai_api_key: str | None = None
    openai_model: str | None = None

    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str | None = None

    ai_fallback_enabled: bool = True

    # development | local | production
    # "development" shows the Gemini free-tier privacy notice in the UI.
    ai_provider_mode: str = "development"

    ai_max_pages: int = 10
    ai_max_context_chars: int = 60000

    ocr_enabled: bool = True
    ocr_language: str = "eng"
    ocr_dpi: int = 300

    ocr_min_character_count: int = 40
    ocr_min_word_count: int = 8
    ocr_min_text_coverage: float = 0.002
    ocr_max_image_ratio: float = 0.70

    tessdata_prefix: str | None = None

    model_config = SettingsConfigDict(
        env_file=(_ROOT_ENV, _BACKEND_ENV),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @property
    def cors_origins(self) -> list[str]:
        """Support comma-separated FRONTEND_URL values."""
        origins = [
            origin.strip()
            for origin in self.frontend_url.split(",")
            if origin.strip()
        ]

        if self.debug:
            for origin in (
                "http://localhost:3000",
                "http://127.0.0.1:3000",
                "http://localhost:3001",
                "http://127.0.0.1:3001",
                "http://192.168.0.193:3000",
            ):
                if origin not in origins:
                    origins.append(origin)

        return origins

    @property
    def upload_path(self) -> Path:
        """Create and return the private upload directory."""
        path = Path(self.upload_directory)
        if not path.is_absolute():
            path = Path(__file__).resolve().parents[2] / path
        path = path.resolve()
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def tessdata_path(self) -> Path | None:
        if not self.tessdata_prefix:
            return None

        path = Path(self.tessdata_prefix)

        if not path.exists():
            return None

        return path


@lru_cache
def get_settings() -> Settings:
    return Settings()
