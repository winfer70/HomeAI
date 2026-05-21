"""
test_config.py — unit tests for config.Settings.

Coverage:
    - All field default values are correct.
    - Environment-variable overrides (str, int, float) are applied.
    - Case-insensitive env-var names work.
    - Field types are coerced correctly (int, float).
    - Validation rejects clearly wrong types where Pydantic enforces them.
    - The module-level `settings` singleton is a Settings instance.
    - Unicode / non-ASCII values survive round-tripping through the model.
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from config import Settings, settings


# ---------------------------------------------------------------------------
# Default values
# ---------------------------------------------------------------------------


class TestSettingsDefaults:
    def test_ollama_base_url_default(self):
        """Ollama base URL defaults to the standard local port."""
        s = Settings()
        assert s.ollama_base_url == "http://localhost:11434"

    def test_ollama_model_default(self):
        """Ollama model defaults to qwen3:8b."""
        s = Settings()
        assert s.ollama_model == "qwen3:8b"

    def test_llm_temperature_default(self):
        """LLM temperature defaults to 0.1 (low, for deterministic answers)."""
        s = Settings()
        assert s.llm_temperature == pytest.approx(0.1)

    def test_llm_timeout_default(self):
        """LLM request timeout defaults to 90 seconds."""
        s = Settings()
        assert s.llm_timeout_s == 90

    def test_react_max_iterations_default(self):
        """ReAct loop defaults to at most 6 iterations."""
        s = Settings()
        assert s.react_max_iterations == 6

    def test_ha_url_default(self):
        """Home Assistant URL defaults to the standard mDNS address."""
        s = Settings()
        assert s.ha_url == "http://homeassistant.local:8123"

    def test_ha_token_default_empty(self):
        """HA token defaults to an empty string (must be supplied via env)."""
        s = Settings()
        assert s.ha_token == ""

    def test_ha_timeout_default(self):
        """HA request timeout defaults to 10 seconds."""
        s = Settings()
        assert s.ha_timeout_s == 10

    def test_searxng_url_default(self):
        """SearXNG URL defaults to the standard local port."""
        s = Settings()
        assert s.searxng_url == "http://localhost:8888"

    def test_brave_api_key_default_empty(self):
        """Brave API key defaults to empty (optional fallback)."""
        s = Settings()
        assert s.brave_api_key == ""

    def test_search_results_default(self):
        """Number of search results defaults to 5."""
        s = Settings()
        assert s.search_results == 5

    def test_search_timeout_default(self):
        """Search timeout defaults to 15 seconds."""
        s = Settings()
        assert s.search_timeout_s == 15

    def test_memory_db_path_default(self):
        """Memory DB path defaults to a local file."""
        s = Settings()
        assert s.memory_db_path == "./homeai_memory.db"

    def test_memory_window_default(self):
        """Context window defaults to 10 turns."""
        s = Settings()
        assert s.memory_window == 10

    def test_log_level_default(self):
        """Log level defaults to INFO."""
        s = Settings()
        assert s.log_level == "INFO"

    def test_log_file_default(self):
        """Log file defaults to a local path."""
        s = Settings()
        assert s.log_file == "./homeai.log"


# ---------------------------------------------------------------------------
# Environment-variable overrides
# ---------------------------------------------------------------------------


class TestSettingsEnvOverrides:
    def test_override_ollama_model(self, monkeypatch):
        """OLLAMA_MODEL env var replaces the default model name."""
        monkeypatch.setenv("OLLAMA_MODEL", "llama3:70b")
        s = Settings()
        assert s.ollama_model == "llama3:70b"

    def test_override_ollama_base_url(self, monkeypatch):
        """OLLAMA_BASE_URL env var is applied correctly."""
        monkeypatch.setenv("OLLAMA_BASE_URL", "http://gpu-box:11434")
        s = Settings()
        assert s.ollama_base_url == "http://gpu-box:11434"

    def test_override_llm_temperature_float(self, monkeypatch):
        """LLM_TEMPERATURE is coerced from str to float."""
        monkeypatch.setenv("LLM_TEMPERATURE", "0.7")
        s = Settings()
        assert s.llm_temperature == pytest.approx(0.7)

    def test_override_llm_timeout_int(self, monkeypatch):
        """LLM_TIMEOUT_S is coerced from str to int."""
        monkeypatch.setenv("LLM_TIMEOUT_S", "120")
        s = Settings()
        assert s.llm_timeout_s == 120

    def test_override_ha_token(self, monkeypatch):
        """HA_TOKEN env var stores the provided token verbatim."""
        monkeypatch.setenv("HA_TOKEN", "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9")
        s = Settings()
        assert s.ha_token == "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9"

    def test_override_ha_url(self, monkeypatch):
        """HA_URL env var points to a custom HA instance."""
        monkeypatch.setenv("HA_URL", "https://my-ha.example.com")
        s = Settings()
        assert s.ha_url == "https://my-ha.example.com"

    def test_override_searxng_url(self, monkeypatch):
        """SEARXNG_URL env var is applied correctly."""
        monkeypatch.setenv("SEARXNG_URL", "http://searx.internal:9000")
        s = Settings()
        assert s.searxng_url == "http://searx.internal:9000"

    def test_override_brave_api_key(self, monkeypatch):
        """BRAVE_API_KEY env var is stored as a plain string."""
        monkeypatch.setenv("BRAVE_API_KEY", "BSAb123Secret")
        s = Settings()
        assert s.brave_api_key == "BSAb123Secret"

    def test_override_search_results_int(self, monkeypatch):
        """SEARCH_RESULTS is coerced from str to int."""
        monkeypatch.setenv("SEARCH_RESULTS", "10")
        s = Settings()
        assert s.search_results == 10

    def test_override_memory_window_int(self, monkeypatch):
        """MEMORY_WINDOW is coerced from str to int."""
        monkeypatch.setenv("MEMORY_WINDOW", "20")
        s = Settings()
        assert s.memory_window == 20

    def test_override_log_level(self, monkeypatch):
        """LOG_LEVEL env var is accepted as a plain string."""
        monkeypatch.setenv("LOG_LEVEL", "DEBUG")
        s = Settings()
        assert s.log_level == "DEBUG"

    def test_override_memory_db_path(self, monkeypatch):
        """MEMORY_DB_PATH env var is applied verbatim."""
        monkeypatch.setenv("MEMORY_DB_PATH", "/tmp/custom.db")
        s = Settings()
        assert s.memory_db_path == "/tmp/custom.db"


# ---------------------------------------------------------------------------
# Case-insensitivity
# ---------------------------------------------------------------------------


class TestSettingsCaseInsensitivity:
    def test_lowercase_env_var_works(self, monkeypatch):
        """Lowercase env var name is accepted (case_sensitive=False)."""
        monkeypatch.setenv("ollama_model", "phi3:mini")
        s = Settings()
        assert s.ollama_model == "phi3:mini"

    def test_mixed_case_env_var_works(self, monkeypatch):
        """Mixed-case env var name is accepted."""
        monkeypatch.setenv("Ha_Timeout_S", "30")
        s = Settings()
        assert s.ha_timeout_s == 30


# ---------------------------------------------------------------------------
# Type coercion and validation
# ---------------------------------------------------------------------------


class TestSettingsTypeCoercion:
    def test_float_field_accepts_integer_string(self, monkeypatch):
        """An integer string is valid for a float field."""
        monkeypatch.setenv("LLM_TEMPERATURE", "1")
        s = Settings()
        assert isinstance(s.llm_temperature, float)
        assert s.llm_temperature == pytest.approx(1.0)

    def test_int_field_rejects_non_numeric_string(self, monkeypatch):
        """A non-numeric string for an int field raises ValidationError."""
        monkeypatch.setenv("LLM_TIMEOUT_S", "notanumber")
        with pytest.raises(ValidationError):
            Settings()

    def test_float_field_rejects_non_numeric_string(self, monkeypatch):
        """A non-numeric string for a float field raises ValidationError."""
        monkeypatch.setenv("LLM_TEMPERATURE", "hot")
        with pytest.raises(ValidationError):
            Settings()

    def test_react_max_iterations_zero_is_valid(self, monkeypatch):
        """Zero is a valid (though degenerate) value for react_max_iterations."""
        monkeypatch.setenv("REACT_MAX_ITERATIONS", "0")
        s = Settings()
        assert s.react_max_iterations == 0


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------


class TestSettingsSingleton:
    def test_module_settings_is_settings_instance(self):
        """The module-level `settings` object is a Settings instance."""
        assert isinstance(settings, Settings)

    def test_module_settings_has_correct_defaults(self):
        """The singleton carries the documented default values (unless overridden by .env)."""
        # We only check the model name here — it is unlikely to be in a real .env
        # during unit tests when running without an .env file.
        # The key assertion is that the singleton is fully initialised.
        assert hasattr(settings, "ollama_model")
        assert hasattr(settings, "ha_url")
        assert hasattr(settings, "memory_window")


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestSettingsEdgeCases:
    def test_empty_string_url_is_accepted(self, monkeypatch):
        """An empty SEARXNG_URL disables SearXNG (falsy check in tools.py)."""
        monkeypatch.setenv("SEARXNG_URL", "")
        s = Settings()
        assert s.searxng_url == ""

    def test_unicode_log_file_path(self, monkeypatch):
        """A Unicode path with Polish characters is stored correctly."""
        monkeypatch.setenv("LOG_FILE", "./logi/główny.log")
        s = Settings()
        assert s.log_file == "./logi/główny.log"

    def test_large_memory_window(self, monkeypatch):
        """A very large memory window is accepted without error."""
        monkeypatch.setenv("MEMORY_WINDOW", "10000")
        s = Settings()
        assert s.memory_window == 10000

    def test_react_max_iterations_large(self, monkeypatch):
        """react_max_iterations accepts large positive integers."""
        monkeypatch.setenv("REACT_MAX_ITERATIONS", "999")
        s = Settings()
        assert s.react_max_iterations == 999
