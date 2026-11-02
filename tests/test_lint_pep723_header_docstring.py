from __future__ import annotations

from pathlib import Path

import pytest
from packaging.version import Version

from _pep723_fixtures import pep723_fixture
from agent_guardrails.python.lint_pep723_header import check_file


_BLOCK = ['requires-python = ">=3.10"', "dependencies = []"]
_FILENAME = "tool.py"


def _violations(tmp_path: Path, invocation: str) -> list[str]:
    script = tmp_path / _FILENAME
    docstring = f'"""Example script.\n\nUsage:\n    {invocation}\n"""'
    script.write_text(pep723_fixture(_FILENAME, block_lines=_BLOCK, docstring=docstring), encoding="utf-8")
    return check_file(script, Version("3.10"))


@pytest.mark.parametrize(
    "invocation",
    [
        f"uv run {_FILENAME}",
        f"uv run {_FILENAME} --flag",
        f"uv run --no-cache {_FILENAME}",
        f"uv run --no-cache {_FILENAME} --flag",
    ],
)
def test_accepted_invocations(tmp_path: Path, invocation: str) -> None:
    assert _violations(tmp_path, invocation) == []


@pytest.mark.parametrize(
    "invocation",
    [
        "uv run --no-cache other.py",
        f"uv run --no-cache-dir {_FILENAME}",
        f"uv run --quiet {_FILENAME}",
        f"uv run --no-cache --quiet {_FILENAME}",
        f"uv --no-cache run {_FILENAME}",
        f"uv run  --no-cache {_FILENAME}",
        f"python {_FILENAME}",
    ],
)
def test_rejected_invocations(tmp_path: Path, invocation: str) -> None:
    violations = _violations(tmp_path, invocation)

    assert len(violations) == 1
    assert "invocation example" in violations[0]
