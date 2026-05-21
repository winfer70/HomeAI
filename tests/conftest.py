"""
conftest.py — shared pytest fixtures for the HomeAI test suite.

Fixtures provided:
    mock_settings   — a patched Settings instance with safe test values,
                      preventing any real .env file from influencing tests.
    memory_db       — an in-memory SQLite Memory instance (window=3).
    tmp_memory_db   — a Memory instance backed by a real temp file; useful for
                      persistence-across-instances tests.
"""
from __future__ import annotations

import pytest

from agent_brain import Memory


# ---------------------------------------------------------------------------
# Settings fixture
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_settings(monkeypatch):
    """
    Patch every external-service URL and credential in the global Settings
    singleton to deterministic test values.  Tests that need to change a
    specific field should call monkeypatch.setattr on top of this fixture.
    """
    import config as cfg_module

    monkeypatch.setattr(cfg_module.settings, "ollama_base_url", "http://ollama.test:11434")
    monkeypatch.setattr(cfg_module.settings, "ollama_model", "test-model")
    monkeypatch.setattr(cfg_module.settings, "llm_temperature", 0.0)
    monkeypatch.setattr(cfg_module.settings, "llm_timeout_s", 5)
    monkeypatch.setattr(cfg_module.settings, "react_max_iterations", 6)

    monkeypatch.setattr(cfg_module.settings, "ha_url", "http://ha.test:8123")
    monkeypatch.setattr(cfg_module.settings, "ha_token", "test-ha-token")
    monkeypatch.setattr(cfg_module.settings, "ha_timeout_s", 5)

    monkeypatch.setattr(cfg_module.settings, "searxng_url", "http://searxng.test:8888")
    monkeypatch.setattr(cfg_module.settings, "brave_api_key", "")
    monkeypatch.setattr(cfg_module.settings, "search_results", 3)
    monkeypatch.setattr(cfg_module.settings, "search_timeout_s", 5)

    monkeypatch.setattr(cfg_module.settings, "memory_db_path", ":memory:")
    monkeypatch.setattr(cfg_module.settings, "memory_window", 10)

    # Also patch the module-level _HA_HEADERS dict inside tools so it reflects
    # the test token (it is built at import time from settings.ha_token).
    import tools as tools_module
    monkeypatch.setitem(
        tools_module._HA_HEADERS,
        "Authorization",
        "Bearer test-ha-token",
    )

    return cfg_module.settings


# ---------------------------------------------------------------------------
# Memory fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def memory_db():
    """
    In-memory SQLite Memory instance with a sliding window of 3 turns.
    Closed automatically after each test.
    """
    mem = Memory(":memory:", window=3)
    yield mem
    mem.close()


@pytest.fixture()
def tmp_memory_db(tmp_path):
    """
    Memory instance backed by a real temporary file, for testing persistence
    across separate Memory instances.  The file is isolated to each test via
    pytest's tmp_path fixture.
    """
    db_file = str(tmp_path / "test_memory.db")
    mem = Memory(db_file, window=5)
    yield mem, db_file          # caller can open a second instance with db_file
    mem.close()
