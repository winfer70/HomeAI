"""
test_memory.py — unit tests for agent_brain.Memory.

The Memory class wraps SQLite with a sliding window over conversation turns.
Each test uses an isolated in-memory or tmp_path-backed database so tests
cannot interfere with each other.

Coverage:
    - add() persists a turn; recent() retrieves it.
    - Multiple adds are returned in chronological order.
    - Sliding window: only the last (window * 2) messages are returned.
    - Window of 1 keeps only the last user+assistant pair.
    - Empty database: recent() returns an empty list.
    - Persistence: a second Memory instance on the same file sees prior turns.
    - close() can be called multiple times without raising.
    - Role values are preserved exactly (user / assistant / system).
    - Content with Polish / Unicode characters is stored and retrieved correctly.
    - Very long content is stored without truncation.
    - Window=0 edge case: recent() returns an empty list.
    - add() with empty string content is accepted.
"""
from __future__ import annotations

import pytest

from agent_brain import Memory


# ---------------------------------------------------------------------------
# Basic add / recent
# ---------------------------------------------------------------------------


class TestMemoryAddRecent:
    def test_single_add_is_retrievable(self, memory_db):
        """A single added turn is returned by recent()."""
        memory_db.add("user", "Hello")
        turns = memory_db.recent()
        assert len(turns) == 1
        assert turns[0] == {"role": "user", "content": "Hello"}

    def test_two_turns_returned_in_chronological_order(self, memory_db):
        """Two turns come back oldest-first (chronological), not newest-first."""
        memory_db.add("user", "First")
        memory_db.add("assistant", "Second")
        turns = memory_db.recent()
        assert turns[0]["content"] == "First"
        assert turns[1]["content"] == "Second"

    def test_role_field_preserved_exactly(self, memory_db):
        """Role strings are stored and returned verbatim."""
        memory_db.add("user", "u")
        memory_db.add("assistant", "a")
        roles = [t["role"] for t in memory_db.recent()]
        assert roles == ["user", "assistant"]

    def test_content_with_polish_characters(self, memory_db):
        """Polish diacritics in content are stored and retrieved without corruption."""
        text = "Włącz światło w salonie, proszę."
        memory_db.add("user", text)
        turns = memory_db.recent()
        assert turns[0]["content"] == text

    def test_content_with_mixed_unicode(self, memory_db):
        """Emoji and non-Latin characters round-trip correctly."""
        text = "Jaka jest temperatura? 🌡️ — 22°C"
        memory_db.add("assistant", text)
        assert memory_db.recent()[0]["content"] == text

    def test_empty_content_string_is_accepted(self, memory_db):
        """add() with an empty string does not raise and is retrievable."""
        memory_db.add("user", "")
        turns = memory_db.recent()
        assert turns[0]["content"] == ""

    def test_very_long_content_stored_without_truncation(self, memory_db):
        """Strings longer than typical column sizes are stored in full."""
        long_text = "A" * 100_000
        memory_db.add("user", long_text)
        turns = memory_db.recent()
        assert turns[0]["content"] == long_text


# ---------------------------------------------------------------------------
# Empty state
# ---------------------------------------------------------------------------


class TestMemoryEmptyState:
    def test_recent_on_empty_db_returns_empty_list(self, memory_db):
        """recent() on a freshly created Memory returns []."""
        assert memory_db.recent() == []

    def test_recent_returns_list_type(self, memory_db):
        """recent() always returns a list, even when empty."""
        assert isinstance(memory_db.recent(), list)


# ---------------------------------------------------------------------------
# Sliding-window clamping
# ---------------------------------------------------------------------------


class TestMemorySlidingWindow:
    def test_window_limits_returned_turns(self):
        """With window=2, at most 4 messages (2 pairs) are returned."""
        mem = Memory(":memory:", window=2)
        for i in range(10):
            role = "user" if i % 2 == 0 else "assistant"
            mem.add(role, f"msg{i}")
        turns = mem.recent()
        mem.close()
        assert len(turns) == 4

    def test_window_returns_most_recent_turns(self):
        """The returned turns are the N most recent, not the oldest."""
        mem = Memory(":memory:", window=1)
        mem.add("user", "old user")
        mem.add("assistant", "old assistant")
        mem.add("user", "new user")
        mem.add("assistant", "new assistant")
        turns = mem.recent()
        mem.close()
        assert len(turns) == 2
        assert turns[0]["content"] == "new user"
        assert turns[1]["content"] == "new assistant"

    def test_window_three_with_fewer_messages(self, memory_db):
        """When fewer messages exist than window*2, all messages are returned."""
        memory_db.add("user", "A")
        memory_db.add("assistant", "B")
        turns = memory_db.recent()
        assert len(turns) == 2

    def test_window_exactly_full(self):
        """When the number of messages equals window*2, all are returned."""
        mem = Memory(":memory:", window=3)
        for i in range(6):
            role = "user" if i % 2 == 0 else "assistant"
            mem.add(role, f"m{i}")
        turns = mem.recent()
        mem.close()
        assert len(turns) == 6

    def test_window_one_returns_at_most_two_messages(self):
        """window=1 means at most 1 user + 1 assistant message returned."""
        mem = Memory(":memory:", window=1)
        mem.add("user", "q1")
        mem.add("assistant", "a1")
        mem.add("user", "q2")
        mem.add("assistant", "a2")
        mem.add("user", "q3")
        mem.add("assistant", "a3")
        turns = mem.recent()
        mem.close()
        assert len(turns) == 2

    def test_window_zero_returns_empty_list(self):
        """window=0 edge case: LIMIT 0 returns no rows."""
        mem = Memory(":memory:", window=0)
        mem.add("user", "hello")
        turns = mem.recent()
        mem.close()
        assert turns == []

    def test_chronological_order_preserved_after_clamping(self):
        """After window clamping the surviving turns are still oldest-first."""
        mem = Memory(":memory:", window=2)
        messages = [f"msg{i}" for i in range(8)]
        for i, msg in enumerate(messages):
            role = "user" if i % 2 == 0 else "assistant"
            mem.add(role, msg)
        turns = mem.recent()
        mem.close()
        # The 4 returned messages should be in increasing order
        contents = [t["content"] for t in turns]
        assert contents == ["msg4", "msg5", "msg6", "msg7"]


# ---------------------------------------------------------------------------
# Persistence across instances
# ---------------------------------------------------------------------------


class TestMemoryPersistence:
    def test_second_instance_sees_turns_from_first(self, tmp_memory_db):
        """Turns added by one Memory instance are visible to a second instance
        opened on the same database file."""
        mem1, db_file = tmp_memory_db
        mem1.add("user", "persisted message")
        mem1.close()

        mem2 = Memory(db_file, window=5)
        turns = mem2.recent()
        mem2.close()

        assert any(t["content"] == "persisted message" for t in turns)

    def test_second_instance_can_add_turns(self, tmp_memory_db):
        """A second Memory instance can add new turns that a third instance sees."""
        mem1, db_file = tmp_memory_db
        mem1.add("user", "from first")
        mem1.close()

        mem2 = Memory(db_file, window=5)
        mem2.add("assistant", "from second")
        mem2.close()

        mem3 = Memory(db_file, window=5)
        contents = [t["content"] for t in mem3.recent()]
        mem3.close()

        assert "from first" in contents
        assert "from second" in contents

    def test_multiple_conversations_stored_sequentially(self, tmp_memory_db):
        """All turns from a multi-turn conversation persist to disk."""
        mem, db_file = tmp_memory_db
        pairs = [
            ("user", "Cześć!"),
            ("assistant", "Cześć! W czym mogę pomóc?"),
            ("user", "Jaka jest pogoda?"),
            ("assistant", "Sprawdzam..."),
        ]
        for role, content in pairs:
            mem.add(role, content)
        mem.close()

        mem2 = Memory(db_file, window=10)
        turns = mem2.recent()
        mem2.close()

        assert len(turns) == 4
        for i, (role, content) in enumerate(pairs):
            assert turns[i]["role"] == role
            assert turns[i]["content"] == content


# ---------------------------------------------------------------------------
# close() behaviour
# ---------------------------------------------------------------------------


class TestMemoryClose:
    def test_close_does_not_raise(self, memory_db):
        """close() on an open connection completes without raising."""
        memory_db.close()   # fixture calls close() again in teardown — that's fine

    def test_table_created_on_init(self, memory_db):
        """The 'turns' table exists after __init__ (schema migration is idempotent)."""
        # Verify by adding and retrieving successfully — no sqlite3 error raised
        memory_db.add("user", "schema check")
        assert len(memory_db.recent()) == 1
