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

# ``git check-ignore -z -v`` emits four NUL-separated fields per ignored path.
_VERBOSE_FIELDS = 4


def find_ignored(paths: list[str]) -> list[str]:
    """Return a violation line for each path in *paths* matching a .gitignore rule.

    All paths are passed to a single ``git check-ignore`` process. Spawning one
    process per path instead makes this the dominant cost of a pre-commit run on
    repositories with thousands of files.
    """
    if not paths:
        return []

    result = subprocess.run(
        ["git", "check-ignore", "-z", "-v", "--no-index", "--stdin"],
        input="\0".join(paths) + "\0",
        capture_output=True,
        text=True,
    )
    # Exit code 1 means no path was ignored; anything above that is a real
    # failure (bad usage, not a repository, ...) that must not pass silently.
    if result.returncode > 1:
        message = result.stderr.strip() or "git check-ignore failed"
        raise RuntimeError(f"{message} (exit code {result.returncode})")

    fields = result.stdout.split("\0")
    violations: list[str] = []
    # The trailing NUL terminator leaves an empty final element; ignore any
    # partial record rather than silently dropping half a violation.
    for index in range(0, len(fields) - _VERBOSE_FIELDS + 1, _VERBOSE_FIELDS):
        source, line, pattern, path = fields[index:index + _VERBOSE_FIELDS]
        violations.append(f"{path}: matched by {source}:{line}:{pattern}\t{path}")
    return violations


def main() -> int:
    violations = find_ignored(sys.argv[1:])
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
