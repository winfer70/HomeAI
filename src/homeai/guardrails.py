from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_ENTITY_PATTERN = re.compile(r"\balarm(?:_control_panel)?\.[A-Za-z0-9_]+\b", re.IGNORECASE)
_SATEL_PATTERN = re.compile(r"\b(?:satel|integra)\b", re.IGNORECASE)
_CRITICAL_PATTERN = re.compile(r"\bcritical life shield\b", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class Violation:
    """One forbidden alarm-reference match found during scanning."""

    source: str
    rule: str
    match: str
    line: int | None = None
    path: str | None = None

    def format(self) -> str:
        location = self.source
        if self.line is not None:
            location = f"{location}:{self.line}"
        if self.path:
            location = f"{location} [{self.path}]"
        return f"{location}: {self.rule}: {self.match}"


class AlarmExposureError(ValueError):
    """Raised when forbidden alarm-related content is detected."""


def _iter_patterns() -> tuple[tuple[re.Pattern[str], str], ...]:
    return (
        (_ENTITY_PATTERN, "forbidden alarm entity id"),
        (_SATEL_PATTERN, "forbidden Satel/Integra reference"),
        (_CRITICAL_PATTERN, "forbidden Critical Life Shield reference"),
    )


def scan_text(text: str, *, source: str) -> list[Violation]:
    """Scan raw text and return all forbidden matches."""
    violations: list[Violation] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        for pattern, rule in _iter_patterns():
            for match in pattern.finditer(line):
                violations.append(
                    Violation(
                        source=source,
                        rule=rule,
                        match=match.group(0),
                        line=line_number,
                    )
                )
    return violations


def scan_path(path: Path) -> list[Violation]:
    """Scan one file path by reading it as text."""
    if not path.is_file():
        return []
    text = path.read_text(encoding="utf-8", errors="ignore")
    return scan_text(text, source=str(path))


def scan_paths(paths: Sequence[Path]) -> list[Violation]:
    """Scan a sequence of file paths."""
    violations: list[Violation] = []
    for path in paths:
        violations.extend(scan_path(path))
    return violations


def _scan_any(
    value: Any,
    *,
    source: str,
    path: str = "",
    seen: set[int] | None = None,
) -> list[Violation]:
    seen = seen or set()
    object_id = id(value)
    if object_id in seen:
        return []
    seen.add(object_id)

    if isinstance(value, str):
        return [
            Violation(
                source=source,
                rule=violation.rule,
                match=violation.match,
                line=violation.line,
                path=path or None,
            )
            for violation in scan_text(value, source=source)
        ]

    if isinstance(value, Mapping):
        violations: list[Violation] = []
        for key, item in value.items():
            key_path = f"{path}.{key}" if path else str(key)
            violations.extend(_scan_any(key, source=source, path=key_path, seen=seen))
            violations.extend(_scan_any(item, source=source, path=key_path, seen=seen))
        return violations

    if isinstance(value, (list, tuple, set, frozenset)):
        violations = []
        for index, item in enumerate(value):
            item_path = f"{path}[{index}]" if path else f"[{index}]"
            violations.extend(_scan_any(item, source=source, path=item_path, seen=seen))
        return violations

    return []


def scan_payload(payload: Any, *, source: str = "payload") -> list[Violation]:
    """Scan an arbitrary JSON-like payload for forbidden references."""
    return _scan_any(payload, source=source)


def assert_no_alarm_exposure(payload: Any, *, source: str = "payload") -> None:
    """Raise if the payload contains any forbidden alarm references."""
    violations = scan_payload(payload, source=source)
    if violations:
        details = "\n".join(violation.format() for violation in violations)
        raise AlarmExposureError(details)

