"""DEPRECATED — use src/homeai/config.py instead.

Legacy configuration module. Application-wide settings loaded from environment variables
or .env file. This root-level copy is outdated and missing validators present in the
package version at src/homeai/config.py.
"""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
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


settings = Settings()
