"""Lint rule: enforce a maximum line count per tracked text file."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


MAX_LINE_COUNT = 800
LOCKFILE_NAMES = frozenset(
    {
        "uv.lock",
        "poetry.lock",
        "Pipfile.lock",
        "package-lock.json",
        "pnpm-lock.yaml",
        "yarn.lock",
        "bun.lock",
        "bun.lockb",
        "Cargo.lock",
    }
)


def parse_max_lines(value: str) -> int:
    """Return a validated maximum line count value."""
    max_lines = int(value)
    if max_lines <= 0:
        raise argparse.ArgumentTypeError("--max-lines must be greater than zero")
    return max_lines


def parse_args(argv: list[str]) -> tuple[int, list[Path]]:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        prog="lint-file-line-count",
        description="Fail when a tracked text file exceeds the configured line limit.",
    )
    parser.add_argument(
        "--max-lines",
        type=parse_max_lines,
        default=MAX_LINE_COUNT,
        help="Maximum allowed line count per file. Defaults to 800.",
    )
    parser.add_argument("files", nargs="*")
    args = parser.parse_args(argv)
    return args.max_lines, [Path(file_name) for file_name in args.files]


def check_file(path: Path, *, max_lines: int) -> list[str]:
    """Return line-count violations for a single file."""
    if not path.is_file():
        return []
    if path.name in LOCKFILE_NAMES:
        return []

    try:
        raw_content = path.read_bytes()
    except OSError as exc:
        raise RuntimeError(f"Failed to read {path}: {exc}") from exc

    if b"\x00" in raw_content:
        return []

    try:
        content = raw_content.decode("utf-8")
    except UnicodeDecodeError:
        return []

    line_count = len(content.splitlines())
    if line_count <= max_lines:
        return []

    return [
        (
            f"{path} has {line_count} lines, which exceeds the maximum of "
            f"{max_lines}. Split the document or refactor the code."
        )
    ]


def main() -> int:
    max_lines, files = parse_args(sys.argv[1:])
    if not files:
        return 0

    violations: list[str] = []
    for path in files:
        violations.extend(check_file(path, max_lines=max_lines))

    if violations:
        print("File line-count lint failed:")
        for violation in violations:
            print(f"  - {violation}")
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
