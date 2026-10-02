# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Lint rule: every directory holding Markdown notes must have a folder note.

A folder note is a Markdown file named after its directory, for example
``Kafka/Kafka.md`` (the Obsidian folder note convention). Every directory on
the path of a Markdown file is checked, so category directories that only hold
subdirectories are covered too. The repository root is not checked. Consumers
choose which directories are exempt via pre-commit ``exclude``.

With ``--top-level-folder-note-only``, a top-level directory may additionally
hold no Markdown file other than its folder note: notes belong in
subdirectories, and the top-level folder note only navigates to them.

Usage:
    uv run lint_folder_note.py [--top-level-folder-note-only] FILE [...]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def missing_folder_notes(files: list[Path]) -> list[Path]:
    """Return directories containing the given files that lack a same-name note."""
    directories = {
        directory
        for path in files
        for directory in path.parents
        if directory != Path(".")
    }
    return sorted(
        directory
        for directory in directories
        if not (directory / f"{directory.name}.md").is_file()
    )


def top_level_non_folder_notes(files: list[Path]) -> list[Path]:
    """Return files placed directly in a top-level directory other than its folder note."""
    return sorted(
        path
        for path in files
        if len(path.parts) == 2 and path.name != f"{path.parent.name}.md"
    )


def parse_args(argv: list[str]) -> tuple[bool, list[Path]]:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        prog="lint-folder-note",
        description="Fail when a directory holding Markdown notes lacks a same-name folder note.",
    )
    parser.add_argument(
        "--top-level-folder-note-only",
        action="store_true",
        help="Also fail when a top-level directory holds a Markdown file other than its folder note.",
    )
    parser.add_argument("files", nargs="*")
    args = parser.parse_args(argv)
    return args.top_level_folder_note_only, [Path(file_name) for file_name in args.files]


def main() -> int:
    top_level_folder_note_only, files = parse_args(sys.argv[1:])

    # Report POSIX paths so messages match what pre-commit passes on every OS.
    violations = [
        f"{directory.as_posix()}/ is missing its folder note "
        f"{(directory / (directory.name + '.md')).as_posix()}"
        for directory in missing_folder_notes(files)
    ]
    if top_level_folder_note_only:
        violations.extend(
            f"{path.as_posix()} is in top-level directory {path.parent.as_posix()}/, which may only hold its folder note; "
            "move it into a subdirectory"
            for path in top_level_non_folder_notes(files)
        )

    if violations:
        print("Folder note lint failed:")
        for violation in violations:
            print(f"  - {violation}")
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
