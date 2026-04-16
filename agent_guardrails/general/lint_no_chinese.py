# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Lint rule: disallow Chinese characters in source code and UI files.

Usage:
    uv run lint_no_chinese.py FILE [...]
"""

from __future__ import annotations

import re
import sys
from pathlib import Path


CHINESE_CHAR_PATTERN = re.compile(r"[\u3400-\u4DBF\u4E00-\u9FFF\uF900-\uFAFF]")


def build_violation(path: Path, line_no: int, line: str) -> str:
    """Format a user-friendly lint error."""
    preview = line.strip()
    return (
        f"{path}:{line_no} contains Chinese characters. "
        f"Replace them with English. Source: {preview}"
    )


def scan_file(path: Path) -> list[str]:
    """Collect all lines containing Chinese characters."""
    violations: list[str] = []
    try:
        raw_content = path.read_bytes()
    except OSError as exc:
        raise RuntimeError(f"Failed to read {path}: {exc}") from exc

    if b"\x00" in raw_content:
        return violations

    try:
        content = raw_content.decode("utf-8")
    except UnicodeDecodeError:
        return violations

    for line_no, line in enumerate(content.splitlines(), start=1):
        if CHINESE_CHAR_PATTERN.search(line):
            violations.append(build_violation(path, line_no, line))
    return violations


def main() -> int:
    files = [Path(file_name) for file_name in sys.argv[1:]]
    if not files:
        return 0

    violations: list[str] = []
    for path in files:
        violations.extend(scan_file(path))

    if violations:
        print("Chinese character lint failed:")
        for violation in violations:
            print(f"  - {violation}")
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
