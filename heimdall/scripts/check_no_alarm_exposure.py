#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from homeai.guardrails import scan_paths  # noqa: E402


def _collect_paths(arguments: list[str]) -> list[Path]:
    if not arguments:
        # Default to scanning the whole heimdall/ tree. Must go through the
        # same directory-expansion branch below (rglob) rather than
        # returning the bare directory Path directly - scan_path() treats
        # anything that isn't is_file() as a no-op, so an unexpanded
        # directory here would silently check zero files and always report
        # a clean pass (found while validating Task 4's changes).
        arguments = ["heimdall"]

    paths: list[Path] = []
    for argument in arguments:
        path = Path(argument)
        if not path.exists():
            raise FileNotFoundError(f"Path does not exist: {argument}")
        if path.is_dir():
            paths.extend(sorted(candidate for candidate in path.rglob("*") if candidate.is_file()))
        else:
            paths.append(path)
    return paths


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Fail if Heimdall files or payloads reference the project's "
            "disallowed home-alarm system, its entities, or its automation "
            "(see the non-negotiable guardrail note in the project brief - "
            "the vendor name is intentionally not spelled out here so this "
            "script's own help text doesn't trip its own check)."
        )
    )
    parser.add_argument(
        "paths",
        nargs="*",
        help="Files or directories to scan. Defaults to the heimdall/ tree.",
    )
    args = parser.parse_args(argv)

    try:
        paths = _collect_paths(args.paths)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    violations = scan_paths(paths)
    if violations:
        for violation in violations:
            print(violation.format(), file=sys.stderr)
        return 1

    print(f"Checked {len(paths)} file(s); no forbidden alarm exposure found.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

