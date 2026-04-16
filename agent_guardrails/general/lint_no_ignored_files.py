# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Lint rule: prevent gitignored files from being committed.

Usage:
    uv run lint_no_ignored_files.py FILE [...]
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def check_file(path: Path) -> list[str]:
    """Return a violation if *path* matches a .gitignore rule."""
    result = subprocess.run(
        ["git", "check-ignore", "-v", "--no-index", "--", str(path)],
        capture_output=True,
        text=True,
    )
    # exit 0 means the path IS ignored
    if result.returncode == 0:
        detail = result.stdout.strip()
        return [f"{path}: matched by {detail}"]
    return []


def main() -> int:
    files = [Path(f) for f in sys.argv[1:]]
    if not files:
        return 0

    violations: list[str] = []
    for path in files:
        violations.extend(check_file(path))

    if violations:
        print("Ignored files must not be committed.")
        print("Remove these paths from the Git index before continuing:")
        for violation in violations:
            print(f"  - {violation}")
        print()
        print("Suggested fix:")
        print("  git rm --cached -- <path>")
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
