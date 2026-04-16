# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Validate Python entrypoints in pre-commit YAML files use language: python.

Usage:
    uv run lint_pre_commit_hook_languages.py FILE [...]
"""

from __future__ import annotations

import re
import sys
from pathlib import Path


HOOK_START_PATTERN = re.compile(r"^(?P<indent>\s*)- id:\s*(?P<hook_id>.+?)\s*$")
FIELD_PATTERN = re.compile(r"^(?P<indent>\s+)(?P<key>entry|language):\s*(?P<value>.+?)\s*$")
LIST_ITEM_PATTERN = re.compile(r"^(?P<indent>\s*)-\s")
PYTHON_MODULE_ENTRY_PATTERN = re.compile(r"^python(?:\d+(?:\.\d+)?)?\s+-m\s+\S+")


def normalize_scalar(raw_value: str) -> str:
    """Return a plain scalar string without inline comments or matching quotes."""
    value = raw_value.split(" #", maxsplit=1)[0].strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def is_python_entrypoint(entry: str) -> bool:
    """Return True when the hook entry executes Python code."""
    return entry.endswith(".py") or PYTHON_MODULE_ENTRY_PATTERN.match(entry) is not None


def check_file(path: Path) -> list[str]:
    """Return language-selection violations for a pre-commit hook manifest."""
    lines = path.read_text(encoding="utf-8").splitlines()
    violations: list[str] = []

    current_hook_id: str | None = None
    current_hook_line = 0
    current_hook_indent = -1
    current_entry: str | None = None
    current_entry_line = 0
    current_language: str | None = None
    current_language_line = 0

    def flush_current_hook() -> None:
        nonlocal current_hook_id
        nonlocal current_hook_line
        nonlocal current_hook_indent
        nonlocal current_entry
        nonlocal current_entry_line
        nonlocal current_language
        nonlocal current_language_line

        if current_hook_id is None or current_entry is None or not is_python_entrypoint(current_entry):
            current_hook_id = None
            current_hook_line = 0
            current_hook_indent = -1
            current_entry = None
            current_entry_line = 0
            current_language = None
            current_language_line = 0
            return

        if current_language != "python":
            report_line = current_language_line or current_entry_line or current_hook_line
            actual_language = current_language or "<missing>"
            violations.append(
                f"{path}:{report_line} hook '{current_hook_id}' uses Python entry "
                f"'{current_entry}' but language is '{actual_language}'. "
                "Python entrypoints in this repository must use 'language: python'."
            )

        current_hook_id = None
        current_hook_line = 0
        current_hook_indent = -1
        current_entry = None
        current_entry_line = 0
        current_language = None
        current_language_line = 0

    for line_number, line in enumerate(lines, start=1):
        hook_match = HOOK_START_PATTERN.match(line)
        if hook_match is not None:
            flush_current_hook()
            current_hook_id = normalize_scalar(hook_match.group("hook_id"))
            current_hook_line = line_number
            current_hook_indent = len(hook_match.group("indent"))
            continue

        list_item_match = LIST_ITEM_PATTERN.match(line)
        if (
            current_hook_id is not None
            and list_item_match is not None
            and len(list_item_match.group("indent")) <= current_hook_indent
        ):
            flush_current_hook()

        field_match = FIELD_PATTERN.match(line)
        if current_hook_id is None or field_match is None:
            continue

        field_indent = len(field_match.group("indent"))
        if field_indent <= current_hook_indent:
            continue

        key = field_match.group("key")
        value = normalize_scalar(field_match.group("value"))
        if key == "entry":
            current_entry = value
            current_entry_line = line_number
        elif key == "language":
            current_language = value
            current_language_line = line_number

    flush_current_hook()
    return violations


def main() -> int:
    files = [Path(file_name) for file_name in sys.argv[1:]]
    if not files:
        return 0

    violations: list[str] = []
    for path in files:
        violations.extend(check_file(path))

    if violations:
        print("Pre-commit hook language lint failed:")
        for violation in violations:
            print(f"  - {violation}")
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
