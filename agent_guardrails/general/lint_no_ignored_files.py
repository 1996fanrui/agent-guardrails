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

    Batch paths so process startup does not dominate large pre-commit runs.
    """
    if not paths:
        return []

    ignored = subprocess.run(
        ["git", "check-ignore", "-z", "--no-index", "--stdin"],
        input="\0".join(paths) + "\0",
        capture_output=True,
        text=True,
    )
    if ignored.returncode == 1:
        return []
    if ignored.returncode != 0:
        message = ignored.stderr.strip() or "git check-ignore failed"
        raise RuntimeError(f"{message} (exit code {ignored.returncode})")
    ignored_paths = [path for path in ignored.stdout.split("\0") if path]
    if not ignored_paths or any(path not in paths for path in ignored_paths):
        raise RuntimeError("git check-ignore returned invalid ignored paths")

    details = subprocess.run(
        ["git", "check-ignore", "-z", "-v", "--no-index", "--stdin"],
        input="\0".join(ignored_paths) + "\0",
        capture_output=True,
        text=True,
    )
    if details.returncode != 0:
        message = details.stderr.strip() or "git check-ignore failed"
        raise RuntimeError(f"{message} (exit code {details.returncode})")

    fields = details.stdout.split("\0")
    if fields[-1] != "" or len(fields) != len(ignored_paths) * _VERBOSE_FIELDS + 1:
        raise RuntimeError("git check-ignore returned incomplete verbose records")
    violations: list[str] = []
    for index in range(0, len(fields) - 1, _VERBOSE_FIELDS):
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
