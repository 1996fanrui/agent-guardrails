# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Pre-commit hook: long-running systemd services must use ``uv run --no-cache``.

A long-lived plain ``uv run`` holds uv's global cache lock for its whole
lifetime, so the cache can never be cleaned. Each ``ExecStart=`` in a
``[Service]`` section that runs ``uv run`` must therefore pass ``--no-cache``,
unless the unit is ``Type=oneshot``: those exit, so they are short tasks.

``--no-cache`` counts only as an option of uv itself, so it must come before the
first positional argument of ``uv run``: anything after it belongs to the
launched command. An option value such as ``--project DIR`` is a positional
argument here, because telling it apart from a command needs uv's full option
table. Put ``--no-cache`` right after ``uv run`` to satisfy the hook.

Usage:
    uv run lint_uv_long_running.py FILE [...]
"""

from __future__ import annotations

import argparse
import shlex
import sys
from collections.abc import Iterator
from pathlib import Path


NO_CACHE = "--no-cache"
ONESHOT = "oneshot"
SERVICE_SECTION = "Service"
# Special executable prefixes from systemd.service(5), e.g. `ExecStart=-/usr/bin/uv`.
EXEC_PREFIX_CHARS = "-@:+!|"
SHELL_OPERATOR_CHARS = frozenset("();<>|&")


def logical_lines(text: str) -> Iterator[tuple[int, str]]:
    """Yield ``(first_line_number, line)``, joining backslash continuations."""
    pending: list[str] = []
    start = 0
    for number, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        # systemd also drops comment lines in the middle of a continuation.
        if line.startswith(("#", ";")):
            continue
        if not pending:
            start = number
        if line.endswith("\\"):
            pending.append(line[:-1])
            continue
        pending.append(line)
        yield start, " ".join(pending)
        pending = []
    if pending:
        yield start, " ".join(pending)


def parse_service_section(text: str) -> tuple[str, list[tuple[int, str]]]:
    """Return the effective ``Type=`` and ``ExecStart=`` entries of ``[Service]``."""
    section = ""
    service_type = ""
    exec_starts: list[tuple[int, str]] = []
    for number, line in logical_lines(text):
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1]
            continue
        key, separator, value = line.partition("=")
        if section != SERVICE_SECTION or not separator:
            continue
        key = key.strip()
        value = value.strip()
        if key == "Type":
            service_type = value
        elif key == "ExecStart":
            # An empty assignment resets the list, as systemd does.
            if value:
                exec_starts.append((number, value))
            else:
                exec_starts.clear()
    return service_type, exec_starts


def split_commands(text: str) -> Iterator[list[str]]:
    """Split a command line into argv lists at shell operators.

    Tokens holding whitespace are quoted scripts such as ``bash -c "uv run x"``
    or ``flock LOCK -c "uv run x"``, so they are split recursively.
    """
    lexer = shlex.shlex(text, posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    lexer.commenters = ""
    command: list[str] = []
    for token in lexer:
        if set(token) <= SHELL_OPERATOR_CHARS:
            yield command
            command = []
        elif len(token.split()) > 1:
            yield from split_commands(token)
        else:
            command.append(token)
    yield command


def find_run_subcommand(uv_args: list[str]) -> int | None:
    """Return the index of ``run`` in the arguments after ``uv``, if it is the subcommand.

    Global options may precede it (``uv --directory DIR run``), and any other
    subcommand ends the search (``uv pip install run``).
    """
    previous = ""
    for index, token in enumerate(uv_args):
        if token == "run":
            return index
        if not token.startswith("-") and not previous.startswith("-"):
            return None
        previous = token
    return None


def uv_options(uv_args: list[str], run_index: int) -> list[str]:
    """Return the options given to uv: global ones plus those leading ``run``."""
    options = uv_args[:run_index]
    for token in uv_args[run_index + 1 :]:
        if token == "--" or not token.startswith("-"):
            break
        options.append(token)
    return options


def runs_uv_without_no_cache(command: list[str]) -> bool:
    for index, token in enumerate(command):
        if token.rsplit("/", 1)[-1] != "uv":
            continue
        uv_args = command[index + 1 :]
        run_index = find_run_subcommand(uv_args)
        if run_index is not None and NO_CACHE not in uv_options(uv_args, run_index):
            return True
    return False


def check_file(path: Path) -> list[str]:
    """Return one error message per offending ``ExecStart=``."""
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return [f"{path}: cannot read file: {exc}"]

    service_type, exec_starts = parse_service_section(text)
    if service_type == ONESHOT:
        return []

    errors: list[str] = []
    for number, value in exec_starts:
        try:
            commands = list(split_commands(value.lstrip(EXEC_PREFIX_CHARS)))
        except ValueError as exc:
            errors.append(f"{path}:{number}: cannot parse ExecStart: {exc}")
            continue
        if any(runs_uv_without_no_cache(command) for command in commands):
            errors.append(
                f"{path}:{number}: long-running ExecStart must use `uv run {NO_CACHE}`\n"
                f"  (a long-lived plain `uv run` holds uv's global cache lock; put "
                f"{NO_CACHE} right after `uv run`, or use Type={ONESHOT} for a short task)"
            )
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Require `uv run --no-cache` in long-running systemd services."
    )
    parser.add_argument("files", nargs="*", help="systemd .service files to check.")
    args = parser.parse_args()

    failed = False
    for file_str in args.files:
        for message in check_file(Path(file_str)):
            sys.stderr.write(message + "\n")
            failed = True

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
