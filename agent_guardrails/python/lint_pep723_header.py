# /// script
# requires-python = ">=3.10"
# dependencies = ["packaging>=24"]
# ///
"""Pre-commit hook: enforce the portable single-file script convention.

Scripts that are meant to be carried around and run by other people must be
self-contained. We codify that as: ``uv run <file>`` is the canonical entry
point, the script declares its own Python version and dependencies inline via
PEP 723, and the script's docstring shows the user how to invoke it.

This hook does NOT silently skip files lacking a PEP 723 header — that is the
violation. Consumers narrow the scope (which files are scanned) through
pre-commit's ``files`` / ``exclude`` filters; everything that gets through
must satisfy every rule below.

Rules (each scanned file must satisfy all):

1. The file contains a ``# /// script`` ... ``# ///`` block (PEP 723 header).
2. The block declares ``requires-python``.
3. ``requires-python`` is a single ``>=`` specifier (no ``==``, ``~=``, range,
   etc.).
4. The declared version is ``>=`` the configured baseline (default ``3.10``).
5. The file has a module docstring, and the docstring mentions
   ``uv run <this-filename>`` so users can copy-paste the invocation.

Version parsing and comparison go through PyPA's ``packaging`` library so all
PEP 440 forms (``3``, ``3.10``, ``3.10.1``, pre/post releases, whitespace) are
handled correctly.

Usage:
    uv run lint_pep723_header.py [--min-python X.Y] FILE [...]
"""

from __future__ import annotations

import argparse
import ast
import sys
import tomllib
from pathlib import Path

from packaging.specifiers import InvalidSpecifier, SpecifierSet
from packaging.version import InvalidVersion, Version


BLOCK_OPEN = "# /// script"
BLOCK_CLOSE = "# ///"
ALLOWED_OPERATOR = ">="
DEFAULT_MIN_PYTHON = "3.10"


def parse_min_python(value: str) -> Version:
    """Parse the ``--min-python`` argument into a ``Version``."""
    try:
        return Version(value)
    except InvalidVersion as exc:
        raise argparse.ArgumentTypeError(
            f"--min-python must be a PEP 440 version (got {value!r}): {exc}"
        ) from exc


def extract_block(lines: list[str]) -> tuple[int, int] | None:
    """Return ``(open_idx, close_idx)`` for the PEP 723 script block, or None."""
    open_idx: int | None = None
    for idx, line in enumerate(lines):
        stripped = line.rstrip("\n")
        if open_idx is None:
            if stripped == BLOCK_OPEN:
                open_idx = idx
            continue
        if stripped == BLOCK_CLOSE:
            return open_idx, idx
    return None


def block_to_toml(lines: list[str], open_idx: int, close_idx: int) -> str:
    """Strip the leading ``# `` / ``#`` prefix from each block line for TOML parsing."""
    body: list[str] = []
    for line in lines[open_idx + 1 : close_idx]:
        stripped = line.rstrip("\n")
        if stripped.startswith("# "):
            body.append(stripped[2:])
        elif stripped.startswith("#"):
            body.append(stripped[1:])
        else:
            body.append(stripped)
    return "\n".join(body) + "\n"


def _validate_requires_python(path: Path, raw: str, baseline: Version) -> list[str]:
    """Check ``requires-python`` value against the form + baseline rules."""
    try:
        spec_set = SpecifierSet(raw)
    except InvalidSpecifier as exc:
        return [
            f"{path}: PEP 723 requires-python {raw!r} is not a valid PEP 440 specifier: {exc}"
        ]

    specs = list(spec_set)
    if len(specs) != 1 or specs[0].operator != ALLOWED_OPERATOR:
        return [
            f"{path}: PEP 723 requires-python uses unsupported form {raw!r}\n"
            f"  (project policy: only a single \">=X.Y\" specifier is allowed)"
        ]

    try:
        declared = Version(specs[0].version)
    except InvalidVersion as exc:
        return [
            f"{path}: PEP 723 requires-python {raw!r} contains an invalid version: {exc}"
        ]

    if declared < baseline:
        return [
            f"{path}: PEP 723 requires-python {raw!r} is below baseline "
            f"\">={baseline}\"\n"
            f"  (override via --min-python in your .pre-commit-config.yaml if needed)"
        ]

    return []


def _validate_docstring(path: Path, source: str) -> list[str]:
    """Check that the file has a module docstring mentioning ``uv run <self>``."""
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return [f"{path}: cannot parse Python source for docstring check: {exc}"]

    docstring = ast.get_docstring(tree)
    if not docstring:
        return [
            f"{path}: missing module docstring\n"
            f"  (portable scripts must self-document; show users how to invoke "
            f"the script via `uv run`)"
        ]

    expected = f"uv run {path.name}"
    if expected not in docstring:
        return [
            f"{path}: docstring is missing a `{expected}` invocation example\n"
            f"  (portable scripts must show the canonical `uv run <self>` "
            f"command so users can copy-paste it)"
        ]

    return []


def check_file(path: Path, baseline: Version) -> list[str]:
    """Run all rules against a single file. Return a list of error messages."""
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return [f"{path}: cannot read file: {exc}"]

    errors: list[str] = []

    lines = text.splitlines(keepends=True)
    bounds = extract_block(lines)
    if bounds is None:
        errors.append(
            f"{path}: missing PEP 723 inline metadata block (`# /// script` ... `# ///`)\n"
            f"  (portable scripts must declare their Python version and dependencies "
            f"inline so `uv run <file>` works with zero setup; see skill-hub#151)"
        )
    else:
        open_idx, close_idx = bounds
        toml_body = block_to_toml(lines, open_idx, close_idx)
        try:
            data = tomllib.loads(toml_body)
        except tomllib.TOMLDecodeError as exc:
            errors.append(f"{path}: PEP 723 header is not valid TOML: {exc}")
        else:
            raw = data.get("requires-python")
            if raw is None:
                errors.append(
                    f"{path}: PEP 723 header missing 'requires-python'"
                )
            elif not isinstance(raw, str):
                errors.append(
                    f"{path}: PEP 723 'requires-python' must be a string "
                    f"(got {type(raw).__name__})"
                )
            else:
                errors.extend(_validate_requires_python(path, raw, baseline))

    errors.extend(_validate_docstring(path, text))

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Enforce the portable single-file script convention: every scanned "
            "file must carry a PEP 723 header and a docstring with a `uv run` example."
        )
    )
    parser.add_argument(
        "--min-python",
        default=parse_min_python(DEFAULT_MIN_PYTHON),
        type=parse_min_python,
        help=f"Minimum Python version baseline as a PEP 440 version (default: {DEFAULT_MIN_PYTHON}).",
    )
    parser.add_argument("files", nargs="*", help="Python files to check.")
    args = parser.parse_args()

    failed = False
    for file_str in args.files:
        for message in check_file(Path(file_str), args.min_python):
            sys.stderr.write(message + "\n")
            failed = True

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
