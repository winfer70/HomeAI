from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ToolResult:
    """Encapsulates the outcome of a single tool invocation."""

    success: bool
    data: str
    error: str | None = None

    def to_llm_text(self) -> str:
        """Return the text representation of this result for LLM consumption."""
        if self.success:
            return self.data
        return f"Error: {self.error or 'unknown error'}"
