# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Fail on known GNU-only shell syntax in repository scripts.

Usage:
    uv run lint_shell_portability.py FILE [...]
"""

from __future__ import annotations

import re
import sys
from pathlib import Path


ALLOW_COMMENT = "noqa: shell-portability"
RULES: tuple[tuple[str, re.Pattern[str], str], ...] = (
    ("SHP001", re.compile(r"\breadlink\s+-f\b"), "Use a portable realpath helper instead of `readlink -f`."),
    ("SHP002", re.compile(r"\bsed\s+-i(?:\s|$|['\"])"), "Avoid `sed -i`; use a portable temp-file or language helper."),
    ("SHP003", re.compile(r"\bdate\s+-d\b"), "Avoid GNU `date -d`; parse timestamps with Python or another portable helper."),
    ("SHP004", re.compile(r"\bstat\s+-c\b"), "Avoid GNU `stat -c`; use a portable helper."),
    ("SHP005", re.compile(r"\bxargs\s+-r\b"), "Avoid GNU `xargs -r`; handle empty input explicitly in shell."),
)


def check_file(path: Path) -> list[str]:
    """Return portability violations for the given shell file."""
    violations: list[str] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if ALLOW_COMMENT in line:
            continue
        for rule_id, pattern, message in RULES:
            if pattern.search(line):
                violations.append(
                    f"{path}:{line_number}: {rule_id} {message}\n"
                    f"    {line.strip()}"
                )
    return violations


def main() -> int:
    files = [Path(file_name) for file_name in sys.argv[1:]]
    if not files:
        return 0

    violations: list[str] = []
    for path in files:
        violations.extend(check_file(path))

    if violations:
        print("Shell portability lint failed:")
        print("\n".join(violations))
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
