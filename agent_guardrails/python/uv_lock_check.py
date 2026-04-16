# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Pre-commit hook: verify uv.lock is in sync with pyproject.toml.

Receives changed file paths, walks up each file's directory tree to find the
nearest pyproject.toml, and runs `uv lock --check` once per discovered project.
Projects without a uv.lock are skipped (they may use a different package manager).

Usage:
    uv run uv_lock_check.py FILE [...]
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def find_uv_project_dir(file_path: Path) -> Path | None:
    """Return the nearest ancestor directory that contains both pyproject.toml and uv.lock."""
    # Resolve so that parent traversal works correctly regardless of cwd.
    resolved = file_path.resolve()
    candidates = [resolved] if resolved.is_dir() else [resolved.parent]
    candidates += list(candidates[0].parents)

    for directory in candidates:
        if (directory / "pyproject.toml").exists() and (directory / "uv.lock").exists():
            return directory
    return None


def main() -> int:
    files = [Path(f) for f in sys.argv[1:]]

    checked: set[Path] = set()
    failed = False

    for file in files:
        project_dir = find_uv_project_dir(file)
        if project_dir is None or project_dir in checked:
            continue

        checked.add(project_dir)
        result = subprocess.run(
            ["uv", "lock", "--check", "--project", str(project_dir)],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            sys.stderr.write(
                f"uv.lock is out of sync with pyproject.toml in {project_dir}:\n"
            )
            if result.stderr:
                sys.stderr.write(result.stderr)
            failed = True

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
