from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from agent_guardrails.general.lint_no_ignored_files import find_ignored


def _init_repo(root: Path, gitignore: str) -> None:
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    (root / ".gitignore").write_text(gitignore, encoding="utf-8")


@pytest.fixture()
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    _init_repo(tmp_path, "build/\n*.log\n")
    monkeypatch.chdir(tmp_path)
    return tmp_path


def test_returns_nothing_when_no_path_is_ignored(repo: Path) -> None:
    assert find_ignored(["README.md", "src/main.py"]) == []


def test_empty_input_skips_git_entirely(repo: Path) -> None:
    assert find_ignored([]) == []


def test_reports_the_matching_gitignore_rule(repo: Path) -> None:
    violations = find_ignored(["build/out.o"])

    assert len(violations) == 1
    # The message must keep naming the rule source so `git rm --cached` guidance
    # stays actionable.
    assert violations[0].startswith("build/out.o: matched by .gitignore:1:build/")


def test_reports_every_ignored_path_in_a_mixed_batch(repo: Path) -> None:
    """A single batched call must not lose violations that follow clean paths."""
    violations = find_ignored(["README.md", "build/out.o", "src/main.py", "debug.log"])

    assert [v.split(":", 1)[0] for v in violations] == ["build/out.o", "debug.log"]


def test_handles_paths_containing_spaces(repo: Path) -> None:
    """NUL-delimited I/O keeps odd filenames from splitting into bogus records."""
    violations = find_ignored(["my build/a.log", "README.md"])

    assert len(violations) == 1
    assert violations[0].startswith("my build/a.log: matched by ")


def test_raises_when_git_cannot_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A non-repository must fail loudly rather than report zero violations."""
    monkeypatch.chdir(tmp_path)

    with pytest.raises(RuntimeError):
        find_ignored(["README.md"])
