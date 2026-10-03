"""Application settings, loaded from environment variables (and an optional .env file).

Every tunable behaviour of the backend lives here so that development, test and
production environments differ only by configuration, never by code.
"""

from functools import lru_cache
from typing import Annotated, Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

Environment = Literal["development", "test", "production"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- Application -------------------------------------------------------------
    app_env: Environment = "development"
    app_name: str = "Nexa AI"
    app_version: str = "1.0.0"
    log_level: str = "INFO"
    log_json: bool = False
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:5173", "http://127.0.0.1:5173"]
    )
    # Directory containing the built frontend. When set, the backend also serves the SPA
    # (used by the single-container cloud deployment).
    static_dir: str | None = None

    # --- Database ------------------------------------------------------------------
    database_url: str = "sqlite+aiosqlite:///./data/nexa.db"
    database_echo: bool = False

    # --- LLM provider ----------------------------------------------------------------
    # "openai_compatible" talks to any OpenAI-compatible endpoint hosting open-source
    # models (Groq, OpenRouter, Together, vLLM, Ollama...). "mock" is deterministic and
    # needs no network: used for tests, CI and offline demos.
    llm_provider: Literal["openai_compatible", "mock"] = "mock"
    llm_base_url: str = "https://api.groq.com/openai/v1"
    llm_api_key: SecretStr | None = None
    # Groq retired llama-3.3-70b-versatile and llama-4-scout for free/developer tiers in 2026
    # (404 model_not_found); qwen3.8-27b is multimodal, so it serves both Fast and Vision.
    model_fast: str = "qwen/qwen3.8-27b"
    model_reasoning: str = "openai/gpt-oss-120b"
    model_vision: str = "qwen/qwen3.8-27b"
    llm_timeout_seconds: float = 60.0
    llm_max_retries: int = Field(default=3, ge=0, le=10)
    llm_retry_base_delay_seconds: float = 0.5
    llm_temperature: float = 0.4
    max_output_tokens: int = 2048
    max_tool_iterations: int = Field(default=4, ge=1, le=10)
    # Approximate token budget for the assembled prompt (long-context window management).
    context_max_tokens: int = 24_000
    max_images_per_request: int = 4

    # --- Safety ------------------------------------------------------------------------
    # Optional model-based moderation (e.g. "meta-llama/llama-guard-4-12b"). Heuristic
    # checks always run; the guard model adds a second opinion when configured.
    safety_model: str | None = None

    # --- Web search ---------------------------------------------------------------------
    search_provider: Literal["duckduckgo", "tavily", "mock"] = "duckduckgo"
    tavily_api_key: SecretStr | None = None
    search_max_results: int = Field(default=5, ge=1, le=10)
    search_timeout_seconds: float = 10.0

    # --- Uploads --------------------------------------------------------------------------
    upload_max_bytes: int = 10 * 1024 * 1024
    upload_retention_hours: int = 24
    document_max_chars: int = 500_000
    image_max_dimension: int = 1568

    # --- Abuse protection & ops -------------------------------------------------------------
    # Upper bound for JSON request bodies (a long conversation is well under 1 MB).
    max_request_bytes: int = 4 * 1024 * 1024
    rate_limit_chat_per_minute: int = 30
    rate_limit_upload_per_minute: int = 20
    # When set, GET /metrics requires "Authorization: Bearer <ops_token>".
    # In production the metrics endpoint is disabled unless a token is configured.
    ops_token: SecretStr | None = None

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @field_validator("database_url", mode="before")
    @classmethod
    def _normalise_database_url(cls, value: object) -> object:
        """Accept plain postgres URLs (as given by Render/Heroku/Fly) and use asyncpg."""
        if isinstance(value, str):
            for prefix in ("postgres://", "postgresql://"):
                if value.startswith(prefix):
                    return "postgresql+asyncpg://" + value[len(prefix) :]
        return value

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    def model_for(self, capability: str) -> str:
        return {
            "fast": self.model_fast,
            "reasoning": self.model_reasoning,
            "vision": self.model_vision,
        }[capability]


@lru_cache
def get_settings() -> Settings:
    return Settings()
