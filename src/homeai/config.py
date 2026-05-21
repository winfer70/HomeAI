from __future__ import annotations

import warnings

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_VALID_LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR"}


class Settings(BaseSettings):
    """Application-wide configuration loaded from environment variables or a .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Ollama / local LLM
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen3:8b"
    llm_temperature: float = 0.1
    llm_timeout_s: int = 90
    react_max_iterations: int = 6

    # Home Assistant
    ha_url: str = "http://homeassistant.local:8123"
    ha_token: str = Field(default="", description="HA long-lived access token")
    ha_timeout_s: int = 10

    # Web search — SearXNG (primary) + Brave API (fallback)
    searxng_url: str = "http://localhost:8888"
    brave_api_key: str = ""
    search_results: int = 5
    search_timeout_s: int = 15

    # Conversation memory
    memory_db_path: str = "./homeai_memory.db"
    memory_window: int = 10  # turns kept in LLM context

    log_level: str = "INFO"
    log_file: str = "./homeai.log"

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Reject log_level values that are not recognised Python logging levels."""
        upper = v.upper()
        if upper not in _VALID_LOG_LEVELS:
            raise ValueError(
                f"log_level must be one of {sorted(_VALID_LOG_LEVELS)}, got {v!r}"
            )
        return upper

    @model_validator(mode="after")
    def warn_if_no_search(self) -> "Settings":
        """Emit a warning when no web-search backend is configured."""
        if not self.searxng_url and not self.brave_api_key:
            warnings.warn(
                "Neither searxng_url nor brave_api_key is set — "
                "web search will be unavailable.",
                stacklevel=2,
            )
        return self


settings = Settings()
