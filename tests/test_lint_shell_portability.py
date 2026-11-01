from __future__ import annotations

from pathlib import Path

import pytest

from agent_guardrails.shell.lint_shell_portability import check_file


def _violations(tmp_path: Path, line: str) -> list[str]:
    script = tmp_path / "script.sh"
    script.write_text(f"{line}\n", encoding="utf-8")
    return check_file(script)


@pytest.mark.parametrize(
    "line",
    [
        r"grep -P '\d+' file",
        r"git --version | grep -oP '\d+\.\d+' | head -1",
        r"grep -i -P '\d+' file",
        r"grep --perl-regexp '\d+' file",
        r"/usr/bin/grep -P '\d+' file",
    ],
)
def test_grep_perl_regexp_is_rejected(tmp_path: Path, line: str) -> None:
    violations = _violations(tmp_path, line)

    assert len(violations) == 1
    assert "SHP006" in violations[0]


@pytest.mark.parametrize(
    "line",
    [
        r"grep -oE '[0-9]+\.[0-9]+' file",
        "grep -E 'a -P b' file",
        "grep -p file",
        "pgrep -P 1",
        "git grep -P foo",
        "ggrep -P foo file",
        "grep -P foo file  # noqa: shell-portability",
    ],
)
def test_portable_commands_are_allowed(tmp_path: Path, line: str) -> None:
    assert _violations(tmp_path, line) == []
