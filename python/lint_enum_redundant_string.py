#!/usr/bin/env python3
"""Lint rule: disallow redundant enum string literals."""

from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path


IGNORED_DIR_NAMES = {
    ".git",
    ".hg",
    ".idea",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".svn",
    ".tox",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "node_modules",
    "venv",
}
TEST_DIR_NAMES = {"test", "tests"}


def load_enum_utils_module(enum_utils_path: Path):
    """Load the project enum utility module directly from its file path."""
    module_name = f"shared_enum_utils_{abs(hash(enum_utils_path.resolve()))}"
    spec = importlib.util.spec_from_file_location(module_name, enum_utils_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Failed to load enum utils from {enum_utils_path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _should_skip(path: Path, project_root: Path) -> bool:
    rel_parts = path.relative_to(project_root).parts
    return any(
        part in IGNORED_DIR_NAMES or part in TEST_DIR_NAMES or part.startswith(".")
        for part in rel_parts
    )


def iter_python_files(scan_root: Path, project_root: Path) -> list[Path]:
    """Return lintable Python files under a scan root."""
    return [
        py_file
        for py_file in sorted(scan_root.rglob("*.py"))
        if not _should_skip(py_file, project_root)
    ]


def main() -> None:
    print("Checking enum redundant string literal rule...")

    project_root = Path(os.environ.get("DEV_LINT_PROJECT_ROOT", Path.cwd())).resolve()

    # Find all src/ and top-level Python package roots that contain enum_utils.py
    enum_targets: list[Path] = []
    for candidate in sorted(project_root.rglob("common/enum_utils.py")):
        scan_root = candidate.parent.parent
        if not _should_skip(scan_root, project_root):
            enum_targets.append(scan_root)

    if not enum_targets:
        print("Skipping enum redundant string literal lint: no compatible enum_utils.py found.")
        sys.exit(0)

    all_violations: list[str] = []
    total_files = 0

    print("Scanning roots:")
    for scan_root in enum_targets:
        print(f"  - {scan_root.relative_to(project_root)}")
        enum_utils_module = load_enum_utils_module(scan_root / "common" / "enum_utils.py")
        violations = enum_utils_module.collect_enum_policy_violations(scan_root=scan_root)
        all_violations.extend(
            f"{scan_root.relative_to(project_root)}/{violation}" for violation in violations
        )
        total_files += len(iter_python_files(scan_root, project_root))

    print(f"Scanned {total_files} files across {len(enum_targets)} root(s).")

    if not all_violations:
        print("No redundant enum string literals found. OK.")
        sys.exit(0)

    print("\nERROR: Enum policy violations found.\n")
    for violation in all_violations:
        print(f"  {violation}")

    print("\nHOW TO FIX:")
    print("  1. Define enum members with auto(), do not manually repeat the name text.")
    print("  2. Use the shared _UpperNameStrEnum only for exact upper-name values.")
    print(
        "  3. Temporary exception only with inline "
        f"'# {enum_utils_module.NOQA_ENUM_STRING}' or '# {enum_utils_module.NOQA_ENUM_BASE}' and a reason."
    )
    print(f"\nLint failed: {len(all_violations)} violations found.")
    sys.exit(1)


if __name__ == "__main__":
    main()
